import express from "express";
import Database from "better-sqlite3";
import cors from 'cors';

const app = express();
app.use(express.json({ limit: "10mb" }));
app.use(cors());

const PORT = 4000;
const API_KEY = "PHQ9123"; // 확장 프로그램과 동일한 키

// --- DB 준비 ---
const db = new Database("events.db");
db.pragma("journal_mode = WAL");

// raw_events 테이블 구조 (확장 프로그램과 호환)
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

// ⭐️ [새로 추가된 부분] 계산된 일일 지표를 저장할 테이블
db.exec(`
CREATE TABLE IF NOT EXISTS daily_metrics (
  day_start_ms INTEGER PRIMARY KEY,
  total_usage REAL,
  late_night_ratio REAL,
  sns_ent_ratio REAL,
  session_length_max REAL,
  session_length_mean REAL,
  bounce_ratio REAL,
  avg_tab_cnt REAL,
  search_freq INTEGER,
  repeat_site_ratio REAL
);
`);


// API KEY 검증 미들웨어
app.use((req, res, next) => {
  if (req.method === 'OPTIONS') {
    return next();
  }
  const key = req.header("x-api-key");
  if (key !== API_KEY) {
    return res.status(401).json({ error: "Invalid API key" });
  }
  next();
});

// 확장 프로그램으로부터 이벤트 데이터를 받는 엔드포인트
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
    res.status(201).json({ ok: true, inserted: events.length });
  } catch (err) {
    console.error("DB insert failed:", err);
    res.status(500).json({ error: "DB insert failed" });
  }
});


/**
 * 지정된 기간(aMs ~ bMs) 동안의 원시 데이터를 분석하여 10가지 지표를 계산하는 함수
 */
function computeMetrics(aMs, bMs) {
  const s = (sql, params={}) => db.prepare(sql).get(params);
  const q = (sql, params={}) => db.prepare(sql).all(params);

  // 1. 총 사용 시간 (dwell 이벤트의 시간 합)
  const dwellTotal = s(`
    SELECT COALESCE(SUM(dwell_ms), 0) AS ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
  `, { a: aMs, b: bMs }).ms;

  // 2. 심야 사용 시간 (00~06시 사이)
  const late = s(`
    SELECT COALESCE(SUM(dwell_ms), 0) AS ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
      AND strftime('%H', datetime(ts/1000, 'unixepoch', 'localtime')) BETWEEN '00' AND '05'
  `, { a: aMs, b: bMs }).ms;

  // 3. SNS/엔터테인먼트 사용 시간
  const snsEnt = s(`
    SELECT COALESCE(SUM(dwell_ms), 0) AS ms
    FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
      AND category IN ('sns', 'entertainment')
  `, { a: aMs, b: bMs }).ms;

  // 4, 5. 세션 길이 (최대/평균)
  const sessions = q(`
    SELECT dwell_ms FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b AND dwell_ms IS NOT NULL
  `, { a: aMs, b: bMs }).map(r => r.dwell_ms);

  const sessionMax = sessions.length ? Math.max(...sessions) : 0;
  const sessionMean = sessions.length ? sessions.reduce((x, y) => x + y, 0) / sessions.length : 0;

  // 6. 즉시 이탈 비율 (10초 미만 체류)
  const shortCnt = sessions.filter(ms => ms <= 10000).length;
  const bounceRatio = sessions.length ? shortCnt / sessions.length : 0;

  // 7. 평균 탭 개수 (tab_count 이벤트의 count 평균)
  const avgTabCnt = s(`
    SELECT AVG(count) AS avgCnt FROM raw_events
    WHERE type='tab_count' AND ts BETWEEN @a AND @b
  `, { a: aMs, b: bMs }).avgCnt || 0;

  // 8. 검색 빈도 (search 카테고리 visit 수)
  const searchFreq = s(`
    SELECT COUNT(*) AS c FROM raw_events
    WHERE type='visit' AND ts BETWEEN @a AND @b AND (category = 'search' OR category LIKE 'search_%')
  `, { a: aMs, b: bMs }).c || 0;

  // 9. 반복 사이트 비율 (상위 5개 사이트 체류 시간 / 전체 체류 시간)
  const topHosts = q(`
    SELECT host, SUM(dwell_ms) AS ms FROM raw_events
    WHERE type='dwell' AND ts BETWEEN @a AND @b
    GROUP BY host ORDER BY ms DESC LIMIT 5
  `, { a: aMs, b: bMs });

  const topMs = topHosts.reduce((sum, row) => sum + row.ms, 0);
  const repeatSiteRatio = dwellTotal > 0 ? topMs / dwellTotal : 0;
  
  // 최종 결과 포맷팅
  const toMin = (ms) => Math.round((ms / 60000) * 100) / 100;
  const safeRatio = (num, den) => (den > 0 ? num / den : 0);

  return {
    total_usage: toMin(dwellTotal),
    late_night_ratio: safeRatio(late, dwellTotal),
    sns_ent_ratio: safeRatio(snsEnt, dwellTotal),
    session_length_max: toMin(sessionMax),
    session_length_mean: toMin(sessionMean),
    bounce_ratio: bounceRatio,
    avg_tab_cnt: Number(avgTabCnt.toFixed(2)),
    search_freq: searchFreq,
    repeat_site_ratio: repeatSiteRatio
  };
}

