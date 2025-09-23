// ====== CONFIG ======
const API_BASE = "http://localhost:4000";
const BATCH_ENDPOINT = `${API_BASE}/events/batch`;
const DEFAULT_BATCH_SECONDS = 60; // 배치 전송 주기
const API_KEY = "PHQ9123"; // 서버와 반드시 동일하게

// ====== STATE ======
const tabActivity = {};
let currentActiveTabId = null;

// ====== UTIL ======
const now = () => Date.now();

const stripQuery = (u) => {
  try {
    const url = new URL(u);
    url.search = ""; // 쿼리 제거
    url.hash = ""; // 해시 제거
    return url.toString();
  } catch {
    return u;
  }
};

const hostOf = (u) => {
  try {
    return new URL(u).hostname;
  } catch {
    return "";
  }
};

/**
 * URL을 분석하여 카테고리를 반환합니다.
 * @param {string} url
 * @returns {string} 'search'|'sns'|'entertainment'|'news'|'education'|'other'
 */
function detectCategory(url) {
  const host = hostOf(url);

  // 검색 (Search)
  if (
    /(google\.[^/]+|bing\.com|duckduckgo\.com)/.test(host) ||
    host.includes("search.naver.com") ||
    host.includes("search.daum.net")
  )
    return "search";

  // SNS
  if (
    /(instagram\.com|facebook\.com|x\.com|twitter\.com|threads\.net|linkedin\.com|pinterest\.com|tiktok\.com)/.test(
      host
    )
  )
    return "sns";

  // 엔터테인먼트 (Entertainment)
  if (
    /(youtube\.com|netflix\.com|twitch\.tv|watcha\.com|wavve\.com|tving\.com)/.test(
      host
    )
  )
    return "entertainment";

  // 뉴스 (News)
  if (
    /(news\.google\.com|news\.naver\.com|media\.daum\.net|bbc\.com|nytimes\.com|cnn\.com)/.test(
      host
    )
  )
    return "news";

  // 교육 (Education)
  if (/(\.ac\.kr|\.edu|wikipedia\.org|stackoverflow\.com|github\.com)/.test(host))
    return "education";

  // 기타
  return "other";
}

// ====== CORE LOGIC ======
async function getSettings() {
  return await chrome.storage.sync.get({
    enabled: true,
    excludeHosts: [],
    batchSeconds: DEFAULT_BATCH_SECONDS,
  });
}

async function pushEvent(ev) {
  const { eventQueue = [] } = await chrome.storage.local.get("eventQueue");
  eventQueue.push(ev);
  await chrome.storage.local.set({ eventQueue });
}

async function deactivateTab(tabId) {
  if (!tabId || !tabActivity[tabId] || !tabActivity[tabId].activeSince) return;

  const dwellMs = now() - tabActivity[tabId].activeSince;
  if (dwellMs > 1000) { // 1초 이상 머무른 경우만 기록
    await pushEvent({
      type: "dwell",
      ts: now(),
      url: tabActivity[tabId].url,
      host: tabActivity[tabId].host,
      category: tabActivity[tabId].category,
      tabId: tabId,
      dwell_ms: dwellMs,
    });
  }
  tabActivity[tabId].activeSince = null;
}

async function activateTab(tabId) {
  if (!tabId || !tabActivity[tabId]) return;
  tabActivity[tabId].activeSince = now();
  currentActiveTabId = tabId;
}

async function handleUrlChange(tabId, url) {
  if (!url || !/^(https?:)?\/\//.test(url)) return;

  await deactivateTab(tabId);

  const { excludeHosts } = await getSettings();
  const host = hostOf(url);
  if (excludeHosts.includes(host)) return;

  const category = detectCategory(url);
  tabActivity[tabId] = {
    url: stripQuery(url),
    host,
    category,
    activeSince: null,
  };

  await pushEvent({
    type: "visit",
    ts: now(),
    url: stripQuery(url),
    host,
    category,
    tabId,
  });

  // 탭이 활성 상태이면 바로 activate
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTab && activeTab.id === tabId) {
    await activateTab(tabId);
  }
}

/**
 * ⭐️ [새 기능] 주기적으로 현재 탭 개수를 기록합니다.
 */
async function recordTabCount() {
    const settings = await getSettings();
    if (!settings.enabled) return;

    chrome.tabs.query({}, (tabs) => {
        pushEvent({
            type: 'tab_count',
            count: tabs.length,
            ts: now()
        });
    });
}


// ====== EVENT HANDLERS ======
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  await deactivateTab(currentActiveTabId);
  await activateTab(activeInfo.tabId);
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    await handleUrlChange(tabId, tab.url);
  }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  await deactivateTab(tabId);
  delete tabActivity[tabId];
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
  await deactivateTab(currentActiveTabId);
  if (windowId !== chrome.windows.WINDOW_ID_NONE) {
    const [activeTab] = await chrome.tabs.query({ active: true, windowId });
    if (activeTab) await activateTab(activeTab.id);
  }
});


// ====== BATCH UPLOAD ======
async function flushBatch() {
  const settings = await getSettings();
  if (!settings.enabled) return;

  const { eventQueue = [] } = await chrome.storage.local.get({ eventQueue: [] });
  if (eventQueue.length === 0) return;

  const sanitized = eventQueue.map((e) => ({ ...e, url: e.url ? stripQuery(e.url) : "" }));

  try {
    const res = await fetch(BATCH_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
      body: JSON.stringify({ events: sanitized }),
    });
    if (!res.ok) {
      console.warn("Batch upload failed:", res.status, await res.text());
      return;
    }
    await chrome.storage.local.set({ eventQueue: [] });
  } catch (e) {
    console.warn("Batch error:", e);
  }
}

// ====== ALARMS & LIFECYCLE ======

// 확장 프로그램이 설치되거나 시작될 때 알람 설정
function setupAlarms() {
    chrome.alarms.get("batch_upload", async (existing) => {
        if (!existing) {
            const { batchSeconds } = await getSettings();
            chrome.alarms.create("batch_upload", { periodInMinutes: batchSeconds / 60 });
        }
    });
    // ⭐️ 1분마다 탭 개수를 기록하는 알람 설정
    chrome.alarms.get("tab_count", (existing) => {
        if (!existing) {
            chrome.alarms.create("tab_count", { periodInMinutes: 1 });
        }
    });
}

// 알람 리스너
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "batch_upload") {
        flushBatch();
    } else if (alarm.name === "tab_count") {
        recordTabCount();
    }
});

// 설정에서 전송 주기가 바뀌면 알람을 다시 설정
chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "sync" && changes.batchSeconds) {
        const periodInMinutes = Math.max(0.25, changes.batchSeconds.newValue / 60);
        chrome.alarms.create("batch_upload", { periodInMinutes });
    }
});

// 브라우저 시작 시
chrome.runtime.onStartup.addListener(setupAlarms);
// 확장 프로그램 설치 시
chrome.runtime.onInstalled.addListener(setupAlarms);