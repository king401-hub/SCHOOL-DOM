const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { dataPath } = require("./config.cjs");

const PORT = 4785;
let server;

function now() {
  return new Date().toISOString();
}

function newId(prefix) {
  return `${prefix}_${crypto.randomBytes(8).toString("hex")}`;
}

function sha256(value) {
  return crypto.createHash("sha256").update(String(value || "")).digest("hex");
}

function storePath() {
  return dataPath("lan-exam-room.json");
}

function defaultStore() {
  return { exams: [], students: [], sessions: [], updated_at: now() };
}

function readStore() {
  try {
    return { ...defaultStore(), ...JSON.parse(fs.readFileSync(storePath(), "utf8")) };
  } catch {
    return defaultStore();
  }
}

function writeStore(store) {
  fs.mkdirSync(path.dirname(storePath()), { recursive: true });
  fs.writeFileSync(storePath(), JSON.stringify({ ...store, updated_at: now() }, null, 2), "utf8");
}

function localAddresses() {
  const addresses = [];
  const nets = os.networkInterfaces();
  for (const entries of Object.values(nets)) {
    for (const entry of entries || []) {
      if (entry.family === "IPv4" && !entry.internal) {
        addresses.push(entry.address);
      }
    }
  }
  return addresses;
}

function normalizeQuestions(text) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    const rows = Array.isArray(parsed) ? parsed : parsed.questions || parsed.items || [];
    return rows.map((question, index) => ({
      id: String(question.id || question.question_id || index + 1),
      number: index + 1,
      text: String(question.text || question.question || question.prompt || `Question ${index + 1}`),
      type: question.type || question.question_type || (question.options?.length ? "multiple_choice" : "theory"),
      options: question.options || question.choices || [],
      marks: Number(question.marks || question.score || 1),
    }));
  } catch {
    return raw
      .split(/\n\s*\n/)
      .map((block) => block.trim())
      .filter(Boolean)
      .map((block, index) => ({
        id: String(index + 1),
        number: index + 1,
        text: block,
        type: "theory",
        options: [],
        marks: 1,
      }));
  }
}

function parseStudents(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [studentId, fullName, className] = line.split(",").map((part) => String(part || "").trim());
      return {
        id: studentId || `STUDENT${index + 1}`,
        student_id: studentId || `STUDENT${index + 1}`,
        full_name: fullName || studentId || `Student ${index + 1}`,
        class_name: className || "",
      };
    });
}

function publishExam(payload = {}) {
  const questions = normalizeQuestions(payload.questionsText);
  if (!questions.length) throw new Error("Add at least one question before publishing.");
  const students = parseStudents(payload.studentsText);
  if (!students.length) throw new Error("Add at least one student before publishing.");
  const exam = {
    id: newId("lan_exam"),
    title: String(payload.title || "Offline CBT Exam").trim(),
    subject: String(payload.subject || "").trim(),
    duration_seconds: Math.max(60, Number(payload.durationMinutes || 60) * 60),
    pin_hash: sha256(payload.pin),
    instructions: String(payload.instructions || "Answer all questions."),
    questions,
    published_at: now(),
  };
  const store = readStore();
  store.exams = [exam, ...store.exams.filter((item) => item.id !== exam.id)];
  store.students = students;
  writeStore(store);
  return snapshot();
}

function snapshot() {
  const store = readStore();
  return {
    ...store,
    port: PORT,
    addresses: localAddresses(),
    urls: localAddresses().map((address) => `http://${address}:${PORT}`),
    running: Boolean(server?.listening),
  };
}

function publicExam(exam) {
  return {
    id: exam.id,
    title: exam.title,
    subject: exam.subject,
    duration_seconds: exam.duration_seconds,
    instructions: exam.instructions,
  };
}

function sendJson(res, status, payload) {
  res.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json",
  });
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 5_000_000) req.destroy();
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

async function handleRequest(req, res) {
  if (req.method === "OPTIONS") return sendJson(res, 200, { ok: true });
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const store = readStore();

  try {
    if (req.method === "GET" && url.pathname === "/health") {
      return sendJson(res, 200, { ok: true, app: "SchoolDom Admin LAN", ...snapshot() });
    }
    if (req.method === "GET" && url.pathname === "/api/exams") {
      return sendJson(res, 200, { exams: store.exams.map(publicExam) });
    }
    if (req.method === "POST" && url.pathname === "/api/login") {
      const body = await readBody(req);
      const student = store.students.find((item) => item.student_id.toLowerCase() === String(body.studentId || "").trim().toLowerCase());
      const exam = store.exams.find((item) => item.pin_hash === sha256(body.pin));
      if (!student) return sendJson(res, 404, { success: false, message: "Student ID was not found on the admin server." });
      if (!exam) return sendJson(res, 403, { success: false, message: "Invalid exam PIN." });
      let session = store.sessions.find((item) => item.exam_id === exam.id && item.student_id === student.student_id);
      if (!session) {
        const started = Date.now();
        session = {
          id: newId("lan_session"),
          exam_id: exam.id,
          student_id: student.student_id,
          status: "in_progress",
          started_at: new Date(started).toISOString(),
          ends_at: new Date(started + exam.duration_seconds * 1000).toISOString(),
          answers: {},
          malpractice_log: [],
          submitted_at: "",
          updated_at: now(),
        };
        store.sessions.push(session);
        writeStore(store);
      }
      return sendJson(res, 200, { success: true, student, exam: publicExam(exam), session });
    }
    const examMatch = url.pathname.match(/^\/api\/exams\/([^/]+)$/);
    if (req.method === "GET" && examMatch) {
      const exam = store.exams.find((item) => item.id === decodeURIComponent(examMatch[1]));
      if (!exam) return sendJson(res, 404, { success: false, message: "Exam not found." });
      return sendJson(res, 200, { success: true, exam: { ...publicExam(exam), payload: { questions: exam.questions } } });
    }
    const saveMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)\/answers$/);
    if (req.method === "POST" && saveMatch) {
      const body = await readBody(req);
      const session = store.sessions.find((item) => item.id === decodeURIComponent(saveMatch[1]));
      if (!session) return sendJson(res, 404, { success: false, message: "Session not found." });
      session.answers = body.answers || {};
      session.updated_at = now();
      writeStore(store);
      return sendJson(res, 200, { success: true, session });
    }
    const submitMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)\/submit$/);
    if (req.method === "POST" && submitMatch) {
      const body = await readBody(req);
      const session = store.sessions.find((item) => item.id === decodeURIComponent(submitMatch[1]));
      if (!session) return sendJson(res, 404, { success: false, message: "Session not found." });
      session.answers = body.answers || session.answers || {};
      session.status = "submitted";
      session.submitted_at = now();
      session.updated_at = now();
      writeStore(store);
      return sendJson(res, 200, { success: true, session });
    }
    const focusMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)\/focus-loss$/);
    if (req.method === "POST" && focusMatch) {
      const body = await readBody(req);
      const session = store.sessions.find((item) => item.id === decodeURIComponent(focusMatch[1]));
      if (!session) return sendJson(res, 404, { success: false, message: "Session not found." });
      session.malpractice_log = [...(session.malpractice_log || []), { at: now(), reason: body.reason || "focus_lost" }];
      session.updated_at = now();
      writeStore(store);
      return sendJson(res, 200, { success: true, session });
    }
    return sendJson(res, 404, { success: false, message: "Not found." });
  } catch (error) {
    return sendJson(res, 500, { success: false, message: error.message || "LAN server error." });
  }
}

function startServer() {
  if (server?.listening) return snapshot();
  server = http.createServer(handleRequest);
  server.listen(PORT, "0.0.0.0");
  return snapshot();
}

function stopServer() {
  if (server?.listening) server.close();
  return snapshot();
}

module.exports = {
  publishExam,
  snapshot,
  startServer,
  stopServer,
};
