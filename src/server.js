
import express from "express";
import Database from "better-sqlite3";
import cors from 'cors';

const app = express();
app.use(express.json({ limit: "10mb" }));
app.use(cors());

app.use((req, res, next) => {
  console.log("REQ", req.method, req.path, "x-api-key:", req.header("x-api-key"));
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-api-key");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(204); // CORS preflight 통과
  next();
});
app.get("/", (req, res) => res.json({ ok: true, service: "phq9-collector" }));


const PORT = 4000;
const API_KEY = "PHQ9123"; // 확장과 동일해야 함

// --- DB 준비 ---
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

CREATE INDEX IF NOT EXISTS idx_raw_ts ON raw_events(ts);
CREATE INDEX IF NOT EXISTS idx_raw_host ON raw_events(host);
`);

// API KEY 미들웨어
app.use((req, res, next) => {
  const key = req.header("x-api-key");
  console.log("API key received:", key);
  if (key !== API_KEY) {
    return res.status(401).json({ error: "Invalid API key" });
  }
  next();
});

// 배치 수신
app.post("/events/batch", (req, res) => {
  const { events } = req.body || {};
  if (!Array.isArray(events) || events.length === 0) {
    return res.status(400).json({ error: "No events" });
  }

  const insert = db.prepare(`
    INSERT INTO raw_events (ts, type, url, host, category, tabId, dwell_ms, speed_px_per_s, count)
    VALUES (@ts, @type, @url, @host, @category, @tabId, @dwell_ms, @speed_px_per_s, @count)
  `);

  const tx = db.transaction((rows) => {
    for (const e of rows) {
      insert.run({
        ts: e.ts ?? Date.now(),
        type: e.type ?? "unknown",
        url: e.url ?? null,
        host: e.host ?? null,
        category: e.category ?? null,
        tabId: e.tabId ?? null,
        dwell_ms: e.dwell_ms ?? null,
        speed_px_per_s: e.speed_px_per_s ?? null,
        count: e.count ?? null
      });
    }
  });

  try {
    tx(events);
    return res.json({ ok: true, inserted: events.length });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "DB insert failed" });
  }
});

// --- Metrics (daily) ---
app.get("/metrics/daily", (req, res) => {
  const dayStart = Number(req.query.dayStart) || startOfLocalDayMs(Date.now());
  const dayEnd = dayStart + 24*60*60*1000;

  const q = (sql, params={}) => db.prepare(sql).all(params);
  const s = (sql, params={}) => db.prepare(sql).get(params);

  // 1) 총 사용시간(분): dwell 합
  const dwell = s(`
    SELECT COALESCE(SUM(dwell_ms),0) AS total_ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
  `, { a: dayStart, b: dayEnd }).total_ms;

  // 2) 심야비율(0~6시)
  const late = s(`
    SELECT COALESCE(SUM(dwell_ms),0) AS ms
    FROM raw_events
    WHERE type='dwell'
      AND ts BETWEEN @a AND @b
      AND strftime('%H', datetime(ts/1000, 'unixepoch', localtime)) BETWEEN '00' AND '05'
  `, { a: dayStart, b: dayEnd }).ms;

  // 3) SNS/엔터 비율
  const snsEnt = s(`
    SELECT COALESCE(SUM(dwell_ms),0) AS ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
      AND (category='sns' OR category='entertainment')
  `, { a: dayStart, b: dayEnd }).ms;

  // 4) 세션 길이
  const sessions = q(`
    SELECT dwell_ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
      AND dwell_ms IS NOT NULL
  `, { a: dayStart, b: dayEnd }).map(r => r.dwell_ms);

  const sessionMax = sessions.length ? Math.max(...sessions) : 0;
  const sessionMean = sessions.length ? (sessions.reduce((x,y)=>x+y,0)/sessions.length) : 0;

  // 5) bounce ratio: ≤10초 비율
  const shortCnt = sessions.filter(ms => ms <= 10_000).length;
  const bounceRatio = sessions.length ? shortCnt / sessions.length : 0;

  // 6) 평균 탭 수
  const avgTabCnt = s(`
    SELECT AVG(count) AS avgCnt
    FROM raw_events
    WHERE type='tab_count' AND ts BETWEEN @a AND @b
  `, { a: dayStart, b: dayEnd }).avgCnt || 0;

  // 7) 검색 빈도
  const searchFreq = s(`
    SELECT COUNT(*) AS c
    FROM raw_events
    WHERE type='visit' AND ts BETWEEN @a AND @b
      AND category LIKE 'search%'
  `, { a: dayStart, b: dayEnd }).c || 0;

  // 8) 반복 사이트 비율 (상위 5)
  const topHosts = q(`
    SELECT host, COALESCE(SUM(dwell_ms),0) AS ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
    GROUP BY host
    ORDER BY ms DESC LIMIT 5
  `, { a: dayStart, b: dayEnd });

  const topMs = topHosts.reduce((s, r) => s + (r.ms||0), 0);
  const repeatSiteRatio = (dwell > 0) ? (topMs / dwell) : 0;

  res.json({
    total_usage_daily: roundMin(dwell),
    late_night_ratio: safeRatio(late, dwell),
    sns_ent_ratio: safeRatio(snsEnt, dwell),
    session_length_max: toMin(sessionMax),
    session_length_mean: toMin(sessionMean),
    bounce_ratio: bounceRatio,
    avg_tab_cnt: Number(avgTabCnt.toFixed(2)),
    search_freq: searchFreq,
    repeat_site_ratio: repeatSiteRatio
  });
});

function roundMin(ms) { return Math.round((ms/60000)*100)/100; }
function toMin(ms) { return Math.round((ms/60000)*100)/100; }
function safeRatio(num, den) { return den > 0 ? num/den : 0; }
function startOfLocalDayMs(t) {
  const d = new Date(t);
  d.setHours(0,0,0,0);
  return d.getTime();
}

app.listen(PORT, () => {
  console.log(`Server on http://localhost:${PORT}`);
});
