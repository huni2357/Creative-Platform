
// 스크롤 속도 같은 페이지 내 상호작용은 콘텐츠 스크립트에서 수집
let lastY = window.scrollY;
let lastTime = Date.now();

window.addEventListener("scroll", () => {
  const nowY = window.scrollY;
  const nowTime = Date.now();

  const deltaY = Math.abs(nowY - lastY);
  const deltaT = (nowTime - lastTime) / 1000;
  const speed = deltaY / Math.max(deltaT, 0.001); // px/s

  chrome.storage.local.get({ eventQueue: [] }, ({ eventQueue }) => {
    eventQueue.push({
      type: "scroll",
      speed_px_per_s: Number(speed.toFixed(2)),
      ts: Date.now()
    });
    chrome.storage.local.set({ eventQueue });
  });

  lastY = nowY;
  lastTime = nowTime;
});
