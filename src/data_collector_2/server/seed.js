import Database from "better-sqlite3";

const db = new Database("events.db");
db.pragma("journal_mode = WAL");

db.exec(`
CREATE TABLE IF NOT EXISTS raw_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  type TEXT NOT NULL,
  url TEXT,
  host TEXT,
  category TEXT,
  tabId INTEGER,
  dwell_ms INTEGER,
  speed_px_per_s REAL,
  count INTEGER
);
`);

const insert = db.prepare(`
  INSERT INTO raw_events (ts, type, url, host, category, tabId, dwell_ms, speed_px_per_s, count)
  VALUES (@ts, @type, @url, @host, @category, @tabId, @dwell_ms, @speed_px_per_s, @count)
`);

const hosts = [
  { host: "www.google.com", category: "search" },
  { host: "www.youtube.com", category: "entertainment" },
  { host: "www.instagram.com", category: "sns" },
  { host: "en.wikipedia.org", category: "education" },
  { host: "www.bbc.com", category: "news" },
  { host: "github.com", category: "education" },
  { host: "other.site.com", category: "other" }
];

const now = Date.now();
const dayMs = 24*60*60*1000;
const start = now - 7*dayMs;

const tx = db.transaction(() => {
  for (let t = start; t < now; t += 30_000) { // 30초 간격으로 여러 이벤트 생성
    const h = hosts[Math.floor(Math.random()*hosts.length)];
    const dwell = Math.floor(Math.random()*90_000); // <= 90초
    insert.run({
      ts: t,
      type: Math.random() < 0.15 ? "visit" : "dwell",
      url: `https://${h.host}/path`,
      host: h.host,
      category: h.category,
      tabId: Math.floor(Math.random()*10),
      dwell_ms: dwell,
      speed_px_per_s: null,
      count: null
    });

    if (Math.random() < 0.05) { // 가끔 탭 수
      insert.run({
        ts: t + 1000,
        type: "tab_count",
        url: null, host: null, category: null, tabId: null,
        dwell_ms: null, speed_px_per_s: null, count: Math.floor(1+Math.random()*8)
      });
    }

    if (Math.random() < 0.05) { // 가끔 스크롤
      insert.run({
        ts: t + 2000,
        type: "scroll",
        url: null, host: null, category: null, tabId: null,
        dwell_ms: null, speed_px_per_s: Number((Math.random()*1200).toFixed(2)), count: null
      });
    }
  }
});

tx();
console.log("Seeded sample events.");