// main.js 예시
const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow () {
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      // 렌더러 프로세스에서 Node.js 모듈 사용을 허용하는 설정 (필수)
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // 앱의 UI를 정의하는 HTML 파일을 로드
  mainWindow.loadFile('index.html');

  // 개발자 도구 열기 (개발 중 디버깅에 유용)
  // mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});