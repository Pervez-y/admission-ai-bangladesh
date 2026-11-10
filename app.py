import os, re, json, sqlite3, hashlib, asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote_plus
import httpx, feedparser
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parent
DB=Path(os.getenv("DB_PATH",ROOT/"admission.db"))
CFG=json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
POLL_MINUTES=int(os.getenv("POLL_MINUTES",CFG.get("poll_minutes",30)))
KEYWORDS=["admission","admit card","application","apply","circular","admission test","ভর্তি","ভর্তির","আবেদন","ভর্তি পরীক্ষা","প্রবেশপত্র","ভর্তি বিজ্ঞপ্তি","আবেদনের সময়","মেধা তালিকা","ফলাফল","রেজাল্ট"]
CATEGORIES={
"GST / গুচ্ছ":["gst","গুচ্ছ","সমন্বিত"],
"Medical & Dental":["medical","dental","মেডিকেল","ডেন্টাল","এমবিবিএস","বিডিএস"],
"Engineering":["engineering","buet","kuet","ruet","cuet","প্রকৌশল"],
"National University":["national university","জাতীয় বিশ্ববিদ্যালয়","জাতীয় বিশ্ববিদ্যালয়"],
"Public University":["public university","ঢাকা বিশ্ববিদ্যালয়","জাহাঙ্গীরনগর","রাজশাহী বিশ্ববিদ্যালয়","চট্টগ্রাম বিশ্ববিদ্যালয়","জগন্নাথ"],
"Private University":["private university","বেসরকারি বিশ্ববিদ্যালয়"]}
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute("""CREATE TABLE IF NOT EXISTS updates(id TEXT PRIMARY KEY,title TEXT,summary TEXT,url TEXT,source TEXT,published TEXT,category TEXT,created TEXT)""")
 c.execute("CREATE TABLE IF NOT EXISTS subscriptions(endpoint TEXT PRIMARY KEY,data TEXT)")
 c.commit();return c
def classify(t):
 t=t.lower()
 if not any(k in t for k in KEYWORDS):return None
 for cat,words in CATEGORIES.items():
  if any(w in t for w in words):return cat
 return "General Admission"
def plain(s):return re.sub(r"\\s+"," ",re.sub(r"<[^>]+>"," ",s or "")).strip()
async def summarize(title,desc):
 text=plain(desc) or title
 base=os.getenv("AI_BASE_URL","").rstrip("/");key=os.getenv("AI_API_KEY","");model=os.getenv("AI_MODEL","")
 if base and key and model:
  try:
   async with httpx.AsyncClient(timeout=20) as c:
    r=await c.post(base+"/chat/completions",headers={"Authorization":"Bearer "+key},
     json={"model":model,"messages":[{"role":"user","content":"Summarize this Bangladesh university admission notice in simple Bangla, under 70 words. Mention dates only if explicitly stated; do not invent details.\\n\\nTitle: "+title+"\\nText: "+text[:5000]}],"temperature":0.2})
    r.raise_for_status();return r.json()["choices"][0]["message"]["content"].strip()
  except Exception as e:print("AI summary unavailable:",e)
 return (text[:260]+("…" if len(text)>260 else "")) or "নতুন ভর্তি-সংক্রান্ত আপডেট শনাক্ত হয়েছে।"
async def push(payload):
 if not(os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_PRIVATE_KEY")):return
 from pywebpush import webpush
 con=db();rows=con.execute("SELECT endpoint,data FROM subscriptions").fetchall();con.close()
 for row in rows:
  try:
   d=json.loads(row["data"])
   webpush(subscription_info={"endpoint":row["endpoint"],"keys":d["keys"]},data=json.dumps(payload),
    vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],vapid_claims={"sub":os.getenv("VAPID_CLAIMS_EMAIL","mailto:admin@example.com")})
  except Exception as e:
   if "410" in str(e) or "404" in str(e):
    con=db();con.execute("DELETE FROM subscriptions WHERE endpoint=?",(row["endpoint"],));con.commit();con.close()
   else:print("Push failed:",e)
async def add(title,link,source,published,desc):
 cat=classify(title+" "+plain(desc))
 if not cat or not link:return 0
 uid=hashlib.sha256(link.encode()).hexdigest();summary=await summarize(title,desc)
 con=db();cur=con.execute("INSERT OR IGNORE INTO updates VALUES(?,?,?,?,?,?,?,?)",
  (uid,title,summary,link,source,published or "",cat,datetime.now(timezone.utc).isoformat()))
 con.commit();new=cur.rowcount>0;con.close()
 if new:await push({"title":"Admission update: "+title[:90],"body":summary[:150],"url":link})
 return int(new)
async def scan():
 total=0;targets=[]
 for q in CFG.get("google_news_queries",[]):
  targets.append(("Google News discovery · "+q,"https://news.google.com/rss/search?q="+quote_plus(q)+"&hl=en-BD&gl=BD&ceid=BD:en"))
 for f in CFG.get("feeds",[]):
  u=f.get("url","")
  if u.startswith(("http://","https://")):targets.append((f.get("name","Custom RSS feed"),u))
 async with httpx.AsyncClient(timeout=25,follow_redirects=True,headers={"User-Agent":"AdmissionAI-Bangladesh/1.0"}) as client:
  for source,url in targets:
   try:
    r=await client.get(url);r.raise_for_status();feed=feedparser.parse(r.text)
    for e in feed.entries[:50]:
     total+=await add(e.get("title","Untitled"),e.get("link",""),source,e.get("published",""),e.get("summary",""))
   except Exception as e:print("Feed failed",source,str(e)[:150])
 return total
async def loop():
 while True:
  try:await scan()
  except Exception as e:print("Scanner error:",e)
  await asyncio.sleep(max(5,POLL_MINUTES)*60)
@asynccontextmanager
async def lifespan(app):
 db().close();task=asyncio.create_task(loop());yield;task.cancel()
app=FastAPI(title="Admission AI Bangladesh API",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
@app.get("/")
def health():return {"app":"Admission AI Bangladesh API","status":"running"}
@app.get("/api/status")
def status():
 c=db();n=c.execute("SELECT COUNT(*) FROM updates").fetchone()[0];subs=c.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0];last=c.execute("SELECT MAX(created) FROM updates").fetchone()[0];c.close()
 return {"monitoring":True,"poll_minutes":POLL_MINUTES,"updates":n,"subscribers":subs,"last_new_update":last,"ai_enabled":bool(os.getenv("AI_API_KEY"))}
@app.get("/api/updates")
def updates(limit:int=100,category:str="All"):
 c=db()
 if category=="All":rows=c.execute("SELECT * FROM updates ORDER BY created DESC LIMIT ?",(min(limit,300),)).fetchall()
 else:rows=c.execute("SELECT * FROM updates WHERE category=? ORDER BY created DESC LIMIT ?",(category,min(limit,300))).fetchall()
 c.close();return [dict(x) for x in rows]
@app.post("/api/scan")
async def manual_scan():return {"new_updates":await scan()}
class Sub(BaseModel):
 endpoint:str
 keys:dict
@app.post("/api/subscribe")
def subscribe(s:Sub):
 if not s.endpoint.startswith("https://"):raise HTTPException(400,"Invalid push endpoint")
 c=db();c.execute("INSERT OR REPLACE INTO subscriptions VALUES(?,?)",(s.endpoint,json.dumps({"keys":s.keys})));c.commit();c.close();return {"ok":True}
@app.get("/api/push-public-key")
def push_key():return {"publicKey":os.getenv("VAPID_PUBLIC_KEY","")}
