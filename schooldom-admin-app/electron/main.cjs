const { app, BrowserWindow, ipcMain, shell } = require("electron");
const fs = require("fs");
const path = require("path");
const { APP_NAME, DEFAULT_SERVER_URL, dataPath } = require("./config.cjs");
const lanServer = require("./lanServer.cjs");

const isDev = !app.isPackaged;
let mainWindow;

function normalizeServerUrl(value) {
  return String(value || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "") || DEFAULT_SERVER_URL;
}

function settingsPath() {
  return dataPath("settings.json");
}

function readSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath(), "utf8"));
  } catch {
    return {};
  }
}

function writeSettings(settings) {
  const target = settingsPath();
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(settings, null, 2), "utf8");
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || `Request failed (${response.status}).`);
  }
  return payload;
}

async function downloadFile(url, targetPath) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Download failed (${response.status}).`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, buffer);
  return targetPath;
}

async function bootstrap(payload = {}) {
  const saved = readSettings();
  const serverUrl = normalizeServerUrl(payload.serverUrl || saved.serverUrl);
  const schoolCode = String(payload.schoolCode || saved.schoolCode || "").trim();
  const query = schoolCode ? `?school_code=${encodeURIComponent(schoolCode)}` : "";
  const data = await fetchJson(`${serverUrl}/api/app/admin-desktop/bootstrap/${query}`);
  const nextSettings = {
    ...saved,
    serverUrl,
    schoolCode: schoolCode || data?.school?.school_code || "",
    school: data?.school || saved.school || null,
  };
  writeSettings(nextSettings);
  return {
    appName: APP_NAME,
    appVersion: app.getVersion(),
    serverUrl,
    ...data,
  };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 780,
    minWidth: 980,
    minHeight: 660,
    title: APP_NAME,
    icon: path.join(__dirname, "..", "public", "schooldom-favicon.jpeg"),
    backgroundColor: "#eef4fb",
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
    mainWindow.loadURL("http://127.0.0.1:5175");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedUrl) => {
    console.error("SchoolDom Admin failed to load", { errorCode, errorDescription, validatedUrl });
  });
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error("SchoolDom Admin renderer stopped", details);
  });
  mainWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    console.log("SchoolDom Admin renderer", { level, message, line, sourceId });
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, targetUrl) => {
    const allowed = isDev ? "http://127.0.0.1:5175" : "file://";
    if (!String(targetUrl).startsWith(allowed)) event.preventDefault();
  });
}

function registerIpc() {
  ipcMain.handle("app:bootstrap", async (_event, payload = {}) => bootstrap(payload));
  ipcMain.handle("app:settings", () => ({
    serverUrl: normalizeServerUrl(readSettings().serverUrl),
    schoolCode: readSettings().schoolCode || "",
  }));
  ipcMain.handle("app:saveSettings", (_event, payload = {}) => {
    const saved = readSettings();
    const next = {
      ...saved,
      serverUrl: normalizeServerUrl(payload.serverUrl),
      schoolCode: String(payload.schoolCode || "").trim(),
    };
    writeSettings(next);
    return next;
  });
  ipcMain.handle("app:openCbtInstaller", async (_event, payload = {}) => {
    const saved = readSettings();
    const serverUrl = normalizeServerUrl(payload.serverUrl || saved.serverUrl);
    const downloadUrl = payload.downloadUrl || `${serverUrl}/app/download/student-cbt/`;
    const targetPath = path.join(app.getPath("downloads"), "SchoolDomCBT.exe");
    await downloadFile(downloadUrl, targetPath);
    const openError = await shell.openPath(targetPath);
    if (openError) {
      throw new Error(openError);
    }
    return { success: true, downloadUrl, filePath: targetPath };
  });
  ipcMain.handle("lan:snapshot", () => lanServer.snapshot());
  ipcMain.handle("lan:start", () => lanServer.startServer());
  ipcMain.handle("lan:stop", () => lanServer.stopServer());
  ipcMain.handle("lan:publishExam", (_event, payload = {}) => lanServer.publishExam(payload));
}

process.on("uncaughtException", (error) => {
  console.error("SchoolDom Admin error", error);
});

app.whenReady().then(() => {
  registerIpc();
  createWindow();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