const startOfLocalDayMs = (t) => new Date(t).setHours(0, 0, 0, 0);
const startOfLocalWeekMs = (t) => {
  const d = new Date(startOfLocalDayMs(t));
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff)).getTime();
};

app.get("/metrics/daily", (req, res) => {
  const dayStart = Number(req.query.dayStart) || startOfLocalDayMs(Date.now());
  const dayEnd = dayStart + 24 * 60 * 60 * 1000;
  const m = computeMetrics(dayStart, dayEnd);

  // ⭐️ [수정된 부분] 계산된 지표를 DB에 저장합니다.
  try {
    const stmt = db.prepare(`
      INSERT OR REPLACE INTO daily_metrics (
        day_start_ms, total_usage, late_night_ratio, sns_ent_ratio,
        session_length_max, session_length_mean, bounce_ratio,
        avg_tab_cnt, search_freq, repeat_site_ratio
      ) VALUES (
        @day_start_ms, @total_usage, @late_night_ratio, @sns_ent_ratio,
        @session_length_max, @session_length_mean, @bounce_ratio,
        @avg_tab_cnt, @search_freq, @repeat_site_ratio
      )
    `);
    stmt.run({
      day_start_ms: dayStart,
      total_usage: m.total_usage,
      late_night_ratio: m.late_night_ratio,
      sns_ent_ratio: m.sns_ent_ratio,
      session_length_max: m.session_length_max,
      session_length_mean: m.session_length_mean,
      bounce_ratio: m.bounce_ratio,
      avg_tab_cnt: m.avg_tab_cnt,
      search_freq: m.search_freq,
      repeat_site_ratio: m.repeat_site_ratio
    });
    console.log(`[DB] ${new Date(dayStart).toLocaleDateString()}의 지표를 저장했습니다.`);
  } catch (err) {
    console.error("일일 지표 저장 실패:", err);
  }

  res.json({ total_usage_daily: m.total_usage, ...m });
});

app.get("/metrics/weekly", (req, res) => {
  const weekStart = Number(req.query.weekStart) || startOfLocalWeekMs(Date.now());
  const weekEnd = weekStart + 7 * 24 * 60 * 60 * 1000;
  const m = computeMetrics(weekStart, weekEnd);
  res.json({ total_usage_weekly: m.total_usage, ...m });
});

// 서버 시작
app.listen(PORT, () => {
  console.log(`Server on http://localhost:${PORT}`);
});