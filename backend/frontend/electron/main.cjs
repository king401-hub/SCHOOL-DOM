const { app, BrowserWindow, dialog, shell } = require("electron");
const fs = require("fs");
const path = require("path");

const DEFAULT_SERVER_URL = process.env.SCHOOLDOM_CBT_SERVER_URL || "http://127.0.0.1:5173";

function readBundledConfig() {
  const candidates = [
    path.join(__dirname, "..", "cbt-server.json"),
    path.join(process.resourcesPath || "", "app", "cbt-server.json"),
  ];
  for (const filePath of candidates) {
    try {
      if (filePath && fs.existsSync(filePath)) {
        return JSON.parse(fs.readFileSync(filePath, "utf8"));
      }
    } catch {
      return {};
    }
  }
  return {};
}

const bundledConfig = readBundledConfig();

function normalizeServerUrl(value) {
  const raw = String(value || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(raw)) {
    return `http://${raw}`;
  }
  return raw;
}

function studentCbtUrl() {
  return `${normalizeServerUrl(process.env.SCHOOLDOM_CBT_SERVER_URL || bundledConfig.serverUrl)}/student-cbt`;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 720,
    fullscreen: true,
    kiosk: process.env.SCHOOLDOM_CBT_KIOSK === "true",
    autoHideMenuBar: true,
    title: "SchoolDom Student CBT",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.setMenuBarVisibility(false);
  win.loadURL(studentCbtUrl());

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  win.webContents.on("will-navigate", (event, url) => {
    const allowedOrigin = new URL(normalizeServerUrl(process.env.SCHOOLDOM_CBT_SERVER_URL || bundledConfig.serverUrl)).origin;
    const nextOrigin = new URL(url).origin;
    if (nextOrigin !== allowedOrigin) {
      event.preventDefault();
    }
  });

  win.webContents.on("did-fail-load", async (_event, _code, description) => {
    const { response } = await dialog.showMessageBox(win, {
      type: "error",
      buttons: ["Retry", "Close"],
      defaultId: 0,
      cancelId: 1,
      title: "Cannot reach admin server",
      message: "The student CBT app could not connect to the admin local server.",
      detail: `${studentCbtUrl()}\n\n${description}`,
    });
    if (response === 0) {
      win.loadURL(studentCbtUrl());
    } else {
      win.close();
    }
  });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
