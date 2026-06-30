# Clean Hour — PWA app (branch: clean-hour-ant)

A responsive, installable web app (PWA) with the liquid-glass design.
Works on iPhone and Android in the browser, and can be added to the home screen.

## Files
- `index.html` — the app (Now / Impact / Settings tabs, liquid glass, animated clock)
- `api/grid.js` — serverless function that holds the API key and returns grid data
- `manifest.json`, `sw.js`, `icon-192.png`, `icon-512.png` — PWA install support
- `team-version.html` — the original team dashboard (kept as backup)

## Run locally (sample data)
Any static server works; the app falls back to sample data when `/api/grid` isn't available:
```
python3 -m http.server 8000
```
Open http://localhost:8000 — you'll see the app with sample data.

## Deploy with LIVE data (recommended: Vercel, free)
1. Push this branch to GitHub (already done).
2. Go to vercel.com → New Project → import the `clean-hour` repo → pick this branch.
3. In Project Settings → Environment Variables, add:
   - `ELECTRICITYMAPS_TOKEN` = your Electricity Maps API token
4. Deploy. Vercel auto-detects `api/grid.js` as a serverless function.
5. Open the deployed URL on your phone → "Add to Home Screen" to install.

The browser never sees the API key — it only calls `/api/grid`, and the
serverless function calls Electricity Maps server-side.

## How the data flows
browser (index.html) → /api/grid (serverless, holds key) → Electricity Maps → back to the app

Endpoints used (all allowed on the free trial): `/latest`, `/history`, `/forecast`.
