const fs = require("fs");
const initSqlJs = require("sql.js");
const { dataPath } = require("./config.cjs");
const { decryptJson, encryptJson, newId, sha256 } = require("./security.cjs");

let SQL;
let db;
let encryptionSecret;
let dbFilePath;
let inTransaction = false;

function now() {
  return new Date().toISOString();
}

async function openDatabase() {
  if (db) return db;
  fs.mkdirSync(dataPath(), { recursive: true });
  SQL = await initSqlJs();
  dbFilePath = dataPath("schooldom-cbt.sqlite");
  if (fs.existsSync(dbFilePath)) {
    db = new SQL.Database(fs.readFileSync(dbFilePath));
  } else {
    db = new SQL.Database();
  }
  db.run(`
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS students (
      id TEXT PRIMARY KEY,
      student_id TEXT NOT NULL UNIQUE,
      full_name TEXT NOT NULL,
      class_name TEXT,
      encrypted_payload TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS exams (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      subject TEXT,
      duration_seconds INTEGER NOT NULL,
      starts_at TEXT,
      ends_at TEXT,
      pin_hash TEXT NOT NULL,
      instructions TEXT,
      encrypted_payload TEXT NOT NULL,
      synced_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      exam_id TEXT NOT NULL,
      student_id TEXT NOT NULL,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      ends_at TEXT NOT NULL,
      submitted_at TEXT,
      focus_loss_count INTEGER NOT NULL DEFAULT 0,
      malpractice_log TEXT NOT NULL DEFAULT '[]',
      encrypted_answers TEXT NOT NULL,
      score REAL,
      sync_status TEXT NOT NULL DEFAULT 'pending',
      updated_at TEXT NOT NULL,
      UNIQUE(exam_id, student_id)
    );
    CREATE TABLE IF NOT EXISTS activity_logs (
      id TEXT PRIMARY KEY,
      session_id TEXT,
      type TEXT NOT NULL,
      message TEXT NOT NULL,
      payload TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sync_queue (
      id TEXT PRIMARY KEY,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      endpoint TEXT NOT NULL,
      method TEXT NOT NULL,
      encrypted_payload TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
  `);
  encryptionSecret = getSetting("deviceSecret") || newId("secret");
  setSetting("deviceSecret", encryptionSecret);
  persist();
  return db;
}

function persist() {
  if (!db || !dbFilePath) return;
  fs.writeFileSync(dbFilePath, Buffer.from(db.export()));
}

function run(sql, params = []) {
  db.run(sql, params);
  if (!inTransaction) persist();
}

