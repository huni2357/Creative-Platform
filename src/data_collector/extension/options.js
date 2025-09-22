
const $ = (id) => document.getElementById(id);

async function load() {
  chrome.storage.sync.get(
    { enabled: true, excludeHosts: [], batchSeconds: 60 },
    ({ enabled, excludeHosts, batchSeconds }) => {
      $("enabled").checked = enabled;
      $("exclude").value = (excludeHosts || []).join("\n");
      $("batchSeconds").value = batchSeconds;
    }
  );
}

document.getElementById("save").addEventListener("click", () => {
  const enabled = document.getElementById("enabled").checked;
  const excludeHosts = document.getElementById("exclude")
    .value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  const batchSeconds = Math.max(15, parseInt(document.getElementById("batchSeconds").value || "60", 10));

  chrome.storage.sync.set({ enabled, excludeHosts, batchSeconds }, () => {
    const status = document.getElementById("status");
    status.textContent = "Saved!";
    setTimeout(() => status.textContent = "", 1500);
  });
});

load();
