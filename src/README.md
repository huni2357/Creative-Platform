
# PHQ9 Privacy-Aware Usage Collector

## Folder Structure
```
phq9-usage-collector/
├─ extension/
│  ├─ manifest.json
│  ├─ background.js
│  ├─ content_script.js
│  ├─ options.html
│  └─ options.js
└─ server/
   ├─ package.json
   ├─ server.js
   ├─ seed.js
   └─ metrics_demo.js
```

## How to Run (Server)
```bash
cd server
npm i
npm run start   # Server on http://localhost:4000
# optional: seed several thousand events
npm run seed
# metrics example
npm run metrics
```

## How to Load (Chrome Extension)
1. Edit `extension/background.js` and set `API_BASE` (default: `http://localhost:4000`) and `API_KEY` to match the server.
2. Open `chrome://extensions` → enable Developer mode → "Load unpacked" → select the `extension` folder.
3. Open the extension **Options** page to toggle *Enable*, add excluded domains, change batch interval.
4. As you browse, the extension batches events to `POST /events/batch`.

## Privacy
- Query strings are stripped from URLs before storing/sending.
- Raw search terms are never stored; only coarse categories (search_web/images/videos/news) are logged.
- You can disable collection or exclude specific domains in Options.
