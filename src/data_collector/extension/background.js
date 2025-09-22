
// ====== CONFIG ======
const API_BASE = "http://localhost:4000";
const BATCH_ENDPOINT = `${API_BASE}/events/batch`;
const DEFAULT_BATCH_SECONDS = 60; // 배치 전송 주기
const API_KEY = "PHQ9123"; // 서버와 반드시 동일하게

// ====== STATE ======
/**
 * tabActivity[tabId] = {
 *   url: "https://example.com/path",
 *   host: "example.com",
 *   category: "search|sns|entertainment|news|education|other",
 *   activeSince: epoch_ms | null
 * }
 */
const tabActivity = {};
let currentActiveTabId = null;

// ====== UTIL ======
const stripQuery = (u) => {
  try {
    const url = new URL(u);
    url.search = "";   // 쿼리 제거
    url.hash = "";     // 해시 제거
    return url.toString();
  } catch {
    return u;
  }
};

const hostOf = (u) => {
  try { return new URL(u).hostname; } catch { return ""; }
};

// 검색 카테고리(원문 금지): 엔진/버티컬만 판별
function detectCategory(url) {
  const host = hostOf(url);
  const path = (() => { try { return new URL(url).pathname.toLowerCase(); } catch { return ""; } })();

  // 대표 검색엔진: 쿼리 파라미터는 이미 stripQuery()로 제거됨
  const isSearchEngine =
    /(google\.[^/]+|bing\.com|search\.naver\.com|duckduckgo\.com)/i.test(host);

  if (isSearchEngine) {
    // 버티컬 기초 분류 (원문 검색어 저장 X)
    if (path.includes("/news")) return "search_news";
    if (path.includes("/images")) return "search_images";
    if (path.includes("/videos")) return "search_videos";
    return "search_web";
  }

  // 아주 단순한 호스트 기반 휴리스틱
  if (/(facebook|instagram|x\.com|twitter|naver\.com\/post)/i.test(host)) return "sns";
  if (/(youtube|twitch|netflix|watcha|wavve|tving)/i.test(host)) return "entertainment";
  if (/(news|nytimes|bbc|hani|chosun|joongang|donga|khan)/i.test(host)) return "news";
  if (/(ac\.kr|edu|wikipedia|wikimedia|khanacademy|coursera|edx)/i.test(host)) return "education";
  return "other";
}

async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(
      { enabled: true, excludeHosts: [], batchSeconds: DEFAULT_BATCH_SECONDS },
      resolve
    );
  });
}

function isExcluded(host, excludeHosts) {
  return excludeHosts.some((h) => host.endsWith(h) || h === host);
}

function now() { return Date.now(); }

// 저장소 enqueue
function pushEvent(ev) {
  chrome.storage.local.get({ eventQueue: [] }, ({ eventQueue }) => {
    eventQueue.push(ev);
    chrome.storage.local.set({ eventQueue });
  });
}

// 비활성화/전환 시 체류시간 종료 기록
async function closeDwell(tabId) {
  const state = tabActivity[tabId];
  if (!state || state.activeSince == null) return;

  const dwellMs = now() - state.activeSince;
  state.activeSince = null;

  pushEvent({
    type: "dwell",
    url: state.url,
    host: state.host,
    category: state.category,
    dwell_ms: dwellMs,
    tabId,
    ts: now()
  });
}

// ====== TAB/LIFECYCLE HOOKS ======
async function handleUrlChange(tabId, url) {
  const settings = await getSettings();
  if (!settings.enabled) return;

  const stripped = stripQuery(url);
  const host = hostOf(stripped);
  if (!host || isExcluded(host, settings.excludeHosts)) return;

  const category = detectCategory(stripped);

  tabActivity[tabId] = {
    ...(tabActivity[tabId] || {}),
    url: stripped,
    host,
    category
  };

  // 방문 이벤트
  pushEvent({
    type: "visit",
    url: stripped,
    host,
    category,
    tabId,
    ts: now()
  });
}

// 활성 탭 바뀔 때
async function activateTab(tabId) {
  const settings = await getSettings();
  if (!settings.enabled) return;

  if (currentActiveTabId != null && currentActiveTabId !== tabId) {
    await closeDwell(currentActiveTabId);
  }
  currentActiveTabId = tabId;

  // 새 탭 활성 시작 시간
  if (!tabActivity[tabId]) tabActivity[tabId] = { activeSince: now() };
  tabActivity[tabId].activeSince = now();

  // 동시 탭 수 이벤트
  const tabs = await chrome.tabs.query({});
  pushEvent({ type: "tab_count", count: tabs.length, ts: now() });
}

// 탭 닫힘
chrome.tabs.onRemoved.addListener(async (tabId) => {
  await closeDwell(tabId);
  delete tabActivity[tabId];
});

// 탭 활성화
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  await activateTab(tabId);
});

// 창 포커스 변경
chrome.windows.onFocusChanged.addListener(async (winId) => {
  const settings = await getSettings();
  if (!settings.enabled) return;

  if (winId === chrome.windows.WINDOW_ID_NONE && currentActiveTabId != null) {
    await closeDwell(currentActiveTabId);
    currentActiveTabId = null;
  } else if (winId !== chrome.windows.WINDOW_ID_NONE) {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tab?.id != null) await activateTab(tab.id);
  }
});

// 네비게이션 커밋
chrome.webNavigation.onCommitted.addListener(async (details) => {
  if (details.frameId !== 0) return; // 메인 프레임만
  await handleUrlChange(details.tabId, details.url);
});

// ====== BATCH UPLOAD ======
async function flushBatch() {
  const settings = await getSettings();
  if (!settings.enabled) return;

  const { eventQueue = [] } = await chrome.storage.local.get({ eventQueue: [] });
  if (eventQueue.length === 0) return;

  // 안전장치: 혹시 남아있을 수 있는 쿼리 제거
  const sanitized = eventQueue.map((e) => ({ ...e, url: stripQuery(e.url || "") }));

  try {
    const res = await fetch(BATCH_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
      body: JSON.stringify({ events: sanitized })
    });
    if (!res.ok) {
      const t = await res.text();
      console.warn("Batch upload failed:", res.status, t);
      return; // 실패 시 큐 유지
    }
    await chrome.storage.local.set({ eventQueue: [] });
    pushEvent({ type: "batch_ok", count: sanitized.length, ts: now() });
  } catch (e) {
    console.warn("Batch error:", e);
  }
}

// 알람으로 주기적 전송
chrome.alarms.create("batch_upload", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "batch_upload") await flushBatch();
});

// 최초 설치 시 기본값
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ enabled: true, excludeHosts: [], batchSeconds: DEFAULT_BATCH_SECONDS });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg === "flush_now" || (msg && msg.type === "flush_now")) {
    // 비동기 응답을 위해 true 반환
    (async () => {
      try {
        await flushBatch();
        sendResponse({ ok: true });
      } catch (e) {
        console.warn("flush_now error:", e);
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true;
  }
});