const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { APP_NAME, DEFAULT_CLOUD_URL } = require("./config.cjs");
const db = require("./db.cjs");
const { discoverAdminRooms } = require("./discovery.cjs");
const { newId } = require("./security.cjs");
const { pushPendingResults, syncFromCloud } = require("./syncService.cjs");

const isDev = !app.isPackaged;
let mainWindow;

const READABLE_EXTENSIONS = new Set([".json", ".txt", ".md", ".csv", ".docx"]);

function normalizeCloudUrl(value) {
  return String(value || DEFAULT_CLOUD_URL).trim().replace(/\/+$/, "") || DEFAULT_CLOUD_URL;
}

function compareVersions(left, right) {
  const a = String(left || "0").split(".").map((part) => Number.parseInt(part, 10) || 0);
  const b = String(right || "0").split(".").map((part) => Number.parseInt(part, 10) || 0);
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    if ((a[index] || 0) > (b[index] || 0)) return 1;
    if ((a[index] || 0) < (b[index] || 0)) return -1;
  }
  return 0;
}

async function checkForDesktopUpdate(cloudUrl) {
  const baseUrl = normalizeCloudUrl(cloudUrl);
  const currentVersion = app.getVersion();
  const fallbackDownloadUrl = `${baseUrl}/app/download/student-cbt/`;

  let payload = {};
  try {
    const response = await fetch(`${baseUrl}/app/download/student-cbt/version/`, {
      headers: { Accept: "application/json" },
    });
    payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || `Update check failed (${response.status}).`);
    }
  } catch (error) {
    return {
      currentVersion,
      latestVersion: currentVersion,
      updateAvailable: false,
      downloadUrl: fallbackDownloadUrl,
      error: error.message || "Could not check for updates.",
    };
  }

  const latestVersion = String(payload.version || currentVersion);
  return {
    currentVersion,
    latestVersion,
    updateAvailable: compareVersions(latestVersion, currentVersion) > 0,
    available: Boolean(payload.available),
    downloadUrl: payload.download_url || fallbackDownloadUrl,
    filename: payload.filename || "SchoolDomCBT.exe",
    sizeBytes: Number(payload.size_bytes || 0),
  };
}

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
    appVersion: app.getVersion(),
    cloudUrl: db.getSetting("cloudUrl") || DEFAULT_CLOUD_URL,
    snapshot: db.getAdminSnapshot(),
  }));
  ipcMain.handle("app:checkForUpdates", async (_event, payload = {}) => checkForDesktopUpdate(payload.cloudUrl));
  ipcMain.handle("app:discoverRooms", async () => discoverAdminRooms());
  ipcMain.handle("app:downloadUpdate", async (_event, payload = {}) => {
    const update = payload.downloadUrl
      ? { downloadUrl: payload.downloadUrl }
      : await checkForDesktopUpdate(payload.cloudUrl);
    await shell.openExternal(update.downloadUrl || `${normalizeCloudUrl(payload.cloudUrl)}/app/download/student-cbt/`);
    return { success: true, downloadUrl: update.downloadUrl };
  });

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
  ipcMain.handle("admin:importLocalExam", async (_event, payload = {}) => {
    const mode = payload.mode === "folder" ? "folder" : "files";
    const result = await dialog.showOpenDialog(mainWindow, {
      title: mode === "folder" ? "Select folder with local CBT questions" : "Select local CBT question files",
      properties: mode === "folder" ? ["openDirectory"] : ["openFile", "multiSelections"],
      filters: mode === "folder" ? undefined : [
        { name: "Supported Question Files", extensions: ["json", "txt", "md", "csv", "docx"] },
        { name: "All Files", extensions: ["*"] },
      ],
    });
    if (result.canceled || !result.filePaths.length) {
      return { success: false, canceled: true };
    }
    const filePaths = mode === "folder" ? collectFiles(result.filePaths[0]) : result.filePaths;
    const exam = buildLocalExamFromFiles(filePaths, payload);
    return db.saveLocalExam({ exam, students: parseLocalStudents(payload.studentsText) });
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
    mainWindow?.setContentProtection(true);
    mainWindow?.setFullScreen(true);
    mainWindow?.setAlwaysOnTop(true, "screen-saver");
    return { success: true };
  });
  ipcMain.handle("window:exitFullscreen", () => {
    mainWindow?.setContentProtection(false);
    mainWindow?.setAlwaysOnTop(false);
    mainWindow?.setFullScreen(false);
    return { success: true };
  });
}

function collectFiles(folderPath) {
  const files = [];
  const stack = [folderPath];
  while (stack.length) {
    const current = stack.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile()) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

function parseLocalStudents(studentsText = "") {
  return String(studentsText || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [studentId, fullName, className] = line.split(",").map((part) => String(part || "").trim());
      return {
        id: studentId,
        student_id: studentId,
        full_name: fullName || studentId,
        class_name: className || "",
      };
    });
}

function buildLocalExamFromFiles(filePaths, payload = {}) {
  const sourceFiles = [];
  const questions = [];
  for (const filePath of filePaths) {
    const stat = fs.statSync(filePath);
    const extension = path.extname(filePath).toLowerCase();
    const sourceFile = {
      name: path.basename(filePath),
      path: filePath,
      extension: extension.replace(".", "") || "file",
      size: stat.size,
    };
    sourceFiles.push(sourceFile);
    const parsedQuestions = parseQuestionsFromFile(filePath, sourceFile);
    questions.push(...parsedQuestions);
  }
  if (!questions.length && sourceFiles.length) {
    questions.push(...sourceFiles.map((file, index) => ({
      id: newId("local_q"),
      number: index + 1,
      type: "theory",
      text: `Review the local exam material "${file.name}" and type your answer.`,
      options: [],
      marks: 1,
      source_file: file,
    })));
  }
  if (!questions.length) {
    throw new Error("No supported local question files were found.");
  }
  return {
    id: newId("local_exam"),
    title: String(payload.title || "Local CBT Exam").trim(),
    subject: String(payload.subject || "Local Subject").trim(),
    duration_minutes: Number(payload.durationMinutes || 60),
    duration_seconds: Math.max(60, Number(payload.durationMinutes || 60) * 60),
    pin: String(payload.pin || "").trim(),
    instructions: String(payload.instructions || "Answer all questions. This exam was created locally on this device."),
    questions: questions.map((question, index) => ({ ...question, number: index + 1 })),
    source_files: sourceFiles,
  };
}

function parseQuestionsFromFile(filePath, sourceFile) {
  const extension = path.extname(filePath).toLowerCase();
  try {
    if (extension === ".json") return parseJsonQuestions(fs.readFileSync(filePath, "utf8"), sourceFile);
    if (extension === ".csv") return parseCsvQuestions(fs.readFileSync(filePath, "utf8"), sourceFile);
    if (extension === ".txt" || extension === ".md") return parseTextQuestions(fs.readFileSync(filePath, "utf8"), sourceFile);
    if (extension === ".docx") return parseTextQuestions(extractDocxText(filePath), sourceFile);
  } catch (error) {
    return [{
      id: newId("local_q"),
      type: "theory",
      text: `The file "${sourceFile.name}" could not be parsed automatically. Admin note: ${error.message}`,
      options: [],
      marks: 1,
      source_file: sourceFile,
    }];
  }
  return [{
    id: newId("local_q"),
    type: "theory",
    text: `Local exam material attached: ${sourceFile.name}`,
    options: [],
    marks: 1,
    source_file: sourceFile,
  }];
}

function parseJsonQuestions(raw, sourceFile) {
  const payload = JSON.parse(raw);
  const questions = payload.questions || payload.items || payload.question_rows || (Array.isArray(payload) ? payload : []);
  return questions.map((question, index) => normalizeLocalQuestion(question, sourceFile, index));
}

function parseCsvQuestions(raw, sourceFile) {
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return [];
  const headers = splitCsvLine(lines[0]).map((item) => item.toLowerCase().replace(/\s+/g, "_"));
  return lines.slice(1).map((line, index) => {
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((header, headerIndex) => {
      row[header] = values[headerIndex] || "";
    });
    return normalizeLocalQuestion(row, sourceFile, index);
  });
}

