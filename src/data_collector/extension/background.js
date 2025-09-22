// background.js
let activeTabInfo = { tabId: null, windowId: null, url: null, startTime: null };

async function startTracking(tabId, windowId) {
  if (activeTabInfo.tabId === tabId) return;
  await flushActiveTab();
  const tab = await chrome.tabs.get(tabId);
  if (tab && tab.url && tab.url.startsWith('http')) {
    activeTabInfo = { tabId, windowId, url: tab.url, startTime: Date.now() };
  }
}

async function flushActiveTab() {
  if (activeTabInfo.startTime && activeTabInfo.url) {
    const endTime = Date.now();
    const duration = Math.round((endTime - activeTabInfo.startTime) / 1000);
    if (duration > 0) {
      const { items = [] } = await chrome.storage.local.get('items');
      items.push({
        url: activeTabInfo.url,
        startTime: new Date(activeTabInfo.startTime).toISOString(),
        endTime: new Date(endTime).toISOString(),
        duration_seconds: duration,
        tabId: activeTabInfo.tabId,
        windowId: activeTabInfo.windowId,
      });
      await chrome.storage.local.set({ items });
    }
  }
  activeTabInfo = { tabId: null, windowId: null, url: null, startTime: null };
}

async function flushBatch() {
  const { items, apiToken, enabled } = await chrome.storage.local.get(['items', 'apiToken', 'enabled']);
  if (!enabled || !items || items.length === 0 || !apiToken) {
    if (!apiToken && enabled) console.error("API Token is not set.");
    return;
  }
  try {
    const response = await fetch('http://127.0.0.1:5000/events/batch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiToken}`,
      },
      body: JSON.stringify(items),
    });
    if (response.ok) {
      console.log('Batch upload successful');
      await chrome.storage.local.remove('items');
    } else {
      const errorBody = await response.json();
      console.error(`Batch upload failed: ${response.status}`, errorBody);
    }
  } catch (error) {
    console.error('Batch error:', error);
  }
}

chrome.tabs.onActivated.addListener(activeInfo => startTracking(activeInfo.tabId, activeInfo.windowId));
chrome.windows.onFocusChanged.addListener(windowId => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    flushActiveTab();
    return;
  }
  chrome.tabs.query({ active: true, windowId }, tabs => {
    if (tabs[0]) startTracking(tabs[0].id, windowId);
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tab.active && changeInfo.url) {
    startTracking(tabId, tab.windowId);
  }
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('batchUpload', { periodInMinutes: 1.0 });
});

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'batchUpload') {
    flushBatch();
  }
});
