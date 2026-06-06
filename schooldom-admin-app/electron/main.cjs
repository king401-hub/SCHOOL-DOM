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

function readInstallSeed() {
  try {
    const downloadsPath = app.getPath("downloads");
    const seedPath = fs
      .readdirSync(downloadsPath, { withFileTypes: true })
      .filter((entry) => entry.isFile() && /^SchoolDomAdmin\.schooldom(?: \(\d+\))?\.json$/i.test(entry.name))
      .map((entry) => {
        const filePath = path.join(downloadsPath, entry.name);
        return { filePath, mtimeMs: fs.statSync(filePath).mtimeMs };
      })
      .sort((left, right) => right.mtimeMs - left.mtimeMs)[0]?.filePath;
    if (!seedPath) return {};
    const seed = JSON.parse(fs.readFileSync(seedPath, "utf8"));
    const schoolCode = String(seed.schoolCode || seed.school_code || "").trim();
    if (!schoolCode) return {};
    return {
      serverUrl: seed.serverUrl || seed.server_url || "",
      schoolCode,
      school: seed.school || null,
    };
  } catch {
    return {};
  }
}

function readSettings() {
  try {
    const saved = JSON.parse(fs.readFileSync(settingsPath(), "utf8"));
    const seed = readInstallSeed();
    if (!seed.schoolCode) return saved;
    return {
      ...saved,
      serverUrl: seed.serverUrl || saved.serverUrl,
      schoolCode: seed.schoolCode,
      school: seed.school || saved.school,
      desktopSettings: {
        ...(saved.desktopSettings || {}),
        ...(seed.school ? { schoolProfile: seed.school } : {}),
      },
    };
  } catch {
    const seed = readInstallSeed();
    return seed.schoolCode
      ? {
          serverUrl: seed.serverUrl,
          schoolCode: seed.schoolCode,
          school: seed.school,
          desktopSettings: seed.school ? { schoolProfile: seed.school } : {},
        }
      : {};
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

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || `Request failed (${response.status}).`);
  }
  return data;
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

function dashboardFromLocal(localData = {}, serverUrl = "") {
  const students = Array.isArray(localData.students) ? localData.students : [];
  const classes = Array.isArray(localData.classes) ? localData.classes : [];
  const exams = Array.isArray(localData.exams) ? localData.exams : [];
  const tokens = localData.activation_tokens || {};
  return {
    settings: {
      name: localData.school?.name || "SchoolDom",
      ip_address: normalizeServerUrl(serverUrl),
      refresh_interval: "Offline cache",
    },
    content: { total: exams.reduce((total, exam) => total + (exam.questions?.length || 0), 0) },
    candidate: { total: students.length, class: classes.length },
    client: { total: 1 },
    test: {
      total: exams.length,
      licensed: exams.filter((exam) => exam.is_published).length,
      pending: 0,
      ongoing: 0,
      submitted: 0,
      batch_count: 0,
    },
    tokens,
  };
}

async function bootstrap(payload = {}) {
  const saved = readSettings();
  const serverUrl = normalizeServerUrl(payload.serverUrl || saved.serverUrl);
  const schoolCode = String(payload.schoolCode || saved.schoolCode || "").trim();
  const query = schoolCode ? `?school_code=${encodeURIComponent(schoolCode)}` : "";
  try {
    const data = await fetchJson(`${serverUrl}/api/app/admin-desktop/bootstrap/${query}`);
    const fetchedSchoolCode = String(data?.school?.school_code || "").trim();
    if (!fetchedSchoolCode) {
      throw new Error("Enter your school code in Install & Settings, then refresh online to fetch this school's data.");
    }
    if (data?.local_data) {
      lanServer.importSchoolSnapshot(data.local_data);
    }
    const previousProfile = saved.desktopSettings?.schoolProfile || {};
    const shouldKeepLocalProfile =
      previousProfile?.school_code && previousProfile.school_code === fetchedSchoolCode && saved.desktopSettings?.schoolProfile;
    const nextSettings = {
      ...saved,
      serverUrl,
      schoolCode: fetchedSchoolCode,
      school: data?.school || saved.school || null,
      localData: data?.local_data || saved.localData || {},
      desktopSettings: {
        ...(saved.desktopSettings || {}),
        schoolProfile: shouldKeepLocalProfile ? previousProfile : data?.school || {},
        academicYear: saved.desktopSettings?.academicYear || data?.academic_year || null,
        term: saved.desktopSettings?.term || data?.term || null,
      },
    };
    writeSettings(nextSettings);
    return {
      appName: APP_NAME,
      appVersion: app.getVersion(),
      serverUrl,
      desktop_settings: nextSettings.desktopSettings,
      ...data,
    };
  } catch (error) {
    const localData = saved.localData || {};
    const cachedSchoolCode = String(saved.school?.school_code || localData.school?.school_code || "").trim();
    if (!schoolCode || (cachedSchoolCode && cachedSchoolCode !== schoolCode)) {
      throw error;
    }
    if (!Object.keys(localData).length && !saved.school) throw error;
    const cachedLocalData = {
      school: saved.school || localData.school || null,
      classes: localData.classes || [],
      students: localData.students || [],
      exams: localData.exams || [],
      activation_tokens: localData.activation_tokens || {},
    };
    lanServer.importSchoolSnapshot(cachedLocalData);
    return {
      appName: APP_NAME,
      appVersion: app.getVersion(),
      serverUrl,
      success: true,
      offline: true,
      school: cachedLocalData.school || { name: "SchoolDom", school_code: schoolCode },
      server: { online: false, host: serverUrl, error: error.message || "Offline" },
      downloads: { student_cbt: `${serverUrl}/app/download/student-cbt/` },
      dashboard: dashboardFromLocal(cachedLocalData, serverUrl),
      local_data: cachedLocalData,
      desktop_settings: saved.desktopSettings || {},
    };
  }
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
      desktopSettings: {
        ...(saved.desktopSettings || {}),
        ...(payload.desktopSettings || {}),
      },
    };
    writeSettings(next);
    return next;
  });
  ipcMain.handle("app:submitSupportTicket", async (_event, payload = {}) => {
    const saved = readSettings();
    const serverUrl = normalizeServerUrl(payload.serverUrl || saved.serverUrl);
    const schoolCode = String(payload.schoolCode || saved.schoolCode || "").trim();
    return postJson(`${serverUrl}/api/app/admin-desktop/support-tickets/`, {
      ...payload,
      school_code: schoolCode,
    });
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
  ipcMain.handle("lan:saveStudent", (_event, payload = {}) => lanServer.saveStudent(payload));
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