function splitCsvLine(line) {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && line[index + 1] === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function parseTextQuestions(raw, sourceFile) {
  const text = String(raw || "").replace(/\r\n/g, "\n").trim();
  if (!text) return [];
  const blocks = text
    .split(/\n\s*\n|(?:^|\n)\s*(?:Q(?:uestion)?\.?\s*)?\d+[\).:-]\s*/i)
    .map((block) => block.trim())
    .filter((block) => block.length > 5);
  const questionBlocks = blocks.length > 1 ? blocks : [text];
  return questionBlocks.map((block, index) => parseQuestionBlock(block, sourceFile, index));
}

function parseQuestionBlock(block, sourceFile, index) {
  const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
  const optionLines = lines.filter((line) => /^[A-D][\).:-]\s+/i.test(line));
  const answerLine = lines.find((line) => /^answer\s*[:=-]/i.test(line));
  const questionLines = lines.filter((line) => !/^[A-D][\).:-]\s+/i.test(line) && !/^answer\s*[:=-]/i.test(line));
  if (optionLines.length >= 2) {
    return {
      id: newId("local_q"),
      type: "multiple_choice",
      text: questionLines.join(" "),
      options: optionLines.map((line) => line.replace(/^[A-D][\).:-]\s+/i, "")),
      answer: answerLine ? answerLine.replace(/^answer\s*[:=-]\s*/i, "") : "",
      marks: 1,
      source_file: sourceFile,
    };
  }
  return {
    id: newId("local_q"),
    type: "theory",
    text: questionLines.join(" ") || block,
    options: [],
    marks: 1,
    source_file: sourceFile,
    local_index: index + 1,
  };
}

function normalizeLocalQuestion(question, sourceFile, index) {
  const options = Array.isArray(question.options)
    ? question.options
    : String(question.options || question.choices || "")
      .split(/[|;]/)
      .map((item) => item.trim())
      .filter(Boolean);
  return {
    id: String(question.id || question.question_id || newId("local_q")),
    type: String(question.type || question.question_type || (options.length ? "multiple_choice" : "theory")),
    text: String(question.text || question.question || question.prompt || `Question ${index + 1}`),
    options,
    answer: question.answer || question.correct_answer || "",
    marks: Number(question.marks || question.score || 1),
    source_file: sourceFile,
  };
}

function extractDocxText(filePath) {
  const buffer = fs.readFileSync(filePath);
  const entries = unzipEntries(buffer);
  const documentXml = entries["word/document.xml"];
  if (!documentXml) return "";
  return documentXml
    .toString("utf8")
    .replace(/<w:tab\/>/g, " ")
    .replace(/<\/w:p>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .trim();
}

function unzipEntries(buffer) {
  const entries = {};
  let offset = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (offset < 0) throw new Error("Invalid DOCX file.");
  const centralDirectoryOffset = buffer.readUInt32LE(offset + 16);
  let pointer = centralDirectoryOffset;
  while (pointer < offset && buffer.readUInt32LE(pointer) === 0x02014b50) {
    const method = buffer.readUInt16LE(pointer + 10);
    const compressedSize = buffer.readUInt32LE(pointer + 20);
    const fileNameLength = buffer.readUInt16LE(pointer + 28);
    const extraLength = buffer.readUInt16LE(pointer + 30);
    const commentLength = buffer.readUInt16LE(pointer + 32);
    const localHeaderOffset = buffer.readUInt32LE(pointer + 42);
    const fileName = buffer.subarray(pointer + 46, pointer + 46 + fileNameLength).toString("utf8");
    const localNameLength = buffer.readUInt16LE(localHeaderOffset + 26);
    const localExtraLength = buffer.readUInt16LE(localHeaderOffset + 28);
    const dataStart = localHeaderOffset + 30 + localNameLength + localExtraLength;
    const compressed = buffer.subarray(dataStart, dataStart + compressedSize);
    if (method === 0) entries[fileName] = compressed;
    if (method === 8) entries[fileName] = zlib.inflateRawSync(compressed);
    pointer += 46 + fileNameLength + extraLength + commentLength;
  }
  return entries;
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
