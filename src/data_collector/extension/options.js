// options.js
const apiTokenInput = document.getElementById('apiToken');
const enabledCheckbox = document.getElementById('enabled');
const excludeTextarea = document.getElementById('exclude');
const batchSecondsInput = document.getElementById('batchSeconds');
const saveButton = document.getElementById('save');
const statusSpan = document.getElementById('status');

function loadSettings() {
  chrome.storage.local.get(
    ['apiToken', 'enabled', 'excludeList', 'batchSeconds'],
    (result) => {
      apiTokenInput.value = result.apiToken || '';
      enabledCheckbox.checked = result.enabled ?? true;
      excludeTextarea.value = (result.excludeList || []).join('\n');
      batchSecondsInput.value = result.batchSeconds || 60;
    }
  );
}

function saveSettings() {
  const settings = {
    apiToken: apiTokenInput.value.trim(),
    enabled: enabledCheckbox.checked,
    excludeList: excludeTextarea.value.split('\n').map(s => s.trim()).filter(Boolean),
    batchSeconds: parseInt(batchSecondsInput.value, 10),
  };
  chrome.storage.local.set(settings, () => {
    statusSpan.textContent = 'Options saved.';
    setTimeout(() => { statusSpan.textContent = ''; }, 1500);
  });
}

document.addEventListener('DOMContentLoaded', loadSettings);
saveButton.addEventListener('click', saveSettings);