function all(sql, params = []) {
  const stmt = db.prepare(sql, params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

function get(sql, params = []) {
  return all(sql, params)[0] || null;
}

function scalar(sql, params = [], key = "value") {
  const row = get(sql, params);
  return row ? row[key] : undefined;
}

function transaction(callback) {
  db.run("BEGIN");
  inTransaction = true;
  try {
    const result = callback();
    inTransaction = false;
    db.run("COMMIT");
    persist();
    return result;
  } catch (error) {
    inTransaction = false;
    db.run("ROLLBACK");
    throw error;
  }
}

function getSetting(key) {
  return scalar("SELECT value FROM settings WHERE key = ?", [key], "value") || "";
}

function setSetting(key, value) {
  run(
    "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
    [key, String(value ?? ""), now()]
  );
}

function getOrCreateSetting(key, prefix) {
  const existing = getSetting(key);
  if (existing) return existing;
  const value = newId(prefix);
  setSetting(key, value);
  return value;
}

function getDeviceId() {
  return getOrCreateSetting("deviceId", "device");
}

function encrypted(value) {
  return encryptJson(value, encryptionSecret);
}

function decrypted(value, fallback) {
  return decryptJson(value, encryptionSecret, fallback);
}

function buildPackageId({ exams = [], students = [], packageMeta = {} }) {
  if (packageMeta.package_id) return String(packageMeta.package_id);
  return sha256(
    JSON.stringify({
      type: packageMeta.package_type || "schooldom_cbt_exam_package",
      version: packageMeta.package_version || 1,
      generated_at: packageMeta.generated_at || "",
      exams: exams.map((exam) => String(exam.id || exam.exam_id)).sort(),
      students: students.map((student) => String(student.student_id || student.admission_number || student.id)).sort(),
    })
  );
}

function lockActivePackage({ packageId, packageMeta = {}, exams = [], students = [] }) {
  const lockedAt = now();
  setSetting("activePackageId", packageId);
  setSetting("packageLockedAt", lockedAt);
  setSetting("packageGeneratedAt", packageMeta.generated_at || packageMeta.created_at || "");
  setSetting("packageSource", packageMeta.source || packageMeta.package_type || "cloud");
  logActivity("", "exam_package_locked", "Locked CBT package for offline exam delivery.", {
    packageId,
    exams: exams.length,
    students: students.length,
    generatedAt: packageMeta.generated_at || packageMeta.created_at || "",
  });
  return lockedAt;
}

function saveSyncSnapshot({ exams = [], students = [], packageMeta = {} }) {
  const packageId = buildPackageId({ exams, students, packageMeta });
  transaction(() => {
    for (const student of students) {
      run(
        `INSERT INTO students (id, student_id, full_name, class_name, encrypted_payload, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(student_id) DO UPDATE SET
           full_name = excluded.full_name,
           class_name = excluded.class_name,
           encrypted_payload = excluded.encrypted_payload,
           updated_at = excluded.updated_at`,
        [
          String(student.id || student.student_id),
          String(student.student_id || student.admission_number || student.id || "").trim(),
          String(student.full_name || student.name || student.email || "Student"),
          String(student.class_name || student.class_label || ""),
          encrypted(student),
          now(),
        ]
      );
    }
    for (const exam of exams) {
      const pin = String(exam.pin || exam.exam_pin || exam.access_pin || "");
      const offlinePinHash = String(exam.offline_pin_hash || exam.pin_sha256 || "").trim();
      const durationSeconds = Number(exam.duration_seconds || Number(exam.duration_minutes || exam.duration || 60) * 60);
      run(
        `INSERT INTO exams (id, title, subject, duration_seconds, starts_at, ends_at, pin_hash, instructions, encrypted_payload, synced_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           title = excluded.title,
           subject = excluded.subject,
           duration_seconds = excluded.duration_seconds,
           starts_at = excluded.starts_at,
           ends_at = excluded.ends_at,
           pin_hash = excluded.pin_hash,
           instructions = excluded.instructions,
           encrypted_payload = excluded.encrypted_payload,
           synced_at = excluded.synced_at`,
        [
          String(exam.id || exam.exam_id),
          String(exam.title || exam.name || "CBT Exam"),
          String(exam.subject || exam.subject_name || ""),
          Math.max(60, durationSeconds || 3600),
          exam.starts_at || exam.start_date || "",
          exam.ends_at || exam.end_date || "",
          offlinePinHash || (pin ? sha256(pin) : ""),
          String(exam.instructions || "Read every question carefully before submitting."),
          encrypted(exam),
          now(),
        ]
      );
    }
  });
  setSetting("lastSyncAt", now());
  lockActivePackage({ packageId, packageMeta, exams, students });
  return getAdminSnapshot();
}

function importExamPackage(packagePayload = {}) {
  const exams = packagePayload.exams || packagePayload.published_exams || packagePayload.data?.exams || [];
  const students = packagePayload.students || packagePayload.data?.students || [];
  if (!Array.isArray(exams) || !Array.isArray(students)) {
    throw new Error("Invalid CBT package. Expected exams and students arrays.");
  }
  const snapshot = saveSyncSnapshot({
    exams,
    students,
    packageMeta: {
      package_id: packagePayload.package_id,
      package_type: packagePayload.package_type,
      package_version: packagePayload.package_version,
      generated_at: packagePayload.generated_at || packagePayload.created_at || "",
      source: "file_import",
    },
  });
  logActivity("", "exam_package_imported", "Imported offline CBT exam package.", {
    exams: exams.length,
    students: students.length,
    source: packagePayload.generated_at || packagePayload.created_at || "",
  });
  return {
    success: true,
    imported: { exams: exams.length, students: students.length },
    snapshot,
  };
}

function saveLocalExam({ exam, students = [] } = {}) {
  if (!exam || !Array.isArray(exam.questions) || !exam.questions.length) {
    throw new Error("Local exam must include at least one question.");
  }
  const cleanedStudents = students
    .map((student, index) => {
      const studentId = String(student.student_id || student.id || "").trim();
      if (!studentId) return null;
      return {
        id: String(student.id || studentId),
        student_id: studentId,
        full_name: String(student.full_name || student.name || `Local Student ${index + 1}`),
        class_name: String(student.class_name || student.class || ""),
        source: "local",
      };
    })
    .filter(Boolean);

  if (!cleanedStudents.length) {
    throw new Error("Add at least one local student ID before creating the exam.");
  }

  const localExam = {
    ...exam,
    id: String(exam.id || newId("local_exam")),
    source: "local",
    created_at: now(),
  };
  const snapshot = saveSyncSnapshot({
    exams: [localExam],
    students: cleanedStudents,
    packageMeta: {
      package_id: localExam.id,
      package_type: "schooldom_cbt_local_exam_package",
      generated_at: localExam.created_at,
      source: "local_exam",
    },
  });
  logActivity("", "local_exam_created", "Created CBT exam from local files.", {
    examId: localExam.id,
    title: localExam.title,
    questions: localExam.questions.length,
    students: cleanedStudents.length,
    files: localExam.source_files?.length || 0,
  });
  return {
    success: true,
    imported: { exams: 1, students: cleanedStudents.length, questions: localExam.questions.length },
    exam: { id: localExam.id, title: localExam.title },
    snapshot,
  };
}

function buildResultsPackage() {
  const results = getPendingSyncItems()
    .filter((item) => item.entity_type === "result")
    .map((item) => ({
      package_item_id: item.id,
      entity_id: item.entity_id,
      attempts: item.attempts,
      last_error: item.last_error || "",
      created_at: item.created_at,
      payload: item.payload,
      sync_envelope: item.sync_envelope,
    }));
  return {
    package_type: "schooldom_cbt_results",
    package_version: 1,
    generated_at: now(),
    results,
    summary: {
      pending_results: results.length,
      package_id: getSetting("activePackageId") || "",
      device_id: getDeviceId(),
    },
  };
}

function listAvailableExams() {
  return all("SELECT id, title, subject, duration_seconds, starts_at, ends_at, instructions, synced_at FROM exams ORDER BY synced_at DESC");
}

function getExamPayload(examId) {
  const row = get("SELECT * FROM exams WHERE id = ?", [examId]);
  if (!row) return null;
  return { ...row, payload: decrypted(row.encrypted_payload, {}) };
}

function validateStudentLogin({ studentId, pin }) {
  const student = get("SELECT * FROM students WHERE lower(student_id) = lower(?)", [String(studentId || "").trim()]);
  if (!student) return { success: false, message: "Student ID was not found on this CBT device." };
  const exams = all("SELECT * FROM exams WHERE pin_hash = ? ORDER BY synced_at DESC", [sha256(pin)]);
  const unavailablePin = get("SELECT id FROM exams WHERE pin_hash = '' LIMIT 1");
  if (!exams.length && unavailablePin) {
    return { success: false, message: "This exam package does not include offline PIN validation. Enter the published PIN during sync." };
  }
  if (!exams.length) return { success: false, message: "Invalid exam PIN." };
  const exam = exams[0];
  const session = startOrResumeSession({ examId: exam.id, studentId: student.student_id });
  return {
    success: true,
    student: { id: student.id, student_id: student.student_id, full_name: student.full_name, class_name: student.class_name },
    exam: { id: exam.id, title: exam.title, subject: exam.subject, duration_seconds: exam.duration_seconds, instructions: exam.instructions },
    session,
  };
}

function startOrResumeSession({ examId, studentId }) {
  const existing = get("SELECT * FROM sessions WHERE exam_id = ? AND student_id = ?", [examId, studentId]);
  if (existing) return serializeSession(existing);
  const exam = get("SELECT duration_seconds FROM exams WHERE id = ?", [examId]);
  const start = new Date();
  const end = new Date(start.getTime() + Number(exam?.duration_seconds || 3600) * 1000);
  const id = newId("session");
  run(
    "INSERT INTO sessions (id, exam_id, student_id, status, started_at, ends_at, encrypted_answers, updated_at) VALUES (?, ?, ?, 'in_progress', ?, ?, ?, ?)",
    [id, examId, studentId, start.toISOString(), end.toISOString(), encrypted({}), now()]
  );
  logActivity(id, "session_started", "Student started or resumed an exam.", { examId, studentId });
  return serializeSession(get("SELECT * FROM sessions WHERE id = ?", [id]));
}

function saveAnswers({ sessionId, answers }) {
  const session = get("SELECT * FROM sessions WHERE id = ?", [sessionId]);
  if (!session || session.status === "submitted") return serializeSession(session);
  run("UPDATE sessions SET encrypted_answers = ?, updated_at = ? WHERE id = ?", [encrypted(answers || {}), now(), sessionId]);
  return serializeSession(get("SELECT * FROM sessions WHERE id = ?", [sessionId]));
}

function logFocusLoss({ sessionId, reason }) {
  const session = get("SELECT * FROM sessions WHERE id = ?", [sessionId]);
  if (!session) return null;
  const log = decrypted(session.malpractice_log, []);
  log.push({ at: now(), reason: reason || "focus_lost" });
  run("UPDATE sessions SET focus_loss_count = focus_loss_count + 1, malpractice_log = ?, updated_at = ? WHERE id = ?", [encrypted(log), now(), sessionId]);
  logActivity(sessionId, "focus_loss", "Student left secure exam focus.", { reason });
  return serializeSession(get("SELECT * FROM sessions WHERE id = ?", [sessionId]));
}

function submitSession(sessionId, cause = "student_submit") {
  const session = get("SELECT * FROM sessions WHERE id = ?", [sessionId]);
  if (!session) return { success: false, message: "Exam session was not found." };
  if (session.status !== "submitted") {
    run("UPDATE sessions SET status = 'submitted', submitted_at = ?, sync_status = 'pending', updated_at = ? WHERE id = ?", [now(), now(), sessionId]);
    logActivity(sessionId, "session_submitted", "Exam was submitted locally.", { cause });
    queueResult(sessionId, cause);
  }
  return { success: true, session: serializeSession(get("SELECT * FROM sessions WHERE id = ?", [sessionId])) };
}

function queueResult(sessionId, cause = "student_submit") {
  const session = serializeSession(get("SELECT * FROM sessions WHERE id = ?", [sessionId]));
  if (!session) return;
  const auditLogs = getActivityLogsForSession(sessionId);
  const payload = {
    session_id: session.id,
    exam_id: session.exam_id,
    student_id: session.student_id,
    answers: session.answers,
    started_at: session.started_at,
    submitted_at: session.submitted_at,
    focus_loss_count: session.focus_loss_count,
    malpractice_log: session.malpractice_log,
    audit_logs: auditLogs,
    cause,
  };
  run(
    "INSERT INTO sync_queue (id, entity_type, entity_id, endpoint, method, encrypted_payload, created_at, updated_at) VALUES (?, 'result', ?, '/api/exams/cbt/offline-results/', 'POST', ?, ?, ?)",
    [newId("sync"), sessionId, encrypted(payload), now(), now()]
  );
}

function getPendingSyncItems() {
  return all("SELECT * FROM sync_queue ORDER BY created_at ASC").map((row) => ({
    ...row,
    payload: decrypted(row.encrypted_payload, {}),
  })).map((item) => ({
    ...item,
    sync_envelope: buildSyncEnvelope(item),
  }));
}

function buildSyncEnvelope(item) {
  const packageId = getSetting("activePackageId") || "";
  const packageLockedAt = getSetting("packageLockedAt") || "";
  const payload = item.payload || {};
  const auditLogs = Array.isArray(payload.audit_logs) ? payload.audit_logs : getActivityLogsForSession(item.entity_id);
  const body = {
    envelope_type: "schooldom_cbt_result_sync",
    envelope_version: 1,
    sync_id: item.id,
    entity_type: item.entity_type,
    entity_id: item.entity_id,
    device_id: getDeviceId(),
    package_id: packageId,
    package_locked_at: packageLockedAt,
    created_at: item.created_at,
    attempts: item.attempts,
    payload: {
      ...payload,
      audit_logs: auditLogs,
    },
  };
  return {
    ...body,
    checksum: sha256(JSON.stringify({
      sync_id: body.sync_id,
      device_id: body.device_id,
      package_id: body.package_id,
      payload: body.payload,
    })),
  };
}

function markSyncSuccess(queueId, entityId) {
  run("DELETE FROM sync_queue WHERE id = ?", [queueId]);
  run("UPDATE sessions SET sync_status = 'synced', updated_at = ? WHERE id = ?", [now(), entityId]);
}

function markSyncFailure(queueId, message) {
  run("UPDATE sync_queue SET attempts = attempts + 1, last_error = ?, updated_at = ? WHERE id = ?", [String(message || "Sync failed."), now(), queueId]);
}

function getAdminSnapshot() {
  const exams = listAvailableExams();
  const students = all("SELECT id, student_id, full_name, class_name, updated_at FROM students ORDER BY full_name");
  const sessions = all("SELECT * FROM sessions ORDER BY updated_at DESC").map(serializeSession);
  const queueCount = scalar("SELECT COUNT(*) AS total FROM sync_queue", [], "total") || 0;
  return {
    settings: {
      cloudUrl: getSetting("cloudUrl") || "",
      lastSyncAt: getSetting("lastSyncAt") || "",
      activePackageId: getSetting("activePackageId") || "",
      packageLockedAt: getSetting("packageLockedAt") || "",
      packageGeneratedAt: getSetting("packageGeneratedAt") || "",
      packageSource: getSetting("packageSource") || "",
      deviceId: getDeviceId(),
      lanName: getSetting("lanName") || "School CBT Room",
      lanInstructions: getSetting("lanInstructions") || "Admin will set Wi-Fi, hotspot, or lab network access manually.",
    },
    exams,
    students,
    sessions,
    queueCount,
  };
}

function saveOfflineSettings(settings = {}) {
  if ("lanName" in settings) setSetting("lanName", settings.lanName);
  if ("lanInstructions" in settings) setSetting("lanInstructions", settings.lanInstructions);
  if ("cloudUrl" in settings) setSetting("cloudUrl", settings.cloudUrl);
  return getAdminSnapshot();
}

function getActivityLogs(limit = 100) {
  return all("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?", [limit]);
}

function getActivityLogsForSession(sessionId) {
  return all("SELECT * FROM activity_logs WHERE session_id = ? ORDER BY created_at ASC", [sessionId]).map((row) => ({
    ...row,
    payload: (() => {
      try {
        return JSON.parse(row.payload || "{}");
      } catch {
        return {};
      }
    })(),
  }));
}

function logActivity(sessionId, type, message, payload = {}) {
  run("INSERT INTO activity_logs (id, session_id, type, message, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)", [
    newId("log"),
    sessionId || "",
    type,
    message,
    JSON.stringify(payload),
    now(),
  ]);
}

function serializeSession(row) {
  if (!row) return null;
  return {
    ...row,
    answers: decrypted(row.encrypted_answers, {}),
    malpractice_log: decrypted(row.malpractice_log, []),
  };
}

function cleanupSyncedCache() {
  const before = scalar("SELECT COUNT(*) AS total FROM sessions", [], "total") || 0;
  run("DELETE FROM sessions WHERE sync_status = 'synced' AND status = 'submitted'");
  const after = scalar("SELECT COUNT(*) AS total FROM sessions", [], "total") || 0;
  const removed = before - after;
  logActivity("", "cache_cleanup", "Cleaned up synced local exam sessions.", { removed });
  return { removed };
}

module.exports = {
  cleanupSyncedCache,
  getActivityLogs,
  getAdminSnapshot,
  getExamPayload,
  getPendingSyncItems,
  getSetting,
  importExamPackage,
  listAvailableExams,
  logFocusLoss,
  markSyncFailure,
  markSyncSuccess,
  openDatabase,
  saveAnswers,
  saveLocalExam,
  saveOfflineSettings,
  saveSyncSnapshot,
  buildResultsPackage,
  setSetting,
  submitSession,
  validateStudentLogin,
};
