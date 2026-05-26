const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const fs = require("fs");
const path = require("path");
const { APP_NAME, DEFAULT_CLOUD_URL } = require("./config.cjs");
const db = require("./db.cjs");
const { pushPendingResults, syncFromCloud } = require("./syncService.cjs");

const isDev = !app.isPackaged;
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    title: APP_NAME,
    icon: path.join(__dirname, "..", "public", "schooldom-favicon.jpeg"),
    backgroundColor: "#eff6ff",
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.setMenuBarVisibility(false);

  if (isDev) {
    mainWindow.loadURL("http://127.0.0.1:5174");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, targetUrl) => {
    const allowed = isDev ? "http://127.0.0.1:5174" : "file://";
    if (!String(targetUrl).startsWith(allowed)) event.preventDefault();
  });
}

function registerIpc() {
  ipcMain.handle("app:bootstrap", () => ({
    appName: APP_NAME,
    cloudUrl: db.getSetting("cloudUrl") || DEFAULT_CLOUD_URL,
    snapshot: db.getAdminSnapshot(),
  }));

  ipcMain.handle("admin:getSnapshot", () => db.getAdminSnapshot());
  ipcMain.handle("admin:getLogs", () => db.getActivityLogs());
  ipcMain.handle("admin:cleanupCache", () => db.cleanupSyncedCache());
  ipcMain.handle("admin:saveOfflineSettings", (_event, payload = {}) => db.saveOfflineSettings(payload));
  ipcMain.handle("admin:importExamPackage", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "Import SchoolDom CBT exam package",
      properties: ["openFile"],
      filters: [
        { name: "SchoolDom CBT Package", extensions: ["json"] },
      ],
    });
    if (result.canceled || !result.filePaths.length) {
      return { success: false, canceled: true };
    }
    const raw = fs.readFileSync(result.filePaths[0], "utf8");
    const payload = JSON.parse(raw);
    return db.importExamPackage(payload);
  });
  ipcMain.handle("admin:exportResultsPackage", async () => {
    const payload = db.buildResultsPackage();
    const stamp = new Date().toISOString().replace(/\D/g, "").slice(0, 14);
    const result = await dialog.showSaveDialog(mainWindow, {
      title: "Export SchoolDom CBT results package",
      defaultPath: `schooldom-cbt-results-${stamp}.json`,
      filters: [
        { name: "SchoolDom CBT Results", extensions: ["json"] },
      ],
    });
    if (result.canceled || !result.filePath) {
      return { success: false, canceled: true };
    }
    fs.writeFileSync(result.filePath, JSON.stringify(payload, null, 2), "utf8");
    return { success: true, filePath: result.filePath, summary: payload.summary };
  });
  ipcMain.handle("admin:syncFromCloud", async (_event, payload = {}) => syncFromCloud(payload));
  ipcMain.handle("admin:pushResults", async (_event, payload = {}) => pushPendingResults(payload));

  ipcMain.handle("student:login", (_event, payload = {}) => db.validateStudentLogin(payload));
  ipcMain.handle("student:getExam", (_event, examId) => {
    const exam = db.getExamPayload(examId);
    return exam ? { success: true, exam } : { success: false, message: "Exam not found." };
  });
  ipcMain.handle("student:saveAnswers", (_event, payload = {}) => ({ success: true, session: db.saveAnswers(payload) }));
  ipcMain.handle("student:submit", (_event, payload = {}) => db.submitSession(payload.sessionId, payload.cause));
  ipcMain.handle("student:focusLoss", (_event, payload = {}) => ({ success: true, session: db.logFocusLoss(payload) }));

  ipcMain.handle("window:enterFullscreen", () => {
    mainWindow?.setFullScreen(true);
    mainWindow?.setAlwaysOnTop(true, "screen-saver");
    return { success: true };
  });
  ipcMain.handle("window:exitFullscreen", () => {
    mainWindow?.setAlwaysOnTop(false);
    mainWindow?.setFullScreen(false);
    return { success: true };
  });
}

process.on("uncaughtException", (error) => {
  dialog.showErrorBox("SchoolDom CBT Client error", error.message || "Unexpected desktop error.");
});

app.whenReady().then(async () => {
  await db.openDatabase();
  registerIpc();
  createWindow();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
