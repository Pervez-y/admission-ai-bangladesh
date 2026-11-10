# Admission AI Bangladesh — Option A (HTML + Cloud Backend)

## Files
- `frontend/index.html`: one standalone HTML dashboard to upload to your HTML-to-APK workflow.
- `backend/`: cloud monitoring API, RSS scanner, SQLite storage, optional AI summaries and Web Push support.

## The simplest phone-friendly setup

### Part 1 — Deploy the backend once
You need an always-on Python hosting service. From your phone:
1. Download and unzip this project.
2. Create a GitHub account/repository and upload the **contents of the backend folder**.
3. On a Python host that supports GitHub deployments (for example Render, Railway, or a VPS), create a new web service from that repository.
4. Set the root directory to `backend` if you uploaded the whole project, or leave it blank if you uploaded only backend contents.
5. Build/install command: `pip install -r requirements.txt`
6. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
7. Use persistent storage for `admission.db` if the host supports it. Without a persistent disk, the update history can reset on redeploy.
8. After deploy, open `https://YOUR-SERVICE-URL/`. It should show JSON with `"status":"running"`.

The service scans Google News RSS discovery searches every 30 minutes by default. Set `POLL_MINUTES` to change it. Free services may sleep, pause, or have usage limits; if the host sleeps, scans and alerts are delayed.

### Part 2 — Connect the HTML
1. Open `frontend/index.html` in a text editor.
2. Upload it to an HTTPS static host (or host it on the same domain as your backend).
3. Open the hosted HTML page on your phone.
4. Paste your backend URL into **Cloud backend URL** and tap **Connect**.
5. Tap **Refresh** to see detected updates.
6. Give the hosted page a home-screen shortcut, or use that HTTPS URL in your HTML-to-APK converter if it supports loading a website URL.

You can also upload the standalone HTML to your APK converter as an asset and enter the backend URL in the app. Dashboard/API access should work if the converter permits network requests and HTTPS. Local-file Web Push is not reliable; see notification note below.

### Part 3 — Enable notifications
Push needs all of these:
- A deployed backend on HTTPS.
- VAPID public/private key pair configured as server environment variables:
  - `VAPID_PUBLIC_KEY`
  - `VAPID_PRIVATE_KEY` (PEM format expected by pywebpush)
  - `VAPID_CLAIMS_EMAIL` (e.g. `mailto:you@example.com`)
- A frontend running from an HTTPS origin with Service Worker + Push API support.
- User permission to show notifications.

The frontend's **Enable notifications** button registers a service worker from the backend URL and subscribes the browser. Some HTML-to-APK converters use WebView configurations that do not support Web Push. If your converter does not support Service Workers/Push API, notifications require a native Android wrapper / Firebase Cloud Messaging integration; simply converting HTML to APK cannot add that capability.

### AI summaries (optional)
Set these backend environment variables:
- `AI_BASE_URL` (OpenAI-compatible API base URL)
- `AI_API_KEY`
- `AI_MODEL`

Keep API keys on the server only, never in `index.html`. Without these, keyword filtering and a basic text extract are used; the app still works.

### Add official sources
Edit `backend/sources.json` and add real RSS/Atom feed URLs under `feeds`, for example:
`{"name":"University name","url":"https://official-site.example/feed.xml"}`
Do not add ordinary HTML homepages as RSS feeds. Google News RSS searches are discovery sources and can include third-party stories; always open the source link and verify the official notice. Some admission portals publish only PDFs, JavaScript pages, social posts, or login-only notices; those require separate supported integrations and are not automatically covered by this RSS starter.

## What is and isn't live yet
This is source code, not an already-hosted monitoring service. Until you deploy the backend and connect the frontend, there are no live updates or notifications. It does not guarantee detection of every Bangladesh institution's notice. The backend is a starter and should be secured with authentication/rate limiting before public production use, especially the manual scan endpoint.
