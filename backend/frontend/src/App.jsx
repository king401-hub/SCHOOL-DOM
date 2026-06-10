import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Signin from "./SignIn";
import LandingPage from "./LandingPage";
import ResourceCenter from "./ResourceCenter";
import FAQPage from "./FAQPage";
import PrivacyPolicyPage from "./PrivacyPolicyPage";
import PricingPage from "./PricingPage";
import { AttendanceModule, TeacherQRCodeAttendancePage } from "./components/Attendance";
import ExamCBT from "./components/ExamCBT/ExamCBT";
import ExamsList from "./components/ExamCBT/ExamsList";
import ExamResult from "./components/ExamCBT/ExamResult";
import FormattedTextarea from "./components/FormattedTextarea";
import RichQuizText from "./components/RichQuizText";
import {
  SESSION_KEY,
  LEGACY_SESSION_KEY,
  UI_THEME_KEY,
  PENDING_AUTH_REDIRECT_KEY,
  API_BASE_URL,
  ID_CARD_VERIFY_PATH,
  PUBLIC_ROUTES,
  AUTH_ROUTES,
  STUDENT_POLL_INTERVAL_MS,
  TEACHER_POLL_INTERVAL_MS,
  DEFAULT_POLL_INTERVAL_MS,
  MESSAGE_POLL_INTERVAL_MS,
  TEACHER_ATTENDANCE_PREFIX,
  ADMIN_ROUTES,
  ACCOUNTANT_ROUTES,
  ADMIN_ROUTE_SET,
  ADMIN_ROUTE_REDIRECTS,
  ADMIN_ENDPOINTS,
  STUDENT_ROUTES,
  STUDENT_ROUTE_SET,
  RECOMMENDED_SUBJECT_GROUPS,
} from "./appConstants";
import {
  MultiSelectBox,
  normalizePath,
  isTeacherAttendanceScanPath,
  isStudentExamPath,
  getTeacherAttendanceToken,
  readStoredSession,
  clearStoredSession,
  writeStoredSession,
  readStoredTheme,
  refreshAccessToken,
  isFileLike,
  payloadContainsFile,
  buildFormData,
  formatApiError,
  requestJson,
  SCHOOL_DATA_MUTATED_EVENT,
  fetchDashboardSnapshot,
  postJson,
  copyToClipboard,
  formatDate,
  userDisplayName,
  userInitials,
  resolveSchoolBrand,
  SchoolBrand,
  roleLabel,
  BellIcon,
  FilterIcon,
  PaintbrushIcon,
  ThemeModeIcon,
  DashboardIcon,
  MetricCard,
  ScreenState,
  OFFLINE_DRAFTS_KEY,
  OFFLINE_EXAM_CREATE_QUEUE_KEY,
  readOfflineDrafts,
  writeOfflineDrafts,
  readOfflineExamCreateQueue,
  writeOfflineExamCreateQueue,
  queueOfflineExamCreate,
  MessageInboxPanel,
  GlobalNotificationBell,
  GlobalHomeButton,
  StudentOfflineExamPage,
} from "./AppShared";
import { TeacherExamManager, TeacherExamBuilder, TeacherPastExamsPanel, ClassMessageComposer } from "./TeacherExamPanels";
const AdminExpenseTrackerScreen = lazy(() => import("./ExpenseTracker"));
const lazyAdminScreen = (exportName) =>
  lazy(() => import("./AdminScreens").then((module) => ({ default: module[exportName] })));

const IdCardVerificationPage = lazyAdminScreen("IdCardVerificationPage");
const AdminDashboardScreen = lazyAdminScreen("AdminDashboardScreen");
const AdminPerformanceHeatmapScreen = lazyAdminScreen("AdminPerformanceHeatmapScreen");
const AdminFinanceScreen = lazyAdminScreen("AdminFinanceScreen");
const AdminExamResultsScreen = lazyAdminScreen("AdminExamResultsScreen");
const AdminResultsScreen = lazyAdminScreen("AdminResultsScreen");
const AdminTableScreen = lazyAdminScreen("AdminTableScreen");
const AdminClassesScreen = lazyAdminScreen("AdminClassesScreen");
const AdminHRPayrollScreen = lazyAdminScreen("AdminHRPayrollScreen");
const AdminNonTeachingStaffScreen = lazyAdminScreen("AdminNonTeachingStaffScreen");
const AdminHRActivityScreen = lazyAdminScreen("AdminHRActivityScreen");
const AdminIdCardsScreen = lazyAdminScreen("AdminIdCardsScreen");
const AdminDocumentsScreen = lazyAdminScreen("AdminDocumentsScreen");
const AdminSettingsScreen = lazyAdminScreen("AdminSettingsScreen");
const AdminStudentsScreen = lazyAdminScreen("AdminStudentsScreen");
const AdminTeachersScreen = lazyAdminScreen("AdminTeachersScreen");
const AdminEnrollmentsScreen = lazyAdminScreen("AdminEnrollmentsScreen");
const AdminMessagesScreen = lazyAdminScreen("AdminMessagesScreen");
const AdminDatabaseImportScreen = lazyAdminScreen("AdminDatabaseImportScreen");

const NAIRA_SYMBOL = "\u20A6";
const DAILY_PERSONAL_QUESTION_LIMIT = 20;
const ADMIN_ACTIVITY_LOG_KEY = "schooldom.admin_activity_notifications";
const STUDENT_CBT_DESKTOP_PATH = "/student-cbt";

function isMobileQuizViewport() {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(max-width: 900px) and (pointer: coarse)").matches;
}

async function requestLandscapeForPersonalQuiz() {
  if (!isMobileQuizViewport()) return;
  try {
    await window.screen?.orientation?.lock?.("landscape");
  } catch {
    // Mobile browsers may only allow orientation lock for installed/fullscreen apps.
  }
}

function collectAttendanceDeviceInfo() {
  const screenSize = window.screen ? `${window.screen.width}x${window.screen.height}` : "unknown-screen";
  return [
    navigator.userAgent,
    `platform=${navigator.platform || "unknown"}`,
    `language=${navigator.language || "unknown"}`,
    `timezone=${Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown"}`,
    `screen=${screenSize}`,
  ].join(" | ");
}

function requestAttendancePosition() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("This device does not support browser location services."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    });
  });
}

async function getTeacherAttendanceLocationPayload() {
  let position;
  try {
    position = await requestAttendancePosition();
  } catch (locationError) {
    if (locationError?.code === 1) {
      throw new Error("Location permission was denied. Enable location access before marking attendance.");
    }
    if (locationError?.code === 2) {
      throw new Error("Location is unavailable. Turn on GPS/location services before marking attendance.");
    }
    if (locationError?.code === 3) {
      throw new Error("Location request timed out. Move to an open area and try again.");
    }
    throw new Error(locationError?.message || "Enable location services before marking attendance.");
  }

  const { latitude, longitude, accuracy } = position.coords;
  return {
    latitude,
    longitude,
    accuracy,
    address: `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
    device_info: collectAttendanceDeviceInfo(),
  };
}

function adminActivityLogKey(session) {
  const schoolCode =
    session?.school_code ||
    session?.schoolCode ||
    session?.school?.school_code ||
    session?.school?.schoolCode ||
    session?.user?.tenant?.schema_name ||
    session?.user?.tenant?.school_code ||
    session?.user?.tenant_id ||
    session?.user?.tenant ||
    "global";
  const userId = session?.user?.id || session?.user?.email || "anonymous";
  return `${ADMIN_ACTIVITY_LOG_KEY}.${String(schoolCode).toLowerCase()}.${userId}`;
}

function readAdminActivityLog(session) {
  if (typeof window === "undefined") return [];
  const storageKey = adminActivityLogKey(session);
  try {
    return JSON.parse(window.localStorage.getItem(storageKey) || "[]");
  } catch {
    window.localStorage.removeItem(storageKey);
    return [];
  }
}

function writeAdminActivityLog(session, items) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(adminActivityLogKey(session), JSON.stringify(items.slice(0, 80)));
}

function createAdminActivityNotification(payload = {}, actor = {}) {
  return {
    id: `activity-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    category: payload.category || "System",
    module: payload.module || "Admin Activity",
    user: payload.user || userDisplayName(actor) || "SchoolDom Admin",
    role: payload.role || roleLabel(actor?.role) || "Admin",
    action: payload.action || "Updated platform records.",
    status: payload.status || "Success",
    priority: payload.priority || "Medium",
    tone: payload.tone || "info",
    createdAt: new Date().toISOString(),
    isRead: false,
    source: "admin-activity",
  };
}

function idCardDate(value) {
  if (!value) {
    return "";
  }
  try {
    return new Date(value).toLocaleDateString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return String(value);
  }
}

function genderDisplay(value) {
  const normalized = String(value || "").toUpperCase();
  if (normalized === "M") return "Male";
  if (normalized === "F") return "Female";
  return value || "";
}

const CBT_ENTRY_CACHE_KEY = "schooldom.student_cbt_entry_cache";

function cbtEntryCacheKey(studentId, pin) {
  return `${String(studentId || "").trim().toLowerCase()}::${String(pin || "").trim().toUpperCase()}`;
}

function readCbtEntryCache() {
  try {
    return JSON.parse(window.localStorage.getItem(CBT_ENTRY_CACHE_KEY) || "{}");
  } catch {
    window.localStorage.removeItem(CBT_ENTRY_CACHE_KEY);
    return {};
  }
}

function writeCbtEntryCache(cache) {
  window.localStorage.setItem(CBT_ENTRY_CACHE_KEY, JSON.stringify(cache));
}

function StudentCbtEntry({ onEntry }) {
  const [studentId, setStudentId] = useState("");
  const [examPin, setExamPin] = useState("");
  const [error, setError] = useState("");
  const [offlineNotice, setOfflineNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    clearStoredSession();
  }, []);

  const canSubmit = studentId.trim().length > 0 && examPin.trim().length > 0 && !submitting;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError("");
    setOfflineNotice("");
    const normalizedPin = examPin.trim().toUpperCase();
    const cacheKey = cbtEntryCacheKey(studentId, normalizedPin);

    try {
      const response = await fetch(`${API_BASE_URL}/api/exams/cbt-entry/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: studentId.trim(),
          exam_pin: normalizedPin,
          is_offline: false,
          device_id: window.schoolDomDesktop?.client || window.navigator.userAgent,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload?.success || !payload?.session || !payload?.attempt_id) {
        throw new Error(payload?.message || payload?.error || "Could not open this CBT exam.");
      }
      const nextSession = { ...payload.session, auth_mode: "cbt_entry" };
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
      const cache = readCbtEntryCache();
      cache[cacheKey] = {
        attempt_id: payload.attempt_id,
        exam_id: payload.exam_id,
        session: nextSession,
        student_id: studentId.trim(),
        exam_pin: normalizedPin,
        cached_at: new Date().toISOString(),
      };
      writeCbtEntryCache(cache);
      onEntry?.(nextSession, payload.attempt_id);
    } catch (entryError) {
      const cached = readCbtEntryCache()[cacheKey];
      if (cached?.attempt_id && cached?.session) {
        window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(cached.session));
        setOfflineNotice("Offline mode: reopening the last exam package saved on this computer.");
        onEntry?.({ ...cached.session, auth_mode: "cbt_entry" }, cached.attempt_id);
        return;
      }
      setError(entryError.message || "Could not open this CBT exam. Check the admin server connection.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="student-cbt-entry-page">
      <section className="student-cbt-entry-card">
        <SchoolBrand school={{ name: "SchoolDom" }} subtitle="Student Exam App" compact />
        <form onSubmit={handleSubmit} className="student-cbt-entry-form">
          <label>
            Student ID
            <input
              value={studentId}
              onChange={(event) => {
                setStudentId(event.target.value);
                setError("");
              }}
              autoComplete="off"
              autoFocus
            />
          </label>
          <label>
            Exam PIN
            <input
              value={examPin}
              onChange={(event) => {
                setExamPin(event.target.value.toUpperCase());
                setError("");
              }}
              autoComplete="one-time-code"
            />
          </label>
          {error ? <p className="form-feedback error">{error}</p> : null}
          {offlineNotice ? <p className="form-feedback success">{offlineNotice}</p> : null}
          <button type="submit" disabled={!canSubmit}>
            {submitting ? "Opening exam..." : "Open Exam"}
          </button>
        </form>
      </section>
    </main>
  );
}

function RecordList({ title, rows = [], render, onSelect }) {
  return (
    <article className="app-panel">
      <h3>{title}</h3>
      {rows.length > 0 ? (
        <ul className="panel-list">
          {rows.map((item) => (
            <li key={item.id || render(item)}>
              {onSelect ? (
                <button type="button" className="table-action ghost" onClick={() => onSelect(item)}>
                  {render(item)}
                </button>
              ) : (
                render(item)
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel-empty">No records found.</p>
      )}
    </article>
  );
}

function AutoGrowTextarea({ value, onChange, rows = 2, className = "", ...props }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      {...props}
      ref={textareaRef}
      className={`auto-grow-textarea ${className}`.trim()}
      value={value}
      onChange={onChange}
      rows={rows}
    />
  );
}

function LessonPlanDetailDialog({ plan, onClose, title = "Lesson plan details" }) {
  if (!plan) return null;
  const sections = [
    ["Summary", plan.description || plan.body || plan.content],
    ["Objectives", plan.objectives],
    ["Activities", plan.activities],
    ["Resources", plan.resources],
    ["Assessment", plan.assessment],
    ["Teacher lesson plan", plan.notes],
  ].filter(([, content]) => content);

  return (
    <div className="lesson-plan-dialog-backdrop" role="presentation" onClick={onClose}>
      <article
        className="lesson-plan-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="lesson-plan-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="lesson-plan-dialog-head">
          <div>
            <p className="quiz-kicker">Week {plan.week_number}</p>
            <h3 id="lesson-plan-dialog-title">{plan.title || title}</h3>
            <small>
              {[plan.subject, plan.class_name, plan.term, plan.academic_year].filter(Boolean).join(" - ")}
            </small>
          </div>
          <button type="button" className="table-action ghost" onClick={onClose}>Close</button>
        </div>
        <div className="lesson-plan-dialog-meta">
          <span>{plan.status || "planned"}</span>
          <span>{plan.teacher ? `Teacher: ${plan.teacher}` : title}</span>
          {plan.updated_at ? <span>Updated: {formatDate(plan.updated_at)}</span> : null}
        </div>
        {sections.length ? (
          <div className="lesson-plan-dialog-sections">
            {sections.map(([label, content]) => (
              <section key={label} className="scheme-plan-section">
                <h5>{label}</h5>
                <p><RichQuizText text={content} /></p>
              </section>
            ))}
          </div>
        ) : (
          <p className="panel-empty">No additional details have been added for this week.</p>
        )}
      </article>
    </div>
  );
}

function StudentSchemeOfWorkPanel({ session, onNavigate, standalone = false }) {
  const [planning, setPlanning] = useState(null);
  const [error, setError] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);

  const loadPlanning = useCallback(async () => {
    setError("");
    try {
      const response = await requestJson(session, "GET", "/api/app/academic/planning/");
      setPlanning(response || {});
    } catch (loadError) {
      setError(loadError.message || "Could not load scheme of work.");
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      loadPlanning();
    }
  }, [loadPlanning, session]);

  const plans = planning?.lesson_plans || [];
  const grouped = plans.reduce((acc, plan) => {
    const key = plan.subject || "General";
    acc[key] = acc[key] || [];
    acc[key].push(plan);
    return acc;
  }, {});

  return (
    <section className={standalone ? "academic-page" : "student-panel academic-plan-panel"}>
      {standalone ? (
        <header className="academic-page-hero">
          <div>
            <p className="quiz-kicker">Academic planning</p>
            <h1>Scheme of Work</h1>
            <p>Weekly subject plans aligned with the active term and academic year.</p>
          </div>
          <button type="button" className="pill-button ghost" onClick={() => onNavigate?.("/dashboard")}>
            Back to dashboard
          </button>
        </header>
      ) : null}
      <div className={standalone ? "student-panel academic-plan-panel" : ""}>
      <div className="student-panel-head">
        <div>
          <h3>Scheme of Work</h3>
          <p className="student-panel-sub">
            {planning?.active_term?.name || "Active term"} - {planning?.active_year?.name || "Academic year"}
          </p>
        </div>
        <span className="student-pill">Week {planning?.progress?.latest_week || 0}</span>
      </div>
      {error ? <p className="form-feedback error">{error}</p> : null}
      {!planning ? (
        <p className="panel-empty">Loading scheme of work...</p>
      ) : plans.length === 0 ? (
        <p className="panel-empty">No scheme of work has been published for your class yet.</p>
      ) : (
        <div className="scheme-subject-grid">
          {Object.entries(grouped).map(([subject, subjectPlans]) => (
            <article key={subject} className="scheme-subject-card">
              <h4>{subject}</h4>
              {subjectPlans.map((plan) => (
                <article key={plan.id} className="scheme-week-detail">
                  <button type="button" className="scheme-week-row scheme-week-button" onClick={() => setSelectedPlan(plan)}>
                    <span>Week {plan.week_number}</span>
                    <strong>{plan.title}</strong>
                    <small>{plan.status}</small>
                    <em>View full details</em>
                  </button>
                </article>
              ))}
            </article>
          ))}
        </div>
      )}
      </div>
      <LessonPlanDetailDialog plan={selectedPlan} onClose={() => setSelectedPlan(null)} />
    </section>
  );
}

function StudentQrAttendanceScanner({ session, onRefresh, attendanceToday }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const frameRef = useRef(null);
  const scanningRef = useRef(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [manualToken, setManualToken] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const stopCamera = useCallback(() => {
    scanningRef.current = false;
    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  const markAttendance = useCallback(
    async (rawToken) => {
      const token = String(rawToken || "").trim();
      if (!token) {
        setError("Scan or enter the school attendance QR code.");
        return;
      }
      setSubmitting(true);
      setError("");
      setFeedback("Requesting location...");
      try {
        const location = await getTeacherAttendanceLocationPayload();
        setFeedback("Saving attendance...");
        const result = await requestJson(session, "POST", "/api/app/attendance/student-qr-mark/", {
          token,
          location,
        });
        setFeedback(result.message || "Attendance marked successfully.");
        setManualToken("");
        stopCamera();
        await onRefresh?.();
      } catch (scanError) {
        setFeedback("");
        setError(scanError.message || "Could not mark attendance.");
      } finally {
        setSubmitting(false);
      }
    },
    [onRefresh, session, stopCamera],
  );

  const startCamera = async () => {
    setError("");
    setFeedback("");
    if (!("BarcodeDetector" in window)) {
      setError("This browser cannot scan QR codes directly. Paste the QR token below instead.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not available on this device.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);
      setFeedback("Point the camera at the school attendance QR code.");
      scanningRef.current = true;
      const detector = new window.BarcodeDetector({ formats: ["qr_code"] });

      const scanFrame = async () => {
        if (!scanningRef.current || !videoRef.current || submitting) return;
        try {
          const codes = await detector.detect(videoRef.current);
          const value = codes?.[0]?.rawValue;
          if (value) {
            await markAttendance(value);
            return;
          }
        } catch {
          setError("The camera could not read the QR code. Try better light or paste the token below.");
        }
        frameRef.current = requestAnimationFrame(scanFrame);
      };
      frameRef.current = requestAnimationFrame(scanFrame);
    } catch (cameraError) {
      setError(cameraError?.message || "Allow camera access to scan the attendance QR code.");
      stopCamera();
    }
  };

  return (
    <section className="student-panel">
      <div className="student-panel-head">
        <div>
          <h3>QR Attendance</h3>
          <p className="student-panel-sub">Scan the school attendance QR code to mark today&apos;s attendance.</p>
        </div>
        <span className={`student-status-pill status-${attendanceToday?.status || "unmarked"}`}>
          {attendanceToday ? `Marked ${attendanceToday.status}` : "Not marked"}
        </span>
      </div>
      <div className="quick-actions-grid">
        <article className="quick-action-card featured" style={{ cursor: "default" }}>
          <div className="quick-action-icon">QR</div>
          <div className="quick-action-content">
            <h4>Student self scan</h4>
            <p>Only non K-12 schools can use student QR attendance.</p>
          </div>
        </article>
        <div className="student-card tone-blue" style={{ minHeight: 180 }}>
          <video
            ref={videoRef}
            muted
            playsInline
            style={{
              width: "100%",
              maxHeight: 220,
              borderRadius: 14,
              background: "#0f172a",
              objectFit: "cover",
              display: cameraActive ? "block" : "none",
            }}
          />
          {!cameraActive ? (
            <span className="student-card-detail">Camera preview will appear here after you start scanning.</span>
          ) : null}
        </div>
      </div>
      <div className="panel-form-actions">
        <button type="button" className="student-primary-btn" onClick={startCamera} disabled={submitting || cameraActive}>
          {cameraActive ? "Scanning..." : "Start scanner"}
        </button>
        {cameraActive ? (
          <button type="button" className="student-link-btn" onClick={stopCamera} disabled={submitting}>
            Stop camera
          </button>
        ) : null}
      </div>
      <label className="panel-field">
        <span>QR token fallback</span>
        <input
          type="text"
          value={manualToken}
          onChange={(event) => setManualToken(event.target.value)}
          placeholder="Paste scanned QR token or URL"
          disabled={submitting}
        />
      </label>
      <div className="panel-form-actions">
        <button type="button" className="student-link-btn" onClick={() => markAttendance(manualToken)} disabled={submitting}>
          {submitting ? "Saving..." : "Mark attendance"}
        </button>
      </div>
      {feedback ? <p className="form-feedback success">{feedback}</p> : null}
      {error ? <p className="form-feedback error">{error}</p> : null}
    </section>
  );
}

function StudentDashboard({
  data = {},
  student = {},
  onPromptResponse,
  onOpenOfflineWorkspace,
  onCheckResults,
  onMessageSend,
  onMarkMessageRead,
  onDeleteMessage,
  onRefresh,
  isRefreshing,
  onSignOut,
  scrollTargets = {},
  onNavigate,
  session,
}) {
  const dashboardData = data || {};
  const attendance = dashboardData.attendance || {};
  const school = resolveSchoolBrand(dashboardData.school, session?.school, session);
  const nonK12School = isNonK12School(session, dashboardData);
  const prompts = dashboardData.question_prompts || [];
  const results = dashboardData.recent_results || [];
  const exams = dashboardData.upcoming_exams || [];
  const subjects = dashboardData.subjects || [];
  const dailyQuiz = dashboardData.daily_personal_quiz || {};
  const fees = dashboardData.fees || [];
  const paymentInstructions = dashboardData.payment_instructions || {};
  const currentTerm = student.term || dashboardData.active_term?.name || "No active term";

  const [reportCard, setReportCard] = useState(null);
  const [reportError, setReportError] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [paymentFeedback, setPaymentFeedback] = useState("");

  const today = new Date();
  const todayLabel = today.toLocaleDateString([], { weekday: "long" });
  const pendingAssignments = prompts.filter((prompt) => !prompt.is_answered).length;
  const attendanceHistory = attendance.history || [];
  const presentCount = attendanceHistory.filter((record) => record.status === "present").length;
  const attendancePercent =
    attendanceHistory.length > 0
      ? Math.round((presentCount / attendanceHistory.length) * 100)
      : attendance.today
        ? 100
        : 0;

  const scoredResults = results.filter((item) => typeof item.score === "number");
  const averageScore = scoredResults.length
    ? Math.round(scoredResults.reduce((sum, item) => sum + (item.score || 0), 0) / scoredResults.length)
    : null;

  const sortedExams = [...exams].sort((a, b) => {
    const aDate = a.start_date || a.due_date || a.date;
    const bDate = b.start_date || b.due_date || b.date;
    return new Date(aDate || 0) - new Date(bDate || 0);
  });

  const upcomingExam = sortedExams[0];
  const examRows = sortedExams.slice(0, 5);
  const feeCurrency = NAIRA_SYMBOL;
  const expectedFees = fees.reduce((sum, fee) => sum + Number(fee.amount || 0), 0);
  const paidFees = fees.reduce((sum, fee) => sum + Number(fee.amount_paid || 0), 0);
  const remainingFees = fees.reduce((sum, fee) => sum + Number(fee.remaining_balance ?? Math.max(Number(fee.amount || 0) - Number(fee.amount_paid || 0), 0)), 0);
  const formatFeeAmount = (value) => `${feeCurrency}${Number(value || 0).toLocaleString()}`;

  const studentName = student.name || "Student";
  const profilePicture = student.profile_picture;
  const initials = userInitials({ full_name: studentName });
  const profileRows = [
    ["Full Name", studentName],
    ["Student ID", student.student_id || student.admission_number],
    ["Admission Number", student.admission_number || student.student_id],
    ["Class", student.class_name],
    ["Term", currentTerm],
    ["Email", student.email],
    ["Phone", student.phone],
    ["Gender", genderDisplay(student.gender)],
    ["Date of Birth", idCardDate(student.date_of_birth)],
    ["Admission Date", idCardDate(student.admission_date)],
    ["State of Origin", student.state_of_origin],
    ["Local Government", student.local_government],
    ["Student Type", student.student_type],
    ["Blood Group", student.blood_group],
    ["Disability", student.disability],
    ["Guardian Name", student.guardian_name],
    ["Guardian Phone", student.guardian_phone],
    ["Guardian Email", student.guardian_email],
    ["Guardian Relation", student.guardian_relation],
    ["Second Guardian Name", student.second_guardian_name],
    ["Second Guardian Phone", student.second_guardian_phone],
    ["Second Guardian Email", student.second_guardian_email],
    ["Second Guardian Relation", student.second_guardian_relation],
    ["Home Address", student.home_address],
  ];
  const unreadInbox = Number(dashboardData.metrics?.unread_inbox ?? 0);

  const fmtDate = (value) => {
    if (!value) {
      return "-";
    }
    try {
      return new Date(value).toLocaleDateString([], { month: "short", day: "numeric" });
    } catch (error) {
      return String(value);
    }
  };

  const fmtTime = (value) => {
    if (!value) {
      return "-";
    }
    try {
      return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    } catch (error) {
      return String(value);
    }
  };

  const handleResultsClick = async () => {
    if (!onCheckResults) {
      return;
    }
    setReportOpen(true);
    if (reportLoading) {
      return;
    }
    setReportLoading(true);
    setReportError("");
    try {
      const payload = await onCheckResults();
      if (!payload?.report_card) {
        throw new Error("No report card is available yet. Check back soon.");
      }
      setReportCard(payload.report_card);
    } catch (loadError) {
      setReportCard(null);
      setReportError(loadError.message || "Could not load your results.");
    } finally {
      setReportLoading(false);
    }
  };

  const statCards = [
    {
      key: "assignments",
      label: "Assignments",
      value: pendingAssignments || 0,
      detail: `${prompts.length} total`,
      tone: "amber",
    },
    {
      key: "attendance",
      label: "Attendance",
      value: attendancePercent ? `${attendancePercent}%` : "-",
      detail: attendance.today ? `Today: ${attendance.today.status}` : nonK12School ? "Scan QR to mark today" : "Awaiting school attendance",
      tone: "emerald",
    },
    {
      key: "grade",
      label: "Average Grade",
      value: averageScore !== null ? `${averageScore}%` : "-",
      detail: scoredResults.length ? "Based on recent results" : "No grades yet",
      tone: "gold",
    },
    {
      key: "upcoming",
      label: "Upcoming Exam",
      value: upcomingExam ? upcomingExam.subject || upcomingExam.title : "None",
      detail: upcomingExam ? fmtDate(upcomingExam.start_date || upcomingExam.due_date) : "No exam scheduled",
      tone: "indigo",
    },
    {
      key: "subjects",
      label: "Subjects Offered",
      value: subjects.length || 0,
      detail: subjects.length ? subjects.slice(0, 2).map((subject) => subject.code || subject.name).join(", ") : "No subjects assigned",
      tone: "blue",
    },
    {
      key: "daily-quiz",
      label: "Daily Quiz",
      value: `${dailyQuiz.completed_today ?? 0}/${dailyQuiz.total_subjects ?? subjects.length}`,
      detail: `Streak: ${dailyQuiz.streak_days || 0} day${Number(dailyQuiz.streak_days || 0) === 1 ? "" : "s"}`,
      tone: "indigo",
    },
    {
      key: "fees",
      label: "Fees Left",
      value: formatFeeAmount(remainingFees),
      detail: expectedFees ? `${formatFeeAmount(paidFees)} paid of ${formatFeeAmount(expectedFees)}` : "No fees assigned",
      tone: remainingFees > 0 ? "amber" : "emerald",
    },
  ];

  const go = (path) => {
    if (onNavigate) {
      onNavigate(path);
    }
  };
  const copyPaymentText = async (value) => {
    if (!value) return;
    const copied = await copyToClipboard(value);
    setPaymentFeedback(copied ? "Copied to clipboard." : `Copy this: ${value}`);
  };

  return (
    <div className={`student-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="student-sidebar">
        <div className="student-sidebar-head">
          <span>Student Workspace</span>
          <strong>{studentName}</strong>
          <small>{student.class_name || "Unassigned"} - {school?.name || "SchoolDom"}</small>
        </div>
        <nav className="student-nav">
          <button
            className="student-nav-item active"
            type="button"
            onClick={() => { go("/dashboard"); setNavOpen(false); }}
          >
            <DashboardIcon name="home" className="inline-icon" />
            <span>Dashboard</span>
          </button>
          {nonK12School ? (
            <button
              className="student-nav-item"
              type="button"
              onClick={() => { go("/attendance"); setNavOpen(false); }}
            >
              <DashboardIcon name="attendance" className="inline-icon" />
              <span>Attendance</span>
            </button>
          ) : null}
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/fees"); setNavOpen(false); }}
          >
            <DashboardIcon name="money" className="inline-icon" />
            <span>School Fees</span>
          </button>
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/quizzes"); setNavOpen(false); }}
          >
            <DashboardIcon name="exam" className="inline-icon" />
            <span>Quizzes</span>
          </button>
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/exams"); setNavOpen(false); }}
          >
            <DashboardIcon name="calendar" className="inline-icon" />
            <span>Exams</span>
          </button>
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/academic-planning"); setNavOpen(false); }}
          >
            <DashboardIcon name="planning" className="inline-icon" />
            <span>Scheme</span>
          </button>
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/messages"); setNavOpen(false); }}
          >
            <BellIcon className="inline-icon" />
            <span>Messages</span>
            {unreadInbox > 0 ? <strong className="student-pill notification-badge">{unreadInbox > 99 ? "99+" : unreadInbox}</strong> : null}
          </button>
          <button
            className="student-nav-item"
            type="button"
            onClick={() => { go("/results"); setNavOpen(false); }}
          >
            <DashboardIcon name="results" className="inline-icon" />
            <span>Results</span>
          </button>
        </nav>
        <div className="student-sidebar-footer">
          <button
            type="button"
            className="student-sidebar-profile"
            onClick={() => {
              setProfileOpen(true);
              setNavOpen(false);
            }}
            aria-label="View profile information"
            title="View profile information"
          >
            <div className="student-avatar">
              {profilePicture ? (
                <img src={profilePicture} alt={`${studentName} avatar`} />
              ) : (
                <span aria-hidden="true">{initials}</span>
              )}
            </div>
            <div>
              <strong>{studentName}</strong>
              <small>{student.email || "Student"}</small>
            </div>
          </button>
          {onSignOut ? (
            <button className="student-sidebar-signout" type="button" onClick={onSignOut}>
              Sign out
            </button>
          ) : null}
        </div>
      </aside>

      <main className="student-main">
        <div className="student-main-topbar">
          <div className="student-topbar-left">
            <button 
              type="button" 
              className="student-menu-toggle" 
              onClick={() => setNavOpen(!navOpen)}
              aria-label="Toggle navigation menu"
            >
              <span className="menu-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
            <p className="topbar-kicker">Student Workspace</p>
          </div>
            <div className="student-user-chip">
              <div className="student-user-meta">
                <p>{studentName}</p>
                <small>{student.email || "Student"}</small>
              </div>
            </div>
            <div className="student-topbar-actions">
              <span className="student-status-pill">Dashboard</span>
            </div>
        </div>

        <section className="student-hero">
          <div>
            <p className="student-hero-kicker">Welcome back</p>
            <h1>
              {studentName}
            </h1>
            <p className="student-hero-meta">
              Grade: {student.class_name || "Unassigned"} - Term: {currentTerm} - Today:{" "}
              {todayLabel}
            </p>
          </div>
          <div className="student-hero-actions">
            <span className={`student-status-pill status-${attendance.today?.status || "unmarked"}`}>
              {attendance.today ? `Marked ${attendance.today.status}` : nonK12School ? "Scan QR attendance" : "Attendance not marked"}
            </span>
            {nonK12School ? (
              <button
                type="button"
                className="student-link-btn"
                onClick={() => onNavigate?.("/attendance")}
              >
                Mark attendance
              </button>
            ) : null}
            <button
              type="button"
              className="student-primary-btn"
              onClick={() => onNavigate?.("/exams")}
            >
              Open exams
            </button>
          </div>
        </section>

        <section className="student-stats-grid student-dashboard-stats">
          {statCards.map((card) => (
            <article key={card.key} className={`student-card tone-${card.tone}`}>
              <span className="student-card-label">{card.label}</span>
              <strong className="student-card-value">{card.value}</strong>
              <span className="student-card-detail">{card.detail}</span>
            </article>
          ))}
        </section>

        {paymentInstructions.reference_code ? (
          <section className="student-panel">
            <div className="student-panel-head">
              <div>
                <h3>School Fees</h3>
                <p className="student-panel-sub">Expected amount, payments received, and what is left.</p>
              </div>
              <button className="student-link-btn" type="button" onClick={() => go("/fees")}>
                Open fees
              </button>
            </div>
            <div className="student-fee-mini-grid">
              <article className="student-card tone-blue">
                <span className="student-card-label">Expected to Pay</span>
                <strong className="student-card-value">{formatFeeAmount(expectedFees)}</strong>
                <span className="student-card-detail">{fees.length ? `${fees.length} assigned fee${fees.length === 1 ? "" : "s"}` : "No fees assigned"}</span>
              </article>
              <article className="student-card tone-emerald">
                <span className="student-card-label">Amount Paid</span>
                <strong className="student-card-value">{formatFeeAmount(paidFees)}</strong>
                <span className="student-card-detail">Confirmed by school finance</span>
              </article>
              <article className="student-card tone-amber">
                <span className="student-card-label">Amount Left</span>
                <strong className="student-card-value">{formatFeeAmount(remainingFees)}</strong>
                <span className="student-card-detail">{remainingFees > 0 ? "Outstanding balance" : "Fully paid"}</span>
              </article>
              <article className="student-card tone-gold">
                <span className="student-card-label">Reference Code</span>
                <strong className="student-card-value">{paymentInstructions.reference_code}</strong>
                <span className="student-card-detail">{paymentInstructions.narration}</span>
              </article>
              <article className="student-card tone-blue">
                <span className="student-card-label">School Account</span>
                <strong className="student-card-value">{paymentInstructions.bank_account_number || "-"}</strong>
                <span className="student-card-detail">{paymentInstructions.bank_account_name || "Ask school office to set account"}</span>
              </article>
            </div>
            <div className="table-actions-inline">
              <button type="button" className="table-action" onClick={() => copyPaymentText(paymentInstructions.reference_code)}>Copy code</button>
              <button type="button" className="table-action" onClick={() => copyPaymentText(paymentInstructions.narration)}>Copy narration</button>
              <button type="button" className="table-action" onClick={() => copyPaymentText(paymentInstructions.bank_account_number)}>Copy account</button>
            </div>
            {paymentFeedback ? <p className="form-feedback success">{paymentFeedback}</p> : null}
          </section>
        ) : null}

        <section className="student-panel">
          <div className="student-panel-head">
            <div>
              <h3>Quick Actions</h3>
              <p className="student-panel-sub">Common tasks and shortcuts</p>
            </div>
          </div>
          <div className="quick-actions-grid">
            <button
              className="quick-action-card"
              type="button"
              onClick={() => go("/quizzes")}
            >
              <div className="quick-action-icon">Q</div>
              <div className="quick-action-content">
                <h4>Take Quiz</h4>
                <p>Access available quizzes and assessments</p>
              </div>
            </button>
            <button
              className="quick-action-card"
              type="button"
              onClick={handleResultsClick}
            >
              <div className="quick-action-icon">R</div>
              <div className="quick-action-content">
                <h4>Check Results</h4>
                <p>View your exam scores and grades</p>
              </div>
            </button>
            <button
              className="quick-action-card featured"
              type="button"
              onClick={() => go("/exams")}
            >
              <div className="quick-action-icon">E</div>
              <div className="quick-action-content">
                <h4>Exam Page</h4>
                <p>Open available CBT exams from your dashboard</p>
              </div>
            </button>
            <button
              className="quick-action-card"
              type="button"
              onClick={() => go("/academic-planning")}
            >
              <div className="quick-action-icon">S</div>
              <div className="quick-action-content">
                <h4>Scheme of Work</h4>
                <p>View weekly plans for each subject</p>
              </div>
            </button>
            <button
              className="quick-action-card"
              type="button"
              onClick={() => go("/messages")}
            >
              <div className="quick-action-icon">M</div>
              <div className="quick-action-content">
                <h4>Messages</h4>
                <p>Communicate with teachers and staff</p>
              </div>
            </button>
          </div>
        </section>
        <section className="student-panel">
          <div className="student-panel-head">
            <div>
              <h3>Subjects Offered</h3>
              <p className="student-panel-sub">Subjects linked to your class, exams, or recorded scores.</p>
            </div>
            <div className="student-panel-actions">
              <span className="student-pill">{subjects.length} total</span>
            </div>
          </div>
          {subjects.length === 0 ? (
            <p className="panel-empty">No subjects have been assigned to you yet.</p>
          ) : (
            <div className="student-subject-grid">
              {subjects.map((subject) => (
                <article key={subject.id || subject.name} className="student-subject-card">
                  <span>{subject.code || "SUB"}</span>
                  <strong>{subject.name}</strong>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="student-panel">
          <div className="student-panel-head">
            <div>
              <h3>Exams</h3>
            </div>
            <button className="student-link-btn" type="button" onClick={handleResultsClick} disabled={reportLoading}>
              {reportLoading ? "Loading..." : "Check results"}
            </button>
            <button className="student-link-btn" type="button" onClick={() => go("/exams")}>
              View all
            </button>
          </div>
          {examRows.length === 0 ? (
            <p className="panel-empty">No exams scheduled.</p>
          ) : (
            <table className="student-table">
              <thead>
                <tr>
                  <th>Exam</th>
                  <th>Subject</th>
                  <th>Date</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {examRows.map((exam) => (
                  <tr key={(exam.id || exam.title) + "_exam"}>
                    <td>{exam.title || "Exam"}</td>
                    <td>{exam.subject || "-"}</td>
                    <td>{fmtDate(exam.start_date || exam.due_date)}</td>
                    <td>{fmtTime(exam.start_date || exam.due_time)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {reportOpen ? (
          <section className="student-panel">
            <div className="student-panel-head">
              <div>
                <h3>Report card</h3>
                <p className="student-panel-sub">
                  {reportCard?.student?.class_name || student.class_name || "Your class"}  - {" "}
                  {reportCard?.student?.student_id || student.student_id || "ID not set"}
                </p>
              </div>
              <div>
                <button className="student-link-btn" type="button" onClick={handleResultsClick} disabled={reportLoading}>
                  {reportLoading ? "Refreshing..." : "Refresh"}
                </button>
                <button className="student-link-btn" type="button" onClick={() => setReportOpen(false)}>
                  Close
                </button>
              </div>
            </div>
            {reportLoading ? (
              <p className="panel-empty">Loading your report...</p>
            ) : reportError ? (
              <p className="form-feedback error">{reportError}</p>
            ) : reportCard ? (
              <>
                <div className="report-school-brand compact-inline">
                  <SchoolBrand school={reportCard.school || school} subtitle="Report card" compact />
                </div>
                <div className="pill-stack">
                  <span className="pill">Total: {reportCard.total_score ?? "-"}</span>
                  <span className="pill">Average: {reportCard.average_score ?? "-"}</span>
                  {reportCard.class_position ? (
                    <span className="pill">
                      Position: {reportCard.class_position} / {reportCard.class_size || "?"}
                    </span>
                  ) : null}
                </div>
                {reportCard.scores && reportCard.scores.length ? (
                  <table className="student-table">
                    <thead>
                      <tr>
                        <th>Subject</th>
                        <th>Score</th>
                        <th>Max</th>
                        <th>%</th>
                        <th>Teacher</th>
                        <th>Term</th>
                        <th>Updated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reportCard.scores.map((row, index) => (
                        <tr key={row.id || `score-${index}`}>
                          <td>{row.subject || "Subject"}</td>
                          <td>{row.score ?? "-"}</td>
                          <td>{row.max_score ?? "-"}</td>
                          <td>{row.percentage ? `${Math.round(row.percentage)}%` : "-"}</td>
                          <td>{row.teacher || row.teacher_email || "-"}</td>
                          <td>{row.term || "-"}</td>
                          <td>{formatDate(row.recorded_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="panel-empty">No subjects have been scored yet.</p>
                )}
              </>
            ) : (
              <p className="panel-empty">Click refresh to load your report.</p>
            )}
          </section>
        ) : null}

        <div
          className="student-sidebar-overlay"
          onClick={() => {
            setNavOpen(false);
            setProfileOpen(false);
          }}
          style={{ display: navOpen || profileOpen ? 'block' : 'none' }}
        />
      </main>
      {profileOpen ? (
        <section className="student-profile-modal" role="dialog" aria-modal="true" aria-label="Student profile information">
          <article className="student-profile-card">
            <header className="student-profile-card-head">
              <div className="student-profile-photo">
                {profilePicture ? <img src={profilePicture} alt={`${studentName} profile`} /> : <span>{initials}</span>}
              </div>
              <div>
                <p className="topbar-kicker">Read-only profile</p>
                <h3>{studentName}</h3>
                <small>{student.class_name || "Unassigned"} - {school?.name || "SchoolDom"}</small>
              </div>
              <button type="button" className="student-profile-close" onClick={() => setProfileOpen(false)} aria-label="Close profile">
                x
              </button>
            </header>
            <dl className="student-profile-details">
              {profileRows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value || "-"}</dd>
                </div>
              ))}
            </dl>
          </article>
        </section>
      ) : null}
    </div>
  );
}

function StudentAttendancePage({ session, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAttendance = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/student/dashboard/");
      setData(result || {});
    } catch (loadError) {
      setError(loadError.message || "Could not load attendance.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const attendance = data?.attendance || {};
  const school = resolveSchoolBrand(data?.school, session?.school, session);
  const nonK12School = isNonK12School(session, data);
  const history = attendance.history || [];

  return (
    <section className="student-standalone-page">
      <header className="student-standalone-hero">
        <div>
          <p className="topbar-kicker">{school?.name || "SchoolDom"}</p>
          <h1>Attendance</h1>
          <p>{nonK12School ? "Scan your school QR code to mark your attendance." : "Your school marks attendance for you."}</p>
        </div>
        <button type="button" className="student-link-btn" onClick={() => onNavigate?.("/dashboard")}>
          Back to dashboard
        </button>
      </header>

      <ScreenState loading={loading && !data} error={error} onRetry={loadAttendance} />

      {data ? (
        nonK12School ? (
          <>
            <StudentQrAttendanceScanner
              session={session}
              attendanceToday={attendance.today}
              onRefresh={loadAttendance}
            />
            <section className="student-panel">
              <div className="student-panel-head">
                <div>
                  <h3>Attendance History</h3>
                  <p className="student-panel-sub">Your latest attendance records.</p>
                </div>
              </div>
              {history.length ? (
                <table className="student-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Status</th>
                      <th>Class</th>
                      <th>Marked By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((record) => (
                      <tr key={`${record.date}-${record.status}`}>
                        <td>{formatDate(record.date)}</td>
                        <td>{record.status || "-"}</td>
                        <td>{record.class_name || "-"}</td>
                        <td>{record.noted_by || "Self scan"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="panel-empty">No attendance history yet.</p>
              )}
            </section>
          </>
        ) : (
          <article className="student-panel">
            <h3>Attendance is managed by your school</h3>
            <p className="student-panel-sub">K-12 attendance is marked by teachers or school staff.</p>
          </article>
        )
      ) : null}
    </section>
  );
}

function StudentFeesPage({
  session,
  onNavigate,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [financeData, setFinanceData] = useState({});
  const [paymentInstructions, setPaymentInstructions] = useState({});
  const [bankPayments, setBankPayments] = useState([]);
  const [fees, setFees] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const school = resolveSchoolBrand(financeData?.school, session?.school, session);

  const loadFinance = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await requestJson(session, "GET", "/api/finance/wallet/");
      setFinanceData({ school: result.school || {} });
      setPaymentInstructions(result.payment_instructions || {});
      setBankPayments(result.bank_payments || []);
      setFees(result.fees || []);
    } catch (loadError) {
      setError(loadError.message || "Could not load school fees.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadFinance();
  }, [loadFinance]);

  const expectedFees = fees.reduce((sum, fee) => sum + Number(fee.amount || 0), 0);
  const paidFees = fees.reduce((sum, fee) => sum + Number(fee.amount_paid || 0), 0);
  const remainingFees = fees.reduce((sum, fee) => sum + Number(fee.remaining_balance ?? Math.max(Number(fee.amount || 0) - Number(fee.amount_paid || 0), 0)), 0);
  const formatFeeAmount = (value) =>
    `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  const copyText = async (value) => {
    if (!value) return;
    const copied = await copyToClipboard(value);
    setFeedback(copied ? "Copied to clipboard." : `Copy this: ${value}`);
  };

  return (
    <div className={`student-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="student-sidebar">
        <SchoolBrand school={school} subtitle="Student" />
        <nav className="student-nav">
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/dashboard"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">D</span>
            <span>Dashboard</span>
          </button>
          <button className="student-nav-item active" type="button">
            <span className="student-nav-icon" aria-hidden="true">
              <DashboardIcon name="money" className="inline-icon" />
            </span>
            <span>School Fees</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/quizzes"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">Q</span>
            <span>Quizzes</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/messages"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">M</span>
            <span>Messages</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/results"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">R</span>
            <span>Results</span>
          </button>
        </nav>
      </aside>

      <main className="student-main">
        <div className="student-main-topbar">
          <div className="student-topbar-left">
            <button 
              type="button" 
              className="student-menu-toggle" 
              onClick={() => setNavOpen(!navOpen)}
              aria-label="Toggle navigation menu"
            >
              <span className="menu-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
            <p className="topbar-kicker">Student Payments</p>
            <h1>School Fees</h1>
            <small>Use your bank transfer reference and track confirmed school-fee payments.</small>
          </div>
        </div>

        {loading ? (
          <p className="panel-empty">Loading school fees...</p>
        ) : error ? (
          <>
            <p className="form-feedback error">{error}</p>
            <button type="button" className="student-primary-btn" onClick={loadFinance}>Retry</button>
          </>
        ) : (
          <>
            <div className="student-fee-summary-grid">
              <article className="app-panel frosted">
                <p className="metric-label">Expected to pay</p>
                <h2 className="metric-value">{formatFeeAmount(expectedFees)}</h2>
                <p className="metric-trend">{fees.length ? `${fees.length} assigned fee${fees.length === 1 ? "" : "s"}` : "No fees assigned yet."}</p>
              </article>
              <article className="app-panel frosted">
                <p className="metric-label">Amount paid</p>
                <h2 className="metric-value">{formatFeeAmount(paidFees)}</h2>
                <p className="metric-trend">Confirmed fee payments.</p>
              </article>
              <article className="app-panel frosted">
                <p className="metric-label">Amount left</p>
                <h2 className="metric-value">{formatFeeAmount(remainingFees)}</h2>
                <p className="metric-trend">{remainingFees > 0 ? "Outstanding balance." : "Fully paid."}</p>
              </article>
              <article className="app-panel frosted">
                <h3>Bank Transfer Reference</h3>
                <p className="metric-label">Use this code in your transfer narration</p>
                <h2 className="metric-value">{paymentInstructions.reference_code || "-"}</h2>
                <div className="table-actions-inline">
                  <button type="button" className="table-action" onClick={() => copyText(paymentInstructions.reference_code)}>Copy code</button>
                  <button type="button" className="table-action" onClick={() => copyText(paymentInstructions.narration)}>Copy narration</button>
                </div>
                <p className="field-note">
                  Bank: {paymentInstructions.bank_account_name || "-"} - {paymentInstructions.bank_account_number || "No account set"}
                </p>
              </article>
              {feedback ? <p className="form-feedback success">{feedback}</p> : null}
            </div>
            <article className="app-panel">
              <h3>Fee Breakdown</h3>
              {fees.length ? (
                <table className="student-table">
                  <thead>
                    <tr>
                      <th>Fee</th>
                      <th>Expected</th>
                      <th>Paid</th>
                      <th>Left</th>
                      <th>Status</th>
                      <th>Due</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fees.map((fee) => {
                      const paid = Number(fee.amount_paid || 0);
                      const remaining = Number(fee.remaining_balance ?? Math.max(Number(fee.amount || 0) - paid, 0));
                      const statusLabel = fee.payment_status || (remaining <= 0 ? "paid" : paid > 0 ? "partial" : fee.status);
                      return (
                        <tr key={fee.id}>
                          <td>{fee.title}</td>
                          <td>{formatFeeAmount(fee.amount, fee.currency)}</td>
                          <td>{formatFeeAmount(paid, fee.currency)}</td>
                          <td>{formatFeeAmount(remaining, fee.currency)}</td>
                          <td><span className={`finance-status status-${statusLabel}`}>{statusLabel}</span></td>
                          <td>{formatDate(fee.due_date)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : <p className="panel-empty">No school fees have been assigned to your class yet.</p>}
            </article>
            <article className="app-panel">
              <h3>Student Bank Payment History</h3>
              {bankPayments.length ? (
                <table className="student-table">
                  <thead><tr><th>Date</th><th>Reference</th><th>Amount</th><th>Applied</th><th>Balance</th><th>Status</th></tr></thead>
                  <tbody>
                    {bankPayments.map((payment) => (
                      <tr key={payment.id}>
                        <td>{formatDate(payment.created_at)}</td>
                        <td>{payment.bank_reference || payment.reference_code || "-"}</td>
                        <td>{formatFeeAmount(payment.amount)}</td>
                        <td>{formatFeeAmount(payment.applied_amount)}</td>
                        <td>{formatFeeAmount(payment.unapplied_amount)}</td>
                        <td><span className={`finance-status status-${payment.status || "pending"}`}>{payment.status || "pending"}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="panel-empty">No bank transfer payments found yet.</p>}
            </article>
          </>
        )}

        <div
          className="student-sidebar-overlay"
          onClick={() => setNavOpen(false)}
          style={{ display: navOpen ? 'block' : 'none' }}
        />
      </main>
    </div>
  );
}

function normalizeRecipientRole(item = {}) {
  return String(item.role || item.user_role || item.type || item.person_type || "").toLowerCase();
}

function recipientClassKey(item = {}) {
  return String(item.class_id || item.class_group_id || item.class_name || item.class_group || "").toLowerCase();
}

function filterRecipientsForRole(recipients = [], viewer = {}, fallbackClass = "") {
  const viewerRole = String(viewer?.role || "").toLowerCase();
  const viewerClass = String(viewer?.class_id || viewer?.class_name || viewer?.class_group || fallbackClass || "").toLowerCase();
  return recipients.filter((item) => {
    const role = normalizeRecipientRole(item);
    const isAdmin = ["admin", "school_admin", "principal", "super_admin"].includes(role) || (!role && item?.email);
    const isTeacher = role === "teacher";
    const isStudent = role === "student";
    if (["school_admin", "principal", "super_admin"].includes(viewerRole)) return true;
    if (viewerRole === "teacher") return isAdmin || isStudent;
    if (viewerRole === "student") {
      return isAdmin || isTeacher;
    }
    if (["staff", "accountant"].includes(viewerRole)) {
      return true;
    }
    return isAdmin;
  });
}

function StudentMessagesPage({ session, data, onMessageSend, onNavigate }) {
  const [messageData, setMessageData] = useState(data || { inbox: [], admin_contacts: [] });
  const [messages, setMessages] = useState((data?.inbox || []).slice(0, 50));
  const [loading, setLoading] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const availableRecipients = filterRecipientsForRole(
    messageData?.recipients || messageData?.admin_contacts || [],
    session?.user,
    messageData?.student?.class_name || data?.student?.class_name
  );
  const recipientOptions = availableRecipients.map((item) => ({
    value: item.email,
    label: `${item.name || item.email}${normalizeRecipientRole(item) ? ` - ${roleLabel(normalizeRecipientRole(item))}` : ""}`,
  }));
  const school = resolveSchoolBrand(messageData?.school, data?.school, session?.school, session);

  const loadMessages = useCallback(async () => {
    setLoading(true);
    try {
      const snapshot = await requestJson(session, "GET", "/api/app/messages/");
      setMessageData(snapshot || { inbox: [], admin_contacts: [] });
      setMessages((snapshot?.inbox || []).slice(0, 50));
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadMessages().catch(() => {});
    const pollId = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadMessages().catch(() => {});
      }
    }, MESSAGE_POLL_INTERVAL_MS);
    return () => window.clearInterval(pollId);
  }, [loadMessages]);

  const handleComposeMessage = async (recipient, subject, body, _selectedRecipient, attachments = []) => {
    if (!onMessageSend) return;
    await onMessageSend(recipient, subject, body, attachments);
    await loadMessages();
  };

  const handleMarkRead = async (messageId) => {
    await requestJson(session, "POST", `/api/app/messages/${messageId}/read/`);
    await loadMessages();
  };

  const handleDelete = async (messageId) => {
    await requestJson(session, "DELETE", `/api/app/messages/${messageId}/`);
    await loadMessages();
  };

  return (
    <div className={`student-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="student-sidebar">
        <SchoolBrand school={school} subtitle={roleLabel(session?.user?.role) || "Messages"} />
        <nav className="student-nav">
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/dashboard"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">D</span>
            <span>Dashboard</span>
          </button>
          {session?.user?.role === "student" ? (
            <>
              <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/fees"); setNavOpen(false); }}>
                <span className="student-nav-icon" aria-hidden="true">
                  <DashboardIcon name="money" className="inline-icon" />
                </span>
                <span>School Fees</span>
              </button>
              <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/quizzes"); setNavOpen(false); }}>
                <span className="student-nav-icon" aria-hidden="true">Q</span>
                <span>Quizzes</span>
              </button>
            </>
          ) : null}
          <button className="student-nav-item active" type="button">
            <span className="student-nav-icon" aria-hidden="true">M</span>
            <span>Messages</span>
          </button>
          {session?.user?.role === "student" ? (
            <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/results"); setNavOpen(false); }}>
              <span className="student-nav-icon" aria-hidden="true">R</span>
              <span>Results</span>
            </button>
          ) : null}
        </nav>
      </aside>

      <main className="student-main">
        <div className="student-main-topbar">
          <div className="student-topbar-left">
            <button 
              type="button" 
              className="student-menu-toggle" 
              onClick={() => setNavOpen(!navOpen)}
              aria-label="Toggle navigation menu"
            >
              <span className="menu-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
            <p className="topbar-kicker">Messages</p>
            <h1>Inbox & Communications</h1>
            <small>Stay connected with your school team.</small>
          </div>
        </div>

        <section className="student-panel">
          <MessageInboxPanel
            title="Your Messages"
            messages={messages}
            recipientOptions={recipientOptions}
            onComposeSubmit={handleComposeMessage}
            onMarkRead={handleMarkRead}
            onDelete={handleDelete}
            onRefresh={loadMessages}
          />
          {loading ? <p className="panel-empty compact">Checking for new messages...</p> : null}
        </section>

        <div
          className="student-sidebar-overlay"
          onClick={() => setNavOpen(false)}
          style={{ display: navOpen ? 'block' : 'none' }}
        />
      </main>
    </div>
  );
}

function StudentResultsPage({ session, data, onNavigate }) {
  const [reportCard, setReportCard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const student = data?.student || {};
  const school = resolveSchoolBrand(reportCard?.school, data?.school, session?.school, session);

  const handleLoadResults = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/results/my/");
      setReportCard(result.report_card || result);
    } catch (err) {
      setError(err.message || "Could not load results.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleLoadResults();
  }, []);

  return (
    <div className={`student-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="student-sidebar">
        <SchoolBrand school={school} subtitle="Student" />
        <nav className="student-nav">
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/dashboard"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">D</span>
            <span>Dashboard</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/fees"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">
              <DashboardIcon name="money" className="inline-icon" />
            </span>
            <span>School Fees</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/quizzes"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">Q</span>
            <span>Quizzes</span>
          </button>
          <button className="student-nav-item" type="button" onClick={() => { onNavigate?.("/messages"); setNavOpen(false); }}>
            <span className="student-nav-icon" aria-hidden="true">M</span>
            <span>Messages</span>
          </button>
          <button className="student-nav-item active" type="button">
            <span className="student-nav-icon" aria-hidden="true">R</span>
            <span>Results</span>
          </button>
        </nav>
      </aside>

      <main className="student-main">
        <div className="student-main-topbar">
          <div className="student-topbar-left">
            <button 
              type="button" 
              className="student-menu-toggle" 
              onClick={() => setNavOpen(!navOpen)}
              aria-label="Toggle navigation menu"
            >
              <span className="menu-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
            <p className="topbar-kicker">Academic Performance</p>
            <h1>Your Results</h1>
            <small>{student.class_name || "Class"} - {student.student_id || "ID"}</small>
          </div>
        </div>

        <section className="student-panel">
          {loading && !reportCard ? (
            <p className="panel-empty">Loading results...</p>
          ) : error ? (
            <>
              <p className="form-feedback error">{error}</p>
              <button type="button" className="student-primary-btn" onClick={handleLoadResults}>Retry</button>
            </>
          ) : reportCard ? (
            <>
              <div className="report-school-brand compact-inline">
                <SchoolBrand school={reportCard.school || school} subtitle="Report card" compact />
              </div>
              <div className="pill-stack">
                <span className="pill">Total: {reportCard.total_score ?? "-"}</span>
                <span className="pill">Average: {reportCard.average_score ?? "-"}</span>
                {reportCard.class_position ? (
                  <span className="pill">
                    Position: {reportCard.class_position} / {reportCard.class_size || "?"}
                  </span>
                ) : null}
              </div>
              {reportCard.scores && reportCard.scores.length ? (
                <table className="student-table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Score</th>
                      <th>Max</th>
                      <th>%</th>
                      <th>Grade</th>
                      <th>Remark</th>
                      <th>Teacher</th>
                      <th>Term</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportCard.scores.map((row, index) => (
                      <tr key={row.id || `score-${index}`}>
                        <td>{row.subject || "Subject"}</td>
                        <td>{row.score ?? "-"}</td>
                        <td>{row.max_score ?? "-"}</td>
                        <td>{row.percentage ? `${Math.round(row.percentage)}%` : "-"}</td>
                        <td>{row.grade || "-"}</td>
                        <td>{row.performance_remark || "-"}</td>
                        <td>{row.teacher || row.teacher_email || "-"}</td>
                        <td>{row.term || "-"}</td>
                        <td>{formatDate(row.recorded_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="panel-empty">No subjects have been scored yet.</p>
              )}
            </>
          ) : (
            <p className="panel-empty">Click refresh to load your results.</p>
          )}
          <button type="button" className="student-link-btn" onClick={handleLoadResults} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh Results"}
          </button>
        </section>

        <div
          className="student-sidebar-overlay"
          onClick={() => setNavOpen(false)}
          style={{ display: navOpen ? 'block' : 'none' }}
        />
      </main>
    </div>
  );
}
 
function StudentWorkspace({
  session,
  data = {},
  onPromptResponse,
  onMessageSend,
  onMarkMessageRead,
  onDeleteMessage,
  onOfflineSubmit,
  onCheckResults,
  onSignOut,
  isRefreshing,
  onRefresh,
  onNavigate,
}) {
  const student = data?.student || {};

  return (
    <StudentDashboard
      data={data}
      student={student}
      onPromptResponse={onPromptResponse}
      onOpenOfflineWorkspace={onOfflineSubmit}
      onCheckResults={onCheckResults}
      onMessageSend={onMessageSend}
      onMarkMessageRead={onMarkMessageRead}
      onDeleteMessage={onDeleteMessage}
      onRefresh={onRefresh}
      onNavigate={onNavigate}
      isRefreshing={isRefreshing}
      onSignOut={onSignOut}
      session={session}
    />
  );
}

function TeacherQuizPage({ session, onNavigate }) {
  const [quizzes, setQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [builder, setBuilder] = useState({
    title: "",
    description: "",
    is_published: false,
    allow_multiple_attempts: false,
    time_limit_minutes: 10,
    questions: [
      {
        text: "",
        explanation: "",
        points: 1,
        choices: [
          { text: "Option A", is_correct: true },
          { text: "Option B", is_correct: false },
        ],
      },
    ],
  });
  const [saving, setSaving] = useState(false);

  const loadQuizzes = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await requestJson(session, "GET", "/api/quizzes/teacher/");
      setQuizzes(response || []);
    } catch (loadError) {
      setError(loadError.message || "Could not load quizzes.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadQuizzes();
  }, [loadQuizzes]);

  const updateQuestion = (index, payload) => {
    setBuilder((prev) => {
      const questions = prev.questions.map((q, i) => (i === index ? { ...q, ...payload } : q));
      return { ...prev, questions };
    });
  };

  const updateChoice = (qIndex, cIndex, payload) => {
    setBuilder((prev) => {
      const questions = prev.questions.map((question, idx) => {
        if (idx !== qIndex) return question;
        const choices = question.choices.map((choice, ci) => (ci === cIndex ? { ...choice, ...payload } : choice));
        return { ...question, choices };
      });
      return { ...prev, questions };
    });
  };

  const addQuestion = () => {
    setBuilder((prev) => ({
      ...prev,
      questions: [
        ...prev.questions,
        {
          text: "",
          explanation: "",
          points: 1,
          choices: [
            { text: "Option A", is_correct: true },
            { text: "Option B", is_correct: false },
          ],
        },
      ],
    }));
  };

  const addChoice = (qIndex) => {
    setBuilder((prev) => {
      const questions = prev.questions.map((question, idx) => {
        if (idx !== qIndex) return question;
        return {
          ...question,
          choices: [...question.choices, { text: `Option ${question.choices.length + 1}`, is_correct: false }],
        };
      });
      return { ...prev, questions };
    });
  };

  const setCorrectChoice = (qIndex, cIndex) => {
    setBuilder((prev) => {
      const questions = prev.questions.map((question, idx) => {
        if (idx !== qIndex) return question;
        return {
          ...question,
          choices: question.choices.map((choice, ci) => ({ ...choice, is_correct: ci === cIndex })),
        };
      });
      return { ...prev, questions };
    });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        title: builder.title.trim(),
        description: builder.description.trim(),
        allow_multiple_attempts: builder.allow_multiple_attempts,
        is_published: builder.is_published,
        time_limit_minutes: Number(builder.time_limit_minutes) || 0,
        questions: builder.questions.map((question, idx) => ({
          text: question.text.trim(),
          explanation: (question.explanation || "").trim(),
          points: Number(question.points) || 1,
          order: idx + 1,
          choices: question.choices.map((choice) => ({ text: choice.text.trim(), is_correct: !!choice.is_correct })),
        })),
      };
      await requestJson(session, "POST", "/api/quizzes/teacher/", payload);
      setBuilder((prev) => ({ ...prev, title: "", description: "", time_limit_minutes: 10 }));
      loadQuizzes();
    } catch (submitError) {
      setError(submitError.message || "Could not save quiz.");
    } finally {
      setSaving(false);
    }
  };

  const handlePublishToggle = async (quiz) => {
    try {
      await requestJson(session, "PATCH", `/api/quizzes/teacher/${quiz.id}/`, { is_published: !quiz.is_published });
      loadQuizzes();
    } catch (toggleError) {
      setError(toggleError.message || "Could not update quiz.");
    }
  };

  const handleDelete = async (quizId) => {
    try {
      await requestJson(session, "DELETE", `/api/quizzes/teacher/${quizId}/`);
      loadQuizzes();
    } catch (deleteError) {
      setError(deleteError.message || "Could not delete quiz.");
    }
  };

  return (
    <section className="quiz-layout">
      <header className="quiz-hero">
        <div>
          <p className="quiz-kicker">Assessments</p>
          <h1>Test and Assessments</h1>
          <p>Create, publish, and track quick checks.</p>
        </div>
        <div className="quiz-actions">
          <button type="button" className="pill-button ghost" onClick={() => onNavigate?.("/dashboard")}>
            Back to dashboard
          </button>
        </div>
      </header>

      <form className="quiz-builder" onSubmit={handleCreate}>
        <div className="quiz-builder-head">
          <div>
            <p className="quiz-kicker">New quiz</p>
            <h3>Compose questions & options</h3>
          </div>
          <div className="quiz-switches">
            <label className="switch">
              <input
                type="checkbox"
                checked={builder.allow_multiple_attempts}
                onChange={(event) => setBuilder((prev) => ({ ...prev, allow_multiple_attempts: event.target.checked }))}
              />
              <span>Allow multiple attempts</span>
            </label>
            <label className="switch">
              <input
                type="checkbox"
                checked={builder.is_published}
                onChange={(event) => setBuilder((prev) => ({ ...prev, is_published: event.target.checked }))}
              />
              <span>Publish on save</span>
            </label>
          </div>
        </div>

        <div className="quiz-field-grid">
          <label className="quiz-field">
            <span>Title</span>
            <input
              value={builder.title}
              onChange={(event) => setBuilder((prev) => ({ ...prev, title: event.target.value }))}
              placeholder="Weekly checkpoint"
              required
            />
          </label>
          <label className="quiz-field">
            <span>Description</span>
            <FormattedTextarea
              value={builder.description}
              onChange={(event) => setBuilder((prev) => ({ ...prev, description: event.target.value }))}
              placeholder="Add context for students..."
            />
          </label>
          <label className="quiz-field">
            <span>Time limit (minutes)</span>
            <input
              type="number"
              min="1"
              value={builder.time_limit_minutes}
              onChange={(event) => setBuilder((prev) => ({ ...prev, time_limit_minutes: Number(event.target.value) || 0 }))}
              placeholder="Enter minutes"
              required
            />
          </label>
        </div>

        <div className="quiz-questions">
          {builder.questions.map((question, qIndex) => (
            <article key={qIndex} className="quiz-question-card">
              <div className="quiz-question-head">
                <div>
                  <p className="quiz-kicker">Question {qIndex + 1}</p>
                  <FormattedTextarea
                    value={question.text}
                    onChange={(event) => updateQuestion(qIndex, { text: event.target.value })}
                    placeholder="Ask a question..."
                    rows={2}
                  />
                  <FormattedTextarea
                    value={question.explanation}
                    onChange={(event) => updateQuestion(qIndex, { explanation: event.target.value })}
                    placeholder="Answer / explanation shown after submission"
                    className="quiz-explanation"
                  />
                </div>
                <label className="quiz-points">
                  <span>Points</span>
                  <input
                    type="number"
                    min="1"
                    value={question.points}
                    onChange={(event) => updateQuestion(qIndex, { points: event.target.value })}
                  />
                </label>
              </div>
              <div className="quiz-choice-grid">
                {question.choices.map((choice, cIndex) => (
                  <label key={cIndex} className={`quiz-choice ${choice.is_correct ? "correct" : ""}`}>
                    <input
                      type="radio"
                      name={`q-${qIndex}-correct`}
                      checked={choice.is_correct}
                      onChange={() => setCorrectChoice(qIndex, cIndex)}
                    />
                    <input
                      value={choice.text}
                      onChange={(event) => updateChoice(qIndex, cIndex, { text: event.target.value })}
                      placeholder="Option text"
                    />
                  </label>
                ))}
              </div>
              <div className="quiz-choice-actions">
                <button type="button" onClick={() => addChoice(qIndex)}>
                  + Add option
                </button>
              </div>
            </article>
          ))}
          <div className="quiz-question-actions">
            <button type="button" onClick={addQuestion}>
              + Add another question
            </button>
          </div>
        </div>

        {error ? <p className="form-feedback error">{error}</p> : null}
        <div className="quiz-submit-row">
          <button className="pill-button" type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save quiz"}
          </button>
        </div>
      </form>

      <section className="quiz-list-section">
        <div className="quiz-list-head">
          <h3>Quizzes</h3>
          <span className="pill muted">{quizzes.length} total</span>
        </div>
        {loading ? (
          <p className="panel-empty">Loading quizzes...</p>
        ) : quizzes.length === 0 ? (
          <p className="panel-empty">No quizzes yet. Create one above.</p>
        ) : (
          <div className="quiz-grid">
            {quizzes.map((quiz) => (
              <article key={quiz.id} className="quiz-card">
                <div className="quiz-card-head">
                  <div>
                    <p className="quiz-kicker">{quiz.is_published ? "Published" : "Draft"}</p>
                    <h4>{quiz.title}</h4>
                    <small>{quiz.description || "No description"}</small>
                  </div>
                  <button type="button" className="pill-button ghost" onClick={() => handlePublishToggle(quiz)}>
                    {quiz.is_published ? "Unpublish" : "Publish"}
                  </button>
                </div>
                <div className="quiz-card-meta">
                  <span>{quiz.question_count} questions</span>
                  <span>{quiz.submission_count} submissions</span>
                </div>
                <div className="quiz-card-actions">
                  <button type="button" onClick={() => onNavigate?.(`/quizzes?quiz=${quiz.id}`)}>
                    Open
                  </button>
                  <button type="button" className="danger" onClick={() => handleDelete(quiz.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function StudentQuizPage({ session, onNavigate }) {
  const [activeQuiz, setActiveQuiz] = useState(null);
  const [quizSource, setQuizSource] = useState("personal");
  const [teacherQuizzes, setTeacherQuizzes] = useState([]);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [timeLeft, setTimeLeft] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const timerRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [options, setOptions] = useState({ subjects: [], history: [], stats: {}, max_questions: 20, class_group: {} });
  const [selectedSubject, setSelectedSubject] = useState("");
  const [flagModalOpen, setFlagModalOpen] = useState(false);
  const [flagReason, setFlagReason] = useState("");
  const [flagStatus, setFlagStatus] = useState({ busy: false, error: "", success: "" });
  const [flagCount, setFlagCount] = useState(0);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const [showAllPersonalHistory, setShowAllPersonalHistory] = useState(false);
  const [screenSecurityWarning, setScreenSecurityWarning] = useState("");
  const flagFeedbackTimerRef = useRef(null);

  const loadPersonalQuizData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [response, publishedQuizzes] = await Promise.all([
        requestJson(session, "GET", "/api/quizzes/personal/options/"),
        requestJson(session, "GET", "/api/quizzes/student/"),
      ]);
      setOptions(response || {});
      setTeacherQuizzes(publishedQuizzes || []);
      if (!selectedSubject && response?.subjects?.length) {
        const firstAvailable = response.subjects.find((subject) => subject.today_status !== "unavailable") || response.subjects[0];
        setSelectedSubject(String(firstAvailable.id));
      }
    } catch (loadError) {
      setError(loadError.message || "Could not load personal quiz data.");
    } finally {
      setLoading(false);
    }
  }, [session, selectedSubject]);

  useEffect(() => {
    loadPersonalQuizData();
  }, [loadPersonalQuizData]);

  useEffect(() => {
    if (!flagStatus.success) {
      return undefined;
    }
    if (flagFeedbackTimerRef.current) {
      window.clearTimeout(flagFeedbackTimerRef.current);
    }
    flagFeedbackTimerRef.current = window.setTimeout(() => {
      setFlagStatus((prev) => ({ ...prev, success: "" }));
      flagFeedbackTimerRef.current = null;
    }, 2000);
    return () => {
      if (flagFeedbackTimerRef.current) {
        window.clearTimeout(flagFeedbackTimerRef.current);
        flagFeedbackTimerRef.current = null;
      }
    };
  }, [flagStatus.success]);

  const generateQuiz = async (subjectId = selectedSubject) => {
    if (!subjectId) {
      setError("Choose a subject before generating a quiz.");
      return;
    }
    const subject = options.subjects?.find((item) => String(item.id) === String(subjectId));
    if (subject?.today_status === "completed") {
      setError("You have already completed this subject quiz today. It will reset tomorrow.");
      return;
    }
    if (subject?.today_status === "unavailable" || Number(subject?.available_question_count || 0) <= 0) {
      setError(`${subject?.name || "This subject"} has no personal quiz questions yet. Add questions to a matching Personal Quiz Folder or CBT question bank.`);
      return;
    }
    setGenerating(true);
    setError("");
    try {
      const quiz = await requestJson(session, "POST", "/api/quizzes/personal/generate/", {
        subject_id: Number(subjectId),
        question_count: DAILY_PERSONAL_QUESTION_LIMIT,
      });
      requestLandscapeForPersonalQuiz();
      setActiveQuiz(quiz);
      setQuizSource("personal");
      setAnswers({});
      setFlagStatus({ busy: false, error: "", success: "" });
      setFlagCount(0);
      setResult(null);
      setCurrentQuestionIndex(0);
    } catch (loadError) {
      setError(loadError.message || "Could not generate quiz.");
    } finally {
      setGenerating(false);
    }
  };

  const startTeacherQuiz = async (quizId) => {
    setGenerating(true);
    setError("");
    try {
      const detail = await requestJson(session, "GET", `/api/quizzes/student/${quizId}/`);
      setActiveQuiz(detail);
      setQuizSource("teacher");
      setAnswers({});
      setFlagStatus({ busy: false, error: "", success: "" });
      setFlagCount(0);
      setResult(null);
      setCurrentQuestionIndex(0);
    } catch (loadError) {
      setError(loadError.message || "Could not load teacher quiz.");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (!activeQuiz || result || !activeQuiz.time_limit_minutes) {
      setTimeLeft(null);
      return;
    }

    const dueTime = activeQuiz.due_at ? new Date(activeQuiz.due_at).getTime() : null;
    const initialSeconds = dueTime
      ? Math.max(0, Math.floor((dueTime - Date.now()) / 1000))
      : Math.max(0, Math.floor(activeQuiz.time_limit_minutes) * 60);
    setTimeLeft(initialSeconds);
    timerRef.current = window.setInterval(() => {
      setTimeLeft((prev) => {
        if (prev === null) return null;
        if (prev <= 1) {
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [activeQuiz, result]);

  useEffect(() => {
    if (!activeQuiz || result) {
      setScreenSecurityWarning("");
      return undefined;
    }

    const warnCaptureBlocked = (message = "Screenshots, screen recording, printing, and copying are disabled during this quiz.") => {
      setScreenSecurityWarning(message);
    };
    const clearClipboard = () => {
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText("").catch(() => {});
      }
    };
    const blockInteraction = (event) => {
      event.preventDefault();
      warnCaptureBlocked();
    };
    const blockKeys = (event) => {
      const key = String(event.key || "").toLowerCase();
      const isPrintScreen = event.key === "PrintScreen";
      const isMacCapture = event.metaKey && event.shiftKey && ["3", "4", "5", "s"].includes(key);
      const isScreenRecorder = (event.metaKey || event.ctrlKey) && event.altKey && key === "r";
      const isRestricted =
        isPrintScreen ||
        isMacCapture ||
        isScreenRecorder ||
        ((event.ctrlKey || event.metaKey) && ["p", "s", "c", "x", "v"].includes(key));

      if (isRestricted) {
        event.preventDefault();
        if (isPrintScreen) clearClipboard();
        warnCaptureBlocked(isPrintScreen ? "Screenshot capture is disabled during this quiz." : undefined);
      }
    };
    const blockPrint = (event) => {
      event.preventDefault();
      warnCaptureBlocked("Printing is disabled during this quiz.");
    };

    document.addEventListener("contextmenu", blockInteraction);
    document.addEventListener("copy", blockInteraction);
    document.addEventListener("cut", blockInteraction);
    document.addEventListener("paste", blockInteraction);
    document.addEventListener("keydown", blockKeys);
    document.addEventListener("keyup", blockKeys);
    window.addEventListener("beforeprint", blockPrint);

    return () => {
      document.removeEventListener("contextmenu", blockInteraction);
      document.removeEventListener("copy", blockInteraction);
      document.removeEventListener("cut", blockInteraction);
      document.removeEventListener("paste", blockInteraction);
      document.removeEventListener("keydown", blockKeys);
      document.removeEventListener("keyup", blockKeys);
      window.removeEventListener("beforeprint", blockPrint);
    };
  }, [activeQuiz, result]);

  useEffect(() => {
    const shouldUseMobileLandscape = Boolean(activeQuiz && quizSource === "personal" && !result);
    if (!shouldUseMobileLandscape) {
      document.body.classList.remove("personal-quiz-mobile-landscape");
      try {
        window.screen?.orientation?.unlock?.();
      } catch {
        // Some browsers do not expose orientation unlock.
      }
      return undefined;
    }

    const syncLandscapeClass = () => {
      document.body.classList.toggle("personal-quiz-mobile-landscape", isMobileQuizViewport());
    };

    syncLandscapeClass();
    requestLandscapeForPersonalQuiz();
    window.addEventListener("resize", syncLandscapeClass);
    window.addEventListener("orientationchange", syncLandscapeClass);

    return () => {
      window.removeEventListener("resize", syncLandscapeClass);
      window.removeEventListener("orientationchange", syncLandscapeClass);
      document.body.classList.remove("personal-quiz-mobile-landscape");
      try {
        window.screen?.orientation?.unlock?.();
      } catch {
        // Some browsers do not expose orientation unlock.
      }
    };
  }, [activeQuiz, quizSource, result]);

  const selectAnswer = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const clearAnswer = (questionId) => {
    setAnswers((prev) => {
      const next = { ...prev };
      delete next[questionId];
      return next;
    });
  };

  const handleFlagCurrentQuestion = async (event) => {
    event.preventDefault();
    if (!activeQuiz || !currentQuestion || result) return;
    if (flagCount >= 2) {
      setFlagStatus({ busy: false, error: "You can only flag 2 questions in this quiz.", success: "" });
      setFlagModalOpen(false);
      return;
    }
    const reason = flagReason.trim();
    if (!reason) {
      setFlagStatus({ busy: false, error: "Please describe why this question is inappropriate.", success: "" });
      return;
    }

    const isTeacherQuiz = quizSource === "teacher";
    setFlagStatus({ busy: true, error: "", success: "" });
    try {
      const response = await requestJson(
        session,
        "POST",
        isTeacherQuiz ? `/api/quizzes/student/${activeQuiz.id}/flag-question/` : `/api/quizzes/personal/${activeQuiz.id}/flag-question/`,
        {
          question_id: currentQuestion.id,
          answer: answers[currentQuestion.id],
          reason,
        }
      );
      setFlagReason("");
      setFlagModalOpen(false);
      setFlagCount((count) => count + 1);
      setFlagStatus({ busy: false, error: "", success: response.message || "Question report sent." });
    } catch (reportError) {
      setFlagStatus({ busy: false, error: reportError.message || "Could not send the question report.", success: "" });
    }
  };

  const handleSubmit = async (autoSubmitted = false) => {
    if (!activeQuiz || result) return;
    const shouldAutoSubmit = autoSubmitted === true;

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const isTeacherQuiz = quizSource === "teacher";
    const payload = isTeacherQuiz
      ? {
          answers: Object.entries(answers).map(([question, choice]) => ({
            question: Number(question),
            choice: Number(choice),
          })),
        }
      : {
          answers: Object.entries(answers).map(([question, answer]) => ({
            question: Number(question),
            answer,
          })),
          auto_submitted: shouldAutoSubmit,
        };

    setLoading(true);
    setError("");
    try {
      const submission = await requestJson(
        session,
        "POST",
        isTeacherQuiz ? `/api/quizzes/student/${activeQuiz.id}/submit/` : `/api/quizzes/personal/${activeQuiz.id}/submit/`,
        payload
      );
      setResult({ ...submission, source: quizSource, title: activeQuiz.title, subject: activeQuiz.subject || activeQuiz.description });
      setActiveQuiz((prev) => ({ ...prev, ...submission }));
      setTimeLeft(0);
      if (!isTeacherQuiz) {
        const history = await requestJson(session, "GET", "/api/quizzes/personal/history/");
        setOptions((prev) => ({ ...prev, history: history.history || [], stats: history.stats || prev.stats }));
      }
    } catch (submitError) {
      setError(submitError.message || "Could not submit quiz.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (timeLeft === 0 && activeQuiz && !result) {
      handleSubmit(true);
    }
  }, [timeLeft, activeQuiz, result]);

  const answeredCount = Object.keys(answers).length;
  const totalQuestions = activeQuiz?.questions?.length || 0;
  const currentQuestion = activeQuiz?.questions?.[currentQuestionIndex] || null;
  const studentName = userDisplayName(session?.user);
  const studentId = session?.user?.student_id || session?.user?.admission_number || session?.user?.username || session?.user?.email || "Student";
  const studentInitials = userInitials(session?.user);
  const studentAvatar = session?.user?.profile_picture || "";
  const stats = options.stats || {};
  const metrics = options.metrics || {};
  const weeklyStreak = metrics.weekly_streak || {};
  const monthlyMetrics = metrics.monthly || {};
  const termMetrics = metrics.term || {};
  const activeMetricsTerm = metrics.active_term || {};
  const subjectMetrics = monthlyMetrics.subjects || [];
  const progressTrends = monthlyMetrics.progress_trends || [];
  const termHistory = termMetrics.history || [];
  const history = options.history || [];
  const visiblePersonalHistory = showAllPersonalHistory ? history : history.slice(0, 3);
  const hasMorePersonalHistory = history.length > 3;
  const dailySubjects = options.subjects || [];

  const renderQuizText = (value) => <RichQuizText text={value} />;

  const formatTime = (seconds) => {
    if (seconds === null || seconds === undefined) return "--:--";
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60)
      .toString()
      .padStart(2, "0");
    const secs = (seconds % 60).toString().padStart(2, "0");
    return hours > 0 ? `${String(hours).padStart(2, "0")}:${mins}:${secs}` : `${mins}:${secs}`;
  };

  const goToQuestion = (index) => {
    if (index < 0 || index >= totalQuestions) {
      return;
    }
    setCurrentQuestionIndex(index);
  };

  const saveAndNext = () => {
    if (currentQuestionIndex < totalQuestions - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    }
  };

  const renderQuestionInput = (question, currentAnswer) => {
    if (quizSource === "teacher") {
      return (
        <div className="cbt-options">
          {(question.choices || []).map((choice, index) => {
            const selected = Number(currentAnswer) === choice.id;
            return (
              <label key={choice.id} className={`cbt-option ${selected ? "selected" : ""}`}>
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  checked={selected}
                  onChange={() => selectAnswer(question.id, choice.id)}
                />
                <span className="cbt-radio" aria-hidden="true" />
                <span className="cbt-option-text">
                  {String.fromCharCode(65 + index)}. {renderQuizText(choice.text)}
                </span>
              </label>
            );
          })}
        </div>
      );
    }

    if (question.question_type === "fill_blank") {
      return (
        <input
          className="personal-fill-input"
          value={currentAnswer || ""}
          onChange={(event) => selectAnswer(question.id, event.target.value)}
          placeholder="Type your answer"
          disabled={!!result}
        />
      );
    }

    const optionsList = question.question_type === "true_false" ? ["True", "False"] : question.options || [];
    return (
      <div className="cbt-options">
        {optionsList.map((option, index) => {
          const selected = currentAnswer === option;
          return (
            <label key={option} className={`cbt-option ${selected ? "selected" : ""}`}>
              <input
                type="radio"
                name={`question-${question.id}`}
                checked={selected}
                onChange={() => selectAnswer(question.id, option)}
                disabled={!!result}
              />
              <span className="cbt-radio" aria-hidden="true" />
              <span className="cbt-option-text">
                {question.question_type === "objective" ? `${String.fromCharCode(65 + index)}. ` : ""}{renderQuizText(option)}
              </span>
            </label>
          );
        })}
      </div>
    );
  };

  if (activeQuiz) {
    const currentAnswer = currentQuestion ? answers[currentQuestion.id] : undefined;
    const questionTitle = activeQuiz.title || "Personal Quiz";

    if (result) {
      const resultPercentage =
        result.percentage !== undefined
          ? result.percentage
          : Math.round((Number(result.score || 0) / Math.max(Number(result.total_points || 0), 1)) * 100);
      return (
        <section className="personal-score-page">
          <header className="personal-score-hero">
            <div>
              <p className="quiz-kicker">Quiz completed</p>
              <h1>Your Score</h1>
              <p>{result.subject || activeQuiz.subject || "Teacher Quiz"} - {result.class_group || activeQuiz.class_group || "Assessment"}</p>
            </div>
            <div className="personal-score-ring">
              <strong>{resultPercentage || 0}%</strong>
              <span>{result.score} / {result.total_points}</span>
            </div>
          </header>

          <section className="personal-score-actions">
            <button type="button" className="pill-button ghost" onClick={() => onNavigate?.("/dashboard")}>
              Back to dashboard
            </button>
            <button
              type="button"
              className="pill-button"
              onClick={() => {
                setActiveQuiz(null);
                setResult(null);
                setAnswers({});
                loadPersonalQuizData();
              }}
            >
              Back to daily task
            </button>
          </section>

          <section className="personal-score-review">
            <div className="quiz-list-head">
              <div>
                <p className="quiz-kicker">Answer review</p>
                <h3>Question breakdown</h3>
              </div>
              <span className="pill success">Submitted {formatDate(result.submitted_at)}</span>
            </div>
            {result.source === "teacher"
              ? result.answers?.map((answer, index) => (
                  <article key={answer.question_id} className={`personal-review-card ${answer.is_correct ? "correct" : "wrong"}`}>
                    <div>
                      <p className="quiz-kicker">Question {index + 1}</p>
                      <h4>{renderQuizText(answer.question)}</h4>
                    </div>
                    <p>
                      Your answer: <strong>{renderQuizText(answer.selected_choice || "No answer")}</strong>
                      <br />
                      Correct answer: <strong>{renderQuizText(answer.correct_choices?.map((choice) => choice.text).join(", ") || "-")}</strong>
                    </p>
                    {answer.explanation ? <small>{answer.explanation}</small> : null}
                  </article>
                ))
              : result.questions?.map((question) => (
                  <article key={question.id} className={`personal-review-card ${question.is_correct ? "correct" : "wrong"}`}>
                    <div>
                      <p className="quiz-kicker">Question {question.order}</p>
                      <h4>{renderQuizText(question.prompt)}</h4>
                    </div>
                    <p>
                      Your answer: <strong>{renderQuizText(question.answer_text || "No answer")}</strong>
                      <br />
                      Correct answer: <strong>{renderQuizText(question.correct_answer)}</strong>
                    </p>
                    <small>{renderQuizText(question.explanation)}</small>
                  </article>
                ))}
          </section>
        </section>
      );
    }

    return (
      <section className={`cbt-page ${quizSource === "personal" ? "personal-cbt-page" : "teacher-cbt-page"}`}>
        <header className="cbt-topbar">
          <div className="cbt-brand">
            <span className="cbt-monitor-icon" aria-hidden="true">
              <span />
            </span>
            <strong>QUIZZES</strong>
          </div>
          <h1>{questionTitle}</h1>
          <div className="cbt-top-actions">
            <div className="cbt-student-identity">
              <div className="cbt-student-avatar">
                {studentAvatar ? <img src={studentAvatar} alt={studentName} /> : <span>{studentInitials}</span>}
              </div>
              <div>
                <strong>{studentName}</strong>
                <span>{studentId}</span>
              </div>
            </div>
            <div className="cbt-time">
              <span className="cbt-clock" aria-hidden="true" />
              <span>Time Left</span>
              <strong>{timeLeft !== null ? formatTime(timeLeft) : "N/A"}</strong>
            </div>
          </div>
        </header>

        <div className="cbt-shell">
          <aside className="cbt-leftnav">
            <p>Test Navigation</p>
            <button type="button" onClick={() => setInstructionsOpen(true)}>
              <span aria-hidden="true">I</span>
              Instructions
            </button>
            <button type="button" className="active">
              <span aria-hidden="true">Q</span>
              Questions
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveQuiz(null);
                setResult(null);
                setAnswers({});
                setFlagModalOpen(false);
                setInstructionsOpen(false);
                setFlagStatus({ busy: false, error: "", success: "" });
                setFlagCount(0);
                loadPersonalQuizData();
              }}
            >
              <span aria-hidden="true">B</span>
              Back to List
            </button>
            <button
              type="button"
              className="cbt-leftnav-flag"
              onClick={() => {
                if (flagCount >= 2) {
                  setFlagStatus({ busy: false, error: "You can only flag 2 questions in this quiz.", success: "" });
                  return;
                }
                setFlagReason("");
                setFlagStatus({ busy: false, error: "", success: "" });
                setFlagModalOpen(true);
              }}
              disabled={!currentQuestion || !!result || flagCount >= 2}
            >
              <span aria-hidden="true">!</span>
              Flag Inappropriate ({flagCount}/2)
            </button>
          </aside>

          <main className="cbt-main">
            <div className="cbt-question-meta">
              <p>
                Section: <strong>{activeQuiz.subject || "Personal Quiz"}</strong>
              </p>
              <p>Question {Math.min(currentQuestionIndex + 1, Math.max(totalQuestions, 1))} of {totalQuestions}</p>
            </div>
            <div className="cbt-feedback-slot">
              {error ? <p className="form-feedback error">{error}</p> : null}
              {flagStatus.error ? <p className="form-feedback error">{flagStatus.error}</p> : null}
              {flagStatus.success ? <p className="form-feedback success">{flagStatus.success}</p> : null}
              {screenSecurityWarning ? <p className="form-feedback error">{screenSecurityWarning}</p> : null}
            </div>

            <section className="cbt-question-panel">
              {currentQuestion ? (
                <>
                  <h2>{renderQuizText(currentQuestion.prompt || currentQuestion.text)}</h2>
                  <p className="personal-question-type">{quizSource === "teacher" ? "teacher quiz" : currentQuestion.question_type?.replace("_", " ")}</p>
                  {renderQuestionInput(currentQuestion, currentAnswer)}
                  <button
                    type="button"
                    className="cbt-clear-btn"
                    onClick={() => clearAnswer(currentQuestion.id)}
                    disabled={currentAnswer === undefined || !!result}
                  >
                    Clear Response
                  </button>
                </>
              ) : (
                <p className="panel-empty">No questions are available for this test.</p>
              )}
            </section>

            <footer className="cbt-footer">
              <button
                type="button"
                className="cbt-secondary-btn"
                onClick={() => goToQuestion(currentQuestionIndex - 1)}
                disabled={currentQuestionIndex === 0}
              >
                Previous
              </button>
              <button
                type="button"
                className="cbt-primary-btn"
                onClick={saveAndNext}
                disabled={currentQuestionIndex >= totalQuestions - 1}
              >
                Save & Next
              </button>
              <button
                type="button"
                className="cbt-submit-btn footer-submit"
                onClick={() => handleSubmit(false)}
                disabled={loading || totalQuestions === 0}
              >
                {loading ? "Submitting..." : "Submit Test"}
              </button>
            </footer>
          </main>

          <aside className="cbt-rightbar">
            <div className="cbt-question-map">
              {activeQuiz.questions.map((question, index) => {
                const isAnswered = answers[question.id] !== undefined;
                const isCurrent = index === currentQuestionIndex;
                return (
                  <button
                    type="button"
                    key={question.id}
                    className={`${isAnswered ? "answered" : ""} ${isCurrent ? "current" : ""}`}
                    onClick={() => goToQuestion(index)}
                  >
                    {index + 1}
                  </button>
                );
              })}
            </div>
          </aside>
        </div>
        {flagModalOpen ? (
          <div className="cbt-flag-modal" role="dialog" aria-modal="true" aria-labelledby="cbt-flag-title">
            <form className="cbt-flag-card" onSubmit={handleFlagCurrentQuestion}>
              <h3 id="cbt-flag-title">Flag inappropriate question</h3>
              <p>Describe what is inappropriate or wrong with question {currentQuestionIndex + 1}.</p>
              <textarea
                value={flagReason}
                onChange={(event) => setFlagReason(event.target.value)}
                maxLength={2000}
                required
                autoFocus
              />
              {flagStatus.error ? <p className="form-feedback error">{flagStatus.error}</p> : null}
              <div className="cbt-flag-actions">
                <button type="button" onClick={() => setFlagModalOpen(false)} disabled={flagStatus.busy}>
                  Cancel
                </button>
                <button type="submit" disabled={flagStatus.busy || !flagReason.trim()}>
                  {flagStatus.busy ? "Sending..." : "Send report"}
                </button>
              </div>
            </form>
          </div>
        ) : null}
        {instructionsOpen ? (
          <div className="cbt-info-modal" role="dialog" aria-modal="true" aria-labelledby="cbt-instructions-title">
            <div className="cbt-info-card">
              <p className="cbt-info-kicker">Test instructions</p>
              <h3 id="cbt-instructions-title">Before you continue</h3>
              <p>{activeQuiz.description || "Read each question carefully before answering."}</p>
              <button type="button" onClick={() => setInstructionsOpen(false)}>
                Continue Test
              </button>
            </div>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className="quiz-layout personal-quiz-layout">
      <header className="quiz-hero personal-quiz-hero">
        <div>
          <p className="quiz-kicker">Daily Personal Quiz</p>
          <h1>Private daily practice</h1>
          <p>Optional subject quizzes from your registered subjects. Each subject opens once per day with a fixed 15-minute timer.</p>
        </div>
        <div className="quiz-actions">
          <button type="button" className="pill-button ghost" onClick={() => onNavigate?.("/dashboard")}>
            Back to dashboard
          </button>
        </div>
      </header>

      {error ? <p className="form-feedback error">{error}</p> : null}

      <section className="personal-stats-grid">
        {[
          ["Attempts", stats.attempts || 0],
          ["Submitted", stats.submitted || 0],
          ["Average", `${stats.average_percentage || 0}%`],
          ["Best score", `${stats.best_percentage || 0}%`],
          ["Weekly streak", `${stats.weekly_streak ?? weeklyStreak.current ?? 0} days`],
          ["Today", `${stats.completed_today || 0}/${stats.total_subjects || dailySubjects.length}`],
        ].map(([label, value]) => (
          <article key={label} className="personal-stat-card">
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className="personal-metrics-dashboard">
        <article className="personal-chart-card personal-month-card">
          <div className="personal-dashboard-head">
            <div>
              <p className="quiz-kicker">Monthly dashboard</p>
              <h3>{formatDate(monthlyMetrics.month_start) || "This month"}</h3>
            </div>
            <span className="pill muted">{activeMetricsTerm.name || "Current term"}</span>
          </div>
          <div className="personal-metric-strip">
            <div>
              <span>Total completed</span>
              <strong>{monthlyMetrics.total_completed || 0}</strong>
            </div>
            <div>
              <span>Overall average</span>
              <strong>{monthlyMetrics.overall_average_percentage || 0}%</strong>
            </div>
            <div>
              <span>Week streak</span>
              <strong>{weeklyStreak.current || 0} days</strong>
            </div>
          </div>
          <div className="personal-subject-metrics">
            {subjectMetrics.length ? subjectMetrics.map((subject) => (
              <div key={subject.subject_id || subject.subject} className="personal-subject-metric-row">
                <span>{subject.subject}</span>
                <div className="personal-chart-track">
                  <div style={{ width: `${Math.max(4, subject.average_percentage || 0)}%` }} />
                </div>
                <strong>{subject.average_percentage || 0}%</strong>
                <small>{subject.completed} quiz{Number(subject.completed) === 1 ? "" : "zes"}</small>
              </div>
            )) : <p className="panel-empty">Subject-by-subject metrics will appear after this month’s first submitted quiz.</p>}
          </div>
        </article>

        <article className="personal-chart-card">
          <div>
            <p className="quiz-kicker">Strengths & focus</p>
            <h3>Performance tracking</h3>
          </div>
          <div className="personal-rank-grid">
            <div>
              <span>Highest scoring</span>
              {(monthlyMetrics.highest_subjects || []).length ? monthlyMetrics.highest_subjects.map((subject) => (
                <p key={`high-${subject.subject_id || subject.subject}`}><strong>{subject.subject}</strong> {subject.average_percentage}%</p>
              )) : <p>No high-score records yet.</p>}
            </div>
            <div>
              <span>Weakest subjects</span>
              {(monthlyMetrics.weakest_subjects || []).length ? monthlyMetrics.weakest_subjects.map((subject) => (
                <p key={`weak-${subject.subject_id || subject.subject}`}><strong>{subject.subject}</strong> {subject.average_percentage}%</p>
              )) : <p>No weak-subject records yet.</p>}
            </div>
          </div>
          <div className="personal-trend-list">
            {progressTrends.length ? progressTrends.map((trend) => (
              <div key={trend.label} className="personal-trend-row">
                <span>{trend.label}</span>
                <div className="personal-chart-track">
                  <div style={{ width: `${Math.max(4, trend.average_percentage || 0)}%` }} />
                </div>
                <strong>{trend.average_percentage || 0}%</strong>
              </div>
            )) : <p className="panel-empty">Monthly progress trends will appear as you complete more quizzes.</p>}
          </div>
        </article>

        <article className="personal-chart-card personal-term-card">
          <div>
            <p className="quiz-kicker">Term archive</p>
            <h3>{termMetrics.total_completed || 0} quizzes this term</h3>
          </div>
          <div className="personal-term-list">
            {termHistory.length ? termHistory.map((term) => (
              <div key={term.term_id || term.term} className={term.is_active ? "active" : ""}>
                <span>{term.term}</span>
                <strong>{term.average_percentage || 0}%</strong>
                <small>{term.completed} completed {term.archived ? "archived" : "current"}</small>
              </div>
            )) : <p className="panel-empty">Past term records will stay here after each term changes.</p>}
          </div>
        </article>
      </section>

      <section className="personal-quiz-workspace">
        <form className="personal-generator" onSubmit={(event) => { event.preventDefault(); generateQuiz(); }}>
          <div>
            <p className="quiz-kicker">Daily task</p>
            <h3>{options.class_group?.name || "Your class"}</h3>
          </div>
          <div className="daily-task-card">
            <div className="daily-task-card-count">
              <strong>{DAILY_PERSONAL_QUESTION_LIMIT}</strong>
              <span>questions</span>
            </div>
            <div>
              <h4>Fixed daily challenge</h4>
              <p>Pick a subject and complete the full task. Your score and correct answers appear immediately after submission.</p>
            </div>
          </div>
          <label>
            Subject
            <select value={selectedSubject} onChange={(event) => setSelectedSubject(event.target.value)} disabled={loading || !options.subjects?.length}>
              {(options.subjects || []).map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name} - {subject.today_status === "unavailable" ? "no questions yet" : subject.today_status?.replace("_", " ") || "available"}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="pill-button" disabled={generating || loading || !selectedSubject}>
            {generating ? "Opening..." : "Start selected subject"}
          </button>
        </form>

        <article className="personal-chart-card daily-subject-card">
          <div>
            <p className="quiz-kicker">Today's subjects</p>
            <h3>{dailySubjects.length || 0} registered subjects</h3>
          </div>
          <div className="daily-subject-list">
            {dailySubjects.length ? dailySubjects.map((subject) => (
              <div key={subject.id} className={`daily-subject-row status-${subject.today_status || "available"}`}>
                <div>
                  <strong>{subject.name}</strong>
                  <small>
                    {subject.code || "Subject"} - {subject.today_status === "unavailable" ? "no questions yet" : (subject.today_status || "available").replace("_", " ")}
                  </small>
                </div>
                <button
                  type="button"
                  className="pill-button ghost"
                  disabled={generating || subject.today_status === "completed" || subject.today_status === "unavailable"}
                  onClick={() => {
                    setSelectedSubject(String(subject.id));
                    generateQuiz(subject.id);
                  }}
                >
                  {subject.today_status === "completed" ? "Done today" : subject.today_status === "in_progress" ? "Resume" : subject.today_status === "unavailable" ? "No questions" : "Start"}
                </button>
              </div>
            )) : <p className="panel-empty">No registered subjects found for your class.</p>}
          </div>
        </article>
      </section>

      <section className="quiz-list-section teacher-quiz-section">
        <div className="quiz-list-head">
          <div>
            <p className="quiz-kicker">Class Test</p>
            <h3>Available Tests.</h3>
          </div>
          <span className="pill muted">{teacherQuizzes.length} available</span>
        </div>
        {teacherQuizzes.length === 0 ? (
          <p className="panel-empty">No teacher-published tests are available yet.</p>
        ) : (
          <div className="quiz-grid">
            {teacherQuizzes.map((quiz) => (
              <article key={quiz.id} className="quiz-card teacher-quiz-card">
                <div className="quiz-card-head">
                  <div>
                    <p className="quiz-kicker">{quiz.allow_multiple_attempts ? "Multiple attempts" : "Single attempt"}</p>
                    <h4>{quiz.title}</h4>
                    <small>{quiz.description || "Teacher assessment"}</small>
                  </div>
                  <button type="button" className="pill-button ghost" onClick={() => startTeacherQuiz(quiz.id)}>
                    Start
                  </button>
                </div>
                <div className="quiz-card-meta">
                  <span>{quiz.questions?.length || 0} questions</span>
                  <span>{quiz.time_limit_minutes ? `${quiz.time_limit_minutes} mins` : "No timer"}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="quiz-list-section personal-history-section">
        <div className="quiz-list-head">
          <div>
            <p className="quiz-kicker">Quiz history</p>
            <h3>Recent attempts</h3>
          </div>
          <span className="pill muted">{visiblePersonalHistory.length} of {history.length} shown</span>
        </div>
        {loading ? (
          <p className="panel-empty">Loading quiz history...</p>
        ) : history.length === 0 ? (
          <p className="panel-empty">No personal quiz attempts yet.</p>
        ) : (
          <div className="personal-history-table">
            <div className="personal-history-head">
              <span>Subject</span>
              <span>Class</span>
              <span>Score</span>
              <span>Status</span>
              <span>Date</span>
            </div>
            {visiblePersonalHistory.map((attempt) => (
              <div key={attempt.id} className="personal-history-row">
                <span>{attempt.subject || "Personal quiz"}</span>
                <span>{attempt.class_group}</span>
                <span>{attempt.score} / {attempt.total_points} ({attempt.percentage || 0}%)</span>
                <span className={`pill ${attempt.is_submitted ? "success" : "muted"}`}>{attempt.is_submitted ? "Submitted" : "In progress"}</span>
                <span>{formatDate(attempt.submitted_at || attempt.started_at)}</span>
              </div>
            ))}
            {hasMorePersonalHistory ? (
              <div className="personal-history-actions">
                <button
                  type="button"
                  className="pill-button ghost"
                  onClick={() => setShowAllPersonalHistory((current) => !current)}
                >
                  {showAllPersonalHistory ? "Show less" : `More (${history.length - 3})`}
                </button>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </section>
  );
}

function QuizHub({ session, onNavigate }) {
  const role = session?.user?.role || "";
  const isTeacherLike = role === "teacher" || role === "school_admin" || role === "principal";

  return isTeacherLike ? (
    <TeacherQuizPage session={session} onNavigate={onNavigate} />
  ) : (
    <StudentQuizPage session={session} onNavigate={onNavigate} />
  );
}

function schoolTypeFromSession(session, data = {}) {
  return (
    data?.school?.school_type ||
    data?.school?.schoolType ||
    session?.school?.school_type ||
    session?.school?.schoolType ||
    "k12"
  );
}

function isNonK12School(session, data = {}) {
  return schoolTypeFromSession(session, data) === "non_k12";
}

function TeacherPlanningPanel({ session, onNavigate, standalone = false }) {
  const [planning, setPlanning] = useState(null);
  const [notes, setNotes] = useState([]);
  const [form, setForm] = useState({ class_id: "", subject_id: "", week_number: 1, title: "", objectives: "", activities: "", resources: "", assessment: "", notes: "", status: "planned" });
  const [noteForm, setNoteForm] = useState({ title: "Quick note", body: "", pinned: false });
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const nonK12 = isNonK12School(session, planning);
  const planningTitle = nonK12 ? "Course Outline & Notepad" : "Lesson Plans & Notepad";
  const planningItemLabel = nonK12 ? "Course outline" : "Lesson plan";

  const loadPlanning = useCallback(async () => {
    setError("");
    try {
      const [planResponse, noteResponse] = await Promise.all([
        requestJson(session, "GET", "/api/app/academic/planning/"),
        requestJson(session, "GET", "/api/app/academic/notes/"),
      ]);
      setPlanning(planResponse || {});
      setNotes(noteResponse?.notes || []);
      const classes = planResponse?.options?.classes || [];
      const subjects = planResponse?.options?.subjects || [];
      setForm((prev) => ({
        ...prev,
        class_id: prev.class_id || (classes[0]?.id ? String(classes[0].id) : ""),
        subject_id: prev.subject_id || (subjects[0]?.id ? String(subjects[0].id) : ""),
      }));
    } catch (loadError) {
      setError(loadError.message || "Could not load academic planning.");
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      loadPlanning();
    }
  }, [loadPlanning, session]);

  const handlePlanSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setError("");
    try {
      await requestJson(session, "POST", "/api/app/academic/planning/", {
        ...form,
        class_id: Number(form.class_id),
        subject_id: Number(form.subject_id),
        week_number: Number(form.week_number || 1),
      });
      setFeedback(`${planningItemLabel} saved and aligned with the active term.`);
      setForm((prev) => ({ ...prev, title: "", objectives: "", activities: "", resources: "", assessment: "", notes: "" }));
      await loadPlanning();
    } catch (saveError) {
      setError(saveError.message || `Could not save ${planningItemLabel.toLowerCase()}.`);
    }
  };

  const handleNoteSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setError("");
    try {
      await requestJson(session, "POST", "/api/app/academic/notes/", noteForm);
      setFeedback("Note saved.");
      setNoteForm({ title: "Quick note", body: "", pinned: false });
      await loadPlanning();
    } catch (saveError) {
      setError(saveError.message || "Could not save note.");
    }
  };

  const plans = planning?.lesson_plans || [];
  const classes = planning?.options?.classes || [];
  const subjects = planning?.options?.subjects || [];

  return (
    <section className={standalone ? "academic-page" : ""}>
      {standalone ? (
        <header className="academic-page-hero">
          <div>
            <p className="quiz-kicker">Teacher workspace</p>
            <h1>{planningTitle}</h1>
            <p>{nonK12 ? "Create course outlines and keep quick academic notes." : "Create weekly scheme-of-work plans and keep quick academic notes."}</p>
          </div>
          <button type="button" className="pill-button ghost" onClick={() => onNavigate?.("/dashboard")}>
            Back to dashboard
          </button>
        </header>
      ) : null}
    <article className="app-panel academic-planning-panel">
      <div className="panel-head">
        <div>
          <h3>{planningTitle}</h3>
          <small>{planning?.active_term?.name || "Active term"} - {planning?.active_year?.name || "Academic year"}</small>
        </div>
        <span className="pill">Week {planning?.progress?.latest_week || 0}</span>
      </div>
      {error ? <p className="form-feedback error">{error}</p> : null}
      {feedback ? <p className="form-feedback success">{feedback}</p> : null}
      <div className="academic-planning-grid">
        <form className="panel-form" onSubmit={handlePlanSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Class
              <select value={form.class_id} onChange={(event) => setForm((prev) => ({ ...prev, class_id: event.target.value }))} required>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="panel-field">
              Subject
              <select value={form.subject_id} onChange={(event) => setForm((prev) => ({ ...prev, subject_id: event.target.value }))} required>
                {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="panel-field">
              Week
              <input type="number" min="1" max="20" value={form.week_number} onChange={(event) => setForm((prev) => ({ ...prev, week_number: event.target.value }))} />
            </label>
            <label className="panel-field">
              Status
              <select value={form.status} onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value }))}>
                <option value="planned">Planned</option>
                <option value="completed">Completed</option>
                <option value="draft">Draft</option>
              </select>
            </label>
            <label className="panel-field full">
              {nonK12 ? "Course topic / outline" : "Topic / Scheme of work"}
              <input value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} required />
            </label>
            <label className="panel-field full">
              Objectives
              <FormattedTextarea value={form.objectives} onChange={(event) => setForm((prev) => ({ ...prev, objectives: event.target.value }))} rows={2} />
            </label>
            <label className="panel-field full">
              Activities
              <FormattedTextarea value={form.activities} onChange={(event) => setForm((prev) => ({ ...prev, activities: event.target.value }))} rows={2} />
            </label>
          </div>
          <div className="panel-form-actions"><button type="submit">Save {planningItemLabel.toLowerCase()}</button></div>
        </form>
        <form className="panel-form note-pad-form" onSubmit={handleNoteSubmit}>
          <label className="panel-field">
            Note title
            <input value={noteForm.title} onChange={(event) => setNoteForm((prev) => ({ ...prev, title: event.target.value }))} />
          </label>
          <label className="panel-field full">
            Digital notepad
            <FormattedTextarea value={noteForm.body} onChange={(event) => setNoteForm((prev) => ({ ...prev, body: event.target.value }))} rows={8} placeholder="Write lesson ideas, reminders, or quick academic notes..." />
          </label>
          <label className="panel-field checkbox-field">
            <input type="checkbox" checked={noteForm.pinned} onChange={(event) => setNoteForm((prev) => ({ ...prev, pinned: event.target.checked }))} />
            Pin note
          </label>
          <div className="panel-form-actions"><button type="submit">Save note</button></div>
        </form>
      </div>
      <div className="scheme-subject-grid">
        {plans.map((plan) => (
          <article key={plan.id} className="scheme-subject-card">
            <button type="button" className="scheme-plan-card-button" onClick={() => setSelectedPlan(plan)}>
              <h4>Week {plan.week_number}: {plan.title}</h4>
              <p>{plan.subject} - {plan.class_name}</p>
              <small>{plan.status}</small>
            </button>
          </article>
        ))}
        {notes.slice(0, 3).map((note) => (
          <article key={note.id} className="scheme-subject-card note-card">
            <h4>{note.title}</h4>
            <p><RichQuizText text={note.body || "No note content."} /></p>
            <small>{note.pinned ? "Pinned" : "Note"}</small>
          </article>
        ))}
      </div>
    </article>
    <LessonPlanDetailDialog plan={selectedPlan} onClose={() => setSelectedPlan(null)} title={planningItemLabel} />
    </section>
  );
}

function StaffSelfServicePanel({ session, initialData = null, standalone = false, showAttendance = true, onRefresh }) {
  const [snapshot, setSnapshot] = useState(initialData || null);
  const [profileForm, setProfileForm] = useState({
    phone: "",
    gender: "",
    date_of_birth: "",
    address: "",
    emergency_contact_name: "",
    emergency_contact_phone: "",
    emergency_contact_relation: "",
    profile_picture: null,
    cv: null,
  });
  const [leaveForm, setLeaveForm] = useState({ leave_type: "Annual", start_date: "", end_date: "", reason: "" });
  const [advanceForm, setAdvanceForm] = useState({ amount: "", reason: "" });
  const [messageData, setMessageData] = useState({ inbox: [], recipients: [] });
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const formatMoney = (value) => `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString()}`;

  useEffect(() => {
    if (initialData) {
      setSnapshot(initialData);
    }
  }, [initialData]);

  useEffect(() => {
    const staff = snapshot?.staff;
    if (!staff) return;
    setProfileForm((prev) => ({
      ...prev,
      phone: staff.phone || "",
      gender: staff.gender || "",
      date_of_birth: String(staff.date_of_birth || "").slice(0, 10),
      address: staff.address || "",
      emergency_contact_name: staff.emergency_contact_name || "",
      emergency_contact_phone: staff.emergency_contact_phone || "",
      emergency_contact_relation: staff.emergency_contact_relation || "",
      profile_picture: null,
      cv: null,
    }));
  }, [snapshot?.staff]);

  const loadSelfService = useCallback(async () => {
    if (!session) return null;
    const result = await requestJson(session, "GET", "/api/hr/me/");
    setSnapshot(result);
    return result;
  }, [session]);

  const loadMessages = useCallback(async () => {
    if (!session) return null;
    const result = await requestJson(session, "GET", "/api/app/messages/");
    setMessageData(result || { inbox: [], recipients: [] });
    return result;
  }, [session]);

  useEffect(() => {
    if (!initialData && session) {
      loadSelfService().catch((loadError) => setError(loadError.message || "Could not load staff requests."));
    }
  }, [initialData, loadSelfService, session]);

  useEffect(() => {
    if (!session) return undefined;
    loadMessages().catch(() => {});
    const pollId = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadMessages().catch(() => {});
      }
    }, MESSAGE_POLL_INTERVAL_MS);
    return () => window.clearInterval(pollId);
  }, [loadMessages, session]);

  const runAction = async (key, action, reset) => {
    setBusy(key);
    setFeedback("");
    setError("");
    try {
      const result = await action();
      setFeedback(result?.message || "Request sent.");
      reset?.();
      await loadSelfService();
      await onRefresh?.();
    } catch (actionError) {
      setError(actionError.message || "Could not send request.");
    } finally {
      setBusy("");
    }
  };

  const handleLeaveSubmit = (event) => {
    event.preventDefault();
    runAction(
      "leave",
      () => postJson(session, "/api/hr/leave/create/", leaveForm),
      () => setLeaveForm((prev) => ({ ...prev, start_date: "", end_date: "", reason: "" }))
    );
  };

  const handleAdvanceSubmit = (event) => {
    event.preventDefault();
    runAction(
      "advance",
      () => postJson(session, "/api/hr/advances/create/", advanceForm),
      () => setAdvanceForm({ amount: "", reason: "" })
    );
  };

  const handleProfileSubmit = (event) => {
    event.preventDefault();
    const formData = new FormData();
    Object.entries(profileForm).forEach(([key, value]) => {
      if (key === "cv" || key === "profile_picture") {
        if (value) formData.append(key, value);
        return;
      }
      formData.append(key, value || "");
    });
    runAction(
      "profile",
      () => requestJson(session, "PATCH", "/api/hr/me/", formData),
      () => setProfileForm((prev) => ({ ...prev, profile_picture: null, cv: null }))
    );
  };

  const staff = snapshot?.staff || {};
  const leaves = snapshot?.leaves || [];
  const advances = snapshot?.advances || [];
  const payroll = snapshot?.payroll || [];
  const attendance = snapshot?.attendance || [];
  const staffRecipientOptions = filterRecipientsForRole(messageData?.recipients || [], session?.user)
    .filter((contact) => contact?.email)
    .map((contact) => ({
      value: contact.email,
      label: `${contact.name || contact.email} - ${roleLabel(contact.role) || "Contact"}`,
    }));

  const handleStaffMessageSend = async (recipientValue, subject, body, _selectedRecipient, attachments = []) => {
    await postJson(session, "/api/app/messages/send/", {
      recipient_email: recipientValue,
      subject,
      body,
      attachments,
    });
    await loadMessages();
  };

  const handleStaffMessageRead = async (messageId) => {
    await requestJson(session, "POST", `/api/app/messages/${messageId}/read/`);
    await loadMessages();
  };

  const handleStaffMessageDelete = async (messageId) => {
    await requestJson(session, "DELETE", `/api/app/messages/${messageId}/`);
    await loadMessages();
  };

  return (
    <section className={`screen-grid ${standalone ? "staff-self-service-page" : ""}`}>
      {standalone ? (
        <div className="screen-hero">
          <h2>Staff Self-Service</h2>
          <p>Request leave, request salary advances, review attendance history, and message your school team.</p>
        </div>
      ) : null}

      <section className="metric-grid staff-metric-grid">
        <MetricCard label="Staff ID" value={staff.staff_code || "-"} trend={staff.role || "Staff profile"} icon="id" tone="blue" />
        <MetricCard label="Salary Balance" value={formatMoney(staff.salary_balance)} trend="Current HR balance" icon="money" tone="emerald" />
        <MetricCard label="Pending Leave" value={snapshot?.summary?.pending_leaves ?? 0} trend="Awaiting review" icon="calendar" tone="amber" />
        <MetricCard label="Pending Advances" value={snapshot?.summary?.pending_advances ?? 0} trend="Awaiting review" icon="requests" tone="rose" />
      </section>

      {(feedback || error) ? (
        <article className="app-panel">
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {error ? <p className="form-feedback error">{error}</p> : null}
        </article>
      ) : null}

      <article className="app-panel">
        <div className="panel-head">
          <div>
            <h3>My profile</h3>
            <small>Update biodata, profile picture, next of kin, and CV.</small>
          </div>
          <button type="button" className="table-action" onClick={() => setProfileOpen(true)}>
            Edit biodata
          </button>
        </div>
      </article>

      <EditableStaffBioProfile
        session={session}
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        onSaved={async () => {
          await loadSelfService();
          await onRefresh?.();
        }}
        fallbackProfile={staff}
        title="Staff profile"
        subtitle="Editable biodata"
      />

      <section className="panel-grid">
        <article className="app-panel">
          <div className="panel-head"><h3>Request leave</h3><small>Sent to HR for approval.</small></div>
          <form className="panel-form" onSubmit={handleLeaveSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Type<input value={leaveForm.leave_type} onChange={(event) => setLeaveForm((prev) => ({ ...prev, leave_type: event.target.value }))} /></label>
              <label className="panel-field">Start<input type="date" value={leaveForm.start_date} onChange={(event) => setLeaveForm((prev) => ({ ...prev, start_date: event.target.value }))} required /></label>
              <label className="panel-field">End<input type="date" value={leaveForm.end_date} onChange={(event) => setLeaveForm((prev) => ({ ...prev, end_date: event.target.value }))} required /></label>
              <label className="panel-field full">Reason<textarea value={leaveForm.reason} onChange={(event) => setLeaveForm((prev) => ({ ...prev, reason: event.target.value }))} rows="3" /></label>
            </div>
            <div className="panel-form-actions"><button type="submit" disabled={busy === "leave"}>{busy === "leave" ? "Sending..." : "Send leave request"}</button></div>
          </form>
        </article>

        <article className="app-panel">
          <div className="panel-head"><h3>Request salary advance</h3><small>Amount remains pending until HR approves.</small></div>
          <form className="panel-form" onSubmit={handleAdvanceSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Amount<input type="number" min="1" step="0.01" value={advanceForm.amount} onChange={(event) => setAdvanceForm((prev) => ({ ...prev, amount: event.target.value }))} required /></label>
              <label className="panel-field full">Reason<textarea value={advanceForm.reason} onChange={(event) => setAdvanceForm((prev) => ({ ...prev, reason: event.target.value }))} rows="3" /></label>
            </div>
            <div className="panel-form-actions"><button type="submit" disabled={busy === "advance"}>{busy === "advance" ? "Sending..." : "Send advance request"}</button></div>
          </form>
        </article>
      </section>

      <section className="panel-grid">
        <RecordList title="Leave history" rows={leaves.slice(0, 8)} render={(item) => `${item.leave_type} - ${item.start_date} to ${item.end_date} - ${item.status}`} />
        <RecordList title="Salary advance history" rows={advances.slice(0, 8)} render={(item) => `${formatMoney(item.amount)} - ${item.request_date} - ${item.status}`} />
        <RecordList title="Payroll history" rows={payroll.slice(0, 8)} render={(item) => `${item.period} - ${formatMoney(item.net_salary)} - ${item.status}`} />
        <RecordList title="Attendance history" rows={attendance.slice(0, 8)} render={(item) => `${item.date} - ${item.status}`} />
      </section>

      <MessageInboxPanel
        title="Staff Messages"
        messages={messageData?.inbox || []}
        recipientOptions={staffRecipientOptions}
        onComposeSubmit={handleStaffMessageSend}
        onMarkRead={handleStaffMessageRead}
        onDelete={handleStaffMessageDelete}
        onRefresh={loadMessages}
      />
    </section>
  );
}

function EditableStaffBioProfile({ session, open, onClose, onSaved, fallbackProfile = {}, title = "My profile", subtitle = "Update your biodata and CV." }) {
  const [staffSnapshot, setStaffSnapshot] = useState(null);
  const [profileForm, setProfileForm] = useState({
    phone: "",
    gender: "",
    date_of_birth: "",
    address: "",
    emergency_contact_name: "",
    emergency_contact_phone: "",
    emergency_contact_relation: "",
    profile_picture: null,
    cv: null,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");

  const profile = staffSnapshot?.staff || fallbackProfile || {};
  const displayName = profile.name || profile.full_name || fallbackProfile.name || fallbackProfile.full_name || fallbackProfile.email || "Profile";
  const avatar = profile.profile_picture || fallbackProfile.profile_picture;
  const initials = userInitials({ full_name: displayName });

  useEffect(() => {
    if (!open || !session) return;
    setLoading(true);
    setFeedback("");
    setError("");
    requestJson(session, "GET", "/api/hr/me/")
      .then((result) => {
        setStaffSnapshot(result);
        const staff = result?.staff || {};
        setProfileForm((prev) => ({
          ...prev,
          phone: staff.phone || "",
          gender: staff.gender || "",
          date_of_birth: String(staff.date_of_birth || "").slice(0, 10),
          address: staff.address || "",
          emergency_contact_name: staff.emergency_contact_name || "",
          emergency_contact_phone: staff.emergency_contact_phone || "",
          emergency_contact_relation: staff.emergency_contact_relation || "",
          profile_picture: null,
          cv: null,
        }));
      })
      .catch((loadError) => setError(loadError.message || "Could not load profile."))
      .finally(() => setLoading(false));
  }, [open, session]);

  if (!open) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setFeedback("");
    setError("");
    const formData = new FormData();
    Object.entries(profileForm).forEach(([key, value]) => {
      if (key === "cv" || key === "profile_picture") {
        if (value) formData.append(key, value);
        return;
      }
      formData.append(key, value || "");
    });
    try {
      const result = await requestJson(session, "PATCH", "/api/hr/me/", formData);
      setStaffSnapshot((prev) => ({ ...(prev || {}), staff: result?.staff || prev?.staff }));
      setProfileForm((prev) => ({ ...prev, profile_picture: null, cv: null }));
      setFeedback(result?.message || "Profile saved.");
      await onSaved?.();
    } catch (saveError) {
      setError(saveError.message || "Could not save profile.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="student-profile-modal teacher-profile-modal" role="dialog" aria-modal="true" aria-label={`${title} biodata`}>
      <article className="student-profile-card teacher-profile-card">
        <header className="student-profile-card-head">
          <div className="student-profile-photo">
            {avatar ? <img src={avatar} alt={`${displayName} profile`} /> : <span>{initials}</span>}
          </div>
          <div>
            <p className="topbar-kicker">{subtitle}</p>
            <h3>{displayName}</h3>
            <small>{profile.staff_code || profile.employee_id || fallbackProfile.employee_id || "Staff profile"}</small>
          </div>
          <button type="button" className="student-profile-close" onClick={onClose} aria-label="Close profile">
            x
          </button>
        </header>
        <form className="panel-form teacher-profile-edit-form" onSubmit={handleSubmit}>
          {loading ? <p className="panel-empty">Loading profile...</p> : null}
          <div className="panel-form-grid">
            <label className="panel-field">Phone<input value={profileForm.phone} onChange={(event) => setProfileForm((prev) => ({ ...prev, phone: event.target.value }))} /></label>
            <label className="panel-field">Gender<select value={profileForm.gender} onChange={(event) => setProfileForm((prev) => ({ ...prev, gender: event.target.value }))}><option value="">Select gender</option><option value="M">Male</option><option value="F">Female</option><option value="O">Other</option><option value="N">Prefer not to say</option></select></label>
            <label className="panel-field">Date of birth<input type="date" value={profileForm.date_of_birth} onChange={(event) => setProfileForm((prev) => ({ ...prev, date_of_birth: event.target.value }))} /></label>
            <label className="panel-field full">Address<textarea rows="2" value={profileForm.address} onChange={(event) => setProfileForm((prev) => ({ ...prev, address: event.target.value }))} /></label>
            <label className="panel-field">Next of kin<input value={profileForm.emergency_contact_name} onChange={(event) => setProfileForm((prev) => ({ ...prev, emergency_contact_name: event.target.value }))} /></label>
            <label className="panel-field">Next of kin phone<input value={profileForm.emergency_contact_phone} onChange={(event) => setProfileForm((prev) => ({ ...prev, emergency_contact_phone: event.target.value }))} /></label>
            <label className="panel-field">Relationship<input value={profileForm.emergency_contact_relation} onChange={(event) => setProfileForm((prev) => ({ ...prev, emergency_contact_relation: event.target.value }))} /></label>
            <label className="panel-field full">Profile picture<input type="file" accept="image/*" onChange={(event) => setProfileForm((prev) => ({ ...prev, profile_picture: event.target.files?.[0] || null }))} /></label>
            <label className="panel-field full">CV<input type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" onChange={(event) => setProfileForm((prev) => ({ ...prev, cv: event.target.files?.[0] || null }))} /></label>
          </div>
          {profile.cv_url || profile.cv || profile.resume ? <p className="field-note">Current CV: <a href={profile.cv_url || profile.cv || profile.resume} target="_blank" rel="noreferrer">Open uploaded CV</a></p> : null}
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {error ? <p className="form-feedback error">{error}</p> : null}
          <div className="panel-form-actions">
            <button type="button" className="table-action" onClick={onClose}>Close</button>
            <button type="submit" disabled={saving || loading}>{saving ? "Saving..." : "Save biodata"}</button>
          </div>
        </form>
      </article>
    </section>
  );
}

function TeacherDashboard({ session, data = {}, onCreatePrompt, onNotifyExam, isRefreshing, onNavigate, onTabChange, onRefresh }) {
  const metrics = data.metrics || {};
  const exams = data.upcoming_assessments || [];
  const teacherProfile = data.profile || data.teacher || data.user || {};
  const teacherName = teacherProfile.name || teacherProfile.full_name || teacherProfile.email || "Teacher";
  const teacherAvatar = teacherProfile.profile_picture;
  const teacherInitials = userInitials({ full_name: teacherName });
  const [profileOpen, setProfileOpen] = useState(false);
  const school = resolveSchoolBrand(data.school, session?.school, session);
  const examResults =
    data.exam_results || data.results || data.recent_results || data.pending_submissions || [];
  const cbtResults = data.cbt_results || data.submitted_results || examResults || [];
  const cbtAverage = metrics.average_cbt_score ?? (
    cbtResults.length
      ? Math.round(cbtResults.reduce((sum, item) => sum + Number(item.percentage || 0), 0) / cbtResults.length)
      : 0
  );
  const subjectOptions = data.options?.subjects || [];
  const assignedSubjects = (() => {
    // Backends may return subjects as strings or arrays; normalize to an array of objects for rendering.
    if (Array.isArray(teacherProfile.subjects)) {
      return teacherProfile.subjects;
    }

    if (Array.isArray(teacherProfile.subjects_taught) && teacherProfile.subjects_taught.length) {
      const normalized = teacherProfile.subjects_taught.map((name) => (name || "").trim().toLowerCase()).filter(Boolean);
      const matched = subjectOptions.filter((subject) =>
        normalized.includes((subject.name || "").trim().toLowerCase())
      );
      if (matched.length) {
        return matched;
      }
      return normalized.map((name, index) => ({ id: `subject-${index}`, name }));
    }

    if (typeof teacherProfile.subjects === "string" && teacherProfile.subjects.trim()) {
      return teacherProfile.subjects
        .split(/[,;]/)
        .map((name, index) => ({ id: `subject-${index}`, name: name.trim() }))
        .filter((item) => item.name.length > 0);
    }

    return [];
  })();


  return (
    <section className="teacher-workspace">
      <div className="teacher-header">
        <SchoolBrand school={school} subtitle="Teacher" compact />
        <div className="teacher-header-copy">
          <p className="topbar-kicker">Welcome back</p>
          <h2>{teacherName}</h2>
          <p>{teacherProfile.specialization || "Teacher workspace"}</p>
          <small>
            {teacherProfile.email || ""} {teacherProfile.employee_id ? `- ${teacherProfile.employee_id}` : ""}{" "}
            {assignedSubjects.length ? `- ${assignedSubjects.map((s) => s.name).join(", ")}` : ""}
          </small>
        </div>
        <div className="teacher-header-actions">
          <button type="button" className="teacher-profile-button" onClick={() => setProfileOpen(true)} aria-label="Edit teacher profile" title="Edit profile">
            {teacherAvatar ? <img src={teacherAvatar} alt={`${teacherName} avatar`} /> : <span>{teacherInitials}</span>}
            <span className="teacher-profile-edit-indicator" aria-hidden="true">
              <PaintbrushIcon className="inline-icon" />
            </span>
          </button>
        </div>
      </div>

      <EditableStaffBioProfile
        session={session}
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        onSaved={onRefresh}
        fallbackProfile={teacherProfile}
        title="Teacher profile"
        subtitle="Editable biodata"
      />

      <section className="screen-grid teacher-dashboard">
        <div className="screen-hero teacher-overview-hero">
          <h2>Teacher Dashboard</h2>
          <p>Professional snapshot of your assessments, teaching activity, and exam results.</p>
        </div>

        <div className="metric-grid">
          <MetricCard
            label="Total Assessments"
            value={metrics.total_assessments ?? 0}
            trend={`${metrics.published_assessments ?? 0} published`}
            icon="exam"
            tone="blue"
          />
          <MetricCard
            label="Upcoming"
            value={metrics.upcoming_assessments ?? 0}
            trend="Scheduled ahead"
            icon="calendar"
            tone="violet"
          />
          <MetricCard
            label="Pending Submissions"
            value={metrics.pending_submissions ?? 0}
            trend="Awaiting grading"
            icon="requests"
            tone="amber"
          />
          <MetricCard
            label="CBT Results"
            value={metrics.submitted_results ?? cbtResults.length}
            trend={`${cbtAverage}% average`}
            icon="results"
            tone="emerald"
          />
        </div>

        <article className="app-panel">
          <h3>Subjects</h3>
          {assignedSubjects.length ? (
            <div className="pill-stack">
              {assignedSubjects.map((subject) => (
                <span key={subject.id} className="pill">
                  {subject.name} {subject.code ? ` -  ${subject.code}` : ""}
                </span>
              ))}
            </div>
          ) : (
            <p className="panel-empty">No subjects provided yet.</p>
          )}
        </article>

        <article className="app-panel">
          <h3>Quick Actions</h3>
          <p className="panel-sub">Common teaching tasks and shortcuts</p>
          <div className="quick-actions-grid">
            <button
              className="quick-action-card"
              type="button"
              onClick={() => onTabChange?.("planning")}
            >
              <div className="quick-action-icon"><DashboardIcon name="planning" className="inline-icon" /></div>
              <div className="quick-action-content">
                <h4>Lesson Plans</h4>
                <p>Open scheme of work and teacher notepad</p>
              </div>
            </button>
            <button
              className="quick-action-card"
              type="button"
              onClick={() => onTabChange?.("results")}
            >
              <div className="quick-action-icon"><DashboardIcon name="results" className="inline-icon" /></div>
              <div className="quick-action-content">
                <h4>Grade Results</h4>
                <p>Review and score student submissions</p>
              </div>
            </button>
            <button
              className="quick-action-card"
              type="button"
              onClick={() => onTabChange?.("requests")}
            >
              <div className="quick-action-icon"><DashboardIcon name="requests" className="inline-icon" /></div>
              <div className="quick-action-content">
                <h4>Leave & Advances</h4>
                <p>Send HR leave or salary advance requests</p>
              </div>
            </button>
          </div>
        </article>

        <div className="panel-grid">
          <article className="app-panel">
            <h3>Upcoming Exams</h3>
            {exams.length === 0 ? (
              <p className="panel-empty">No upcoming assessments.</p>
            ) : (
              <ul className="panel-list">
                {exams.map((exam) => (
                  <li key={exam.id}>
                    {exam.title} - {exam.class_name} - {formatDate(exam.start_date)}
                  </li>
                ))}
              </ul>
            )}
          </article>
          </div>
        {isRefreshing ? <p className="field-note">Auto-refreshing...</p> : null}
      </section>
    </section>
  );
}

function TeacherSwipeAttendancePanel({ session, classOptions = [] }) {
  const [classId, setClassId] = useState("");
  const [students, setStudents] = useState([]);
  const [history, setHistory] = useState([]);
  const [index, setIndex] = useState(0);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [rosterSearch, setRosterSearch] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [locationStatus, setLocationStatus] = useState("");
  const [savingStatus, setSavingStatus] = useState("");
  const activeStudent = students[index];
  const selectedClass = classOptions.find((item) => String(item.id) === String(classId));
  const filteredRoster = useMemo(() => {
    const query = rosterSearch.trim().toLowerCase();
    if (!query) {
      return students;
    }
    return students.filter((student) =>
      [student.name, student.student_id, student.email, student.class_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [rosterSearch, students]);

  useEffect(() => {
    if (!classId && classOptions.length) {
      setClassId(String(classOptions[0].id));
    }
  }, [classId, classOptions]);

  const loadStudents = useCallback(async () => {
    setError("");
    if (!classId) {
      setStudents([]);
      setIndex(0);
      return;
    }
    try {
      const params = new URLSearchParams({ class_id: classId, date });
      const result = await requestJson(session, "GET", `/api/app/attendance/class-students/?${params.toString()}`);
      setStudents(result.students || []);
      setHistory(result.attendance_records || []);
      setIndex(0);
    } catch (loadError) {
      setError(loadError.message || "Could not load class students.");
    }
  }, [classId, date, session]);

  useEffect(() => {
    if (session) {
      loadStudents();
    }
  }, [loadStudents, session]);

  const mark = async (statusValue) => {
    if (!activeStudent) return;
    setError("");
    setFeedback("");
    setLocationStatus("Requesting GPS location...");
    setSavingStatus(statusValue);
    try {
      const location = await getTeacherAttendanceLocationPayload();
      setLocationStatus("Location captured. Saving attendance...");
      const result = await requestJson(session, "POST", "/api/app/attendance/teacher-mark/", {
        student_id: activeStudent.student_id,
        class_id: classId,
        status: statusValue,
        date,
        location,
      });
      setHistory((previous) => [
        result.attendance,
        ...previous.filter((item) => item.id !== result.attendance?.id && item.student_id !== result.attendance?.student_id),
      ].slice(0, 20));
      setFeedback(result.message || "Attendance saved.");
      setIndex((previous) => Math.min(previous + 1, students.length));
      setLocationStatus("");
    } catch (markError) {
      setError(markError.message || "Could not save attendance.");
    } finally {
      setSavingStatus("");
    }
  };

  return (
    <section className="screen-grid swipe-attendance-page">
      <div className="screen-hero">
        <div>
          <p className="topbar-kicker">Tap Attendance</p>
          <h2>Student Attendance</h2>
          <p>Select an assigned class, then tap a status to save each student's attendance.</p>
        </div>
      </div>
      <article className="app-panel">
        <div className="panel-form-grid">
          <label className="panel-field">
            Class
            <select value={classId} onChange={(event) => setClassId(event.target.value)}>
              <option value="">Select assigned class</option>
              {classOptions.map((item) => <option key={item.id} value={item.id}>{item.label || item.name}</option>)}
            </select>
          </label>
          <label className="panel-field">
            Date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
        </div>
      </article>

      <section className="panel-grid teacher-class-overview-grid">
        <article className="app-panel">
          <div className="panel-head">
            <h3>Assigned classes</h3>
            <small>{classOptions.length} class{classOptions.length === 1 ? "" : "es"}</small>
          </div>
          {classOptions.length ? (
            <div className="teacher-class-chip-list">
              {classOptions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={String(item.id) === String(classId) ? "active" : ""}
                  onClick={() => setClassId(String(item.id))}
                >
                  {item.label || item.name}
                </button>
              ))}
            </div>
          ) : (
            <p className="panel-empty">No class has been assigned to you yet.</p>
          )}
        </article>

        <article className="app-panel">
          <div className="panel-head">
            <h3>Class roster</h3>
            <small>{selectedClass ? `${students.length} student${students.length === 1 ? "" : "s"} in ${selectedClass.label || selectedClass.name}` : "Select a class"}</small>
          </div>
          <label className="panel-field roster-search-field">
            Find student
            <input
              value={rosterSearch}
              onChange={(event) => setRosterSearch(event.target.value)}
              placeholder="Search name, ID, or email"
              disabled={!students.length}
            />
          </label>
          {filteredRoster.length ? (
            <table className="data-table teacher-roster-table">
              <thead>
                <tr><th>Student</th><th>ID</th><th>Email</th></tr>
              </thead>
              <tbody>
                {filteredRoster.map((student) => (
                  <tr key={student.id || student.student_id}>
                    <td>{student.name || "Student"}<br /><small>{student.class_name || selectedClass?.label || "Assigned class"}</small></td>
                    <td>{student.student_id}</td>
                    <td>{student.email || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="panel-empty">{classId ? (rosterSearch ? "No students match your search." : "No students are in this class yet.") : "Select an assigned class to view students."}</p>
          )}
        </article>
      </section>

      <section className="swipe-attendance-grid">
        <article className="swipe-student-card tap-attendance-card">
          {activeStudent ? (
            <>
              <span className="pill muted">{index + 1} / {students.length}</span>
              <div className="swipe-avatar">{activeStudent.name?.slice(0, 2).toUpperCase()}</div>
              <h3>{activeStudent.name}</h3>
              <p>{activeStudent.student_id} - {activeStudent.class_name}</p>
              <div className="swipe-actions">
                <button type="button" className="danger" onClick={() => mark("absent")} disabled={Boolean(savingStatus)}>{savingStatus === "absent" ? "Saving..." : "Absent"}</button>
                <button type="button" onClick={() => mark("late")} disabled={Boolean(savingStatus)}>{savingStatus === "late" ? "Saving..." : "Late"}</button>
                <button type="button" onClick={() => mark("present")} disabled={Boolean(savingStatus)}>{savingStatus === "present" ? "Saving..." : "Present"}</button>
              </div>
              <small>Tap once to capture GPS, save, and move to the next student.</small>
            </>
          ) : (
            <p className="panel-empty">{classId ? "No more students to mark." : "Select an assigned class to begin."}</p>
          )}
          {locationStatus ? <p className="panel-empty">{locationStatus}</p> : null}
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {error ? <p className="form-feedback error">{error}</p> : null}
        </article>
        <article className="app-panel">
          <div className="panel-head"><h3>Daily records</h3><small>{history.length} marked this session</small></div>
          {history.length ? (
            <ul className="panel-list">
              {history.map((item) => <li key={item.id}>{item.student_name} - {item.class_name} - {item.date} - {item.status}</li>)}
            </ul>
          ) : <p className="panel-empty">Attendance records will appear after marking.</p>}
        </article>
      </section>
    </section>
  );
}

function TeacherResultsPanel({ subjects = [], classOptions = [], cbtResults = [], onSubmitScore, onLoadResults, onLoadClassStudents, onPushResults, onSaveGradeScale }) {
  const [form, setForm] = useState({
    student_id: "",
    subject_id: subjects[0]?.id || "",
    max_score: 100,
    class_id: "",
    theory_score: "",
    cbt_score: "",
    assessment_score: "",
    assignment_score: "",
    attendance_score: "",
    other_score: "",
    remarks: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [recent, setRecent] = useState([]);
  const [studentOptions, setStudentOptions] = useState([]);
  const [studentLoading, setStudentLoading] = useState(false);
  const [studentSearch, setStudentSearch] = useState("");
  const [gradeScales, setGradeScales] = useState([]);
  const [gradeForm, setGradeForm] = useState({ letter: "A", min_percentage: "70", max_percentage: "100", remark: "Excellent" });
  const subjectIdSet = useMemo(() => new Set(subjects.map((subject) => String(subject.id))), [subjects]);
  const subjectCbtResults = useMemo(
    () => cbtResults.filter((row) => !row.subject_id || subjectIdSet.has(String(row.subject_id))),
    [cbtResults, subjectIdSet]
  );

  useEffect(() => {
    if (!form.subject_id && subjects.length) {
      setForm((prev) => ({ ...prev, subject_id: subjects[0].id }));
    }
  }, [subjects, form.subject_id]);

  const refresh = useCallback(async () => {
    if (!onLoadResults) {
      return;
    }
    try {
      const snapshot = await onLoadResults();
      setRecent(snapshot?.leaderboard || []);
      setGradeScales(snapshot?.grade_scales || []);
    } catch (loadError) {
      // No-op; teacher can still submit scores.
    }
  }, [onLoadResults]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    let active = true;
    if (!onLoadClassStudents) {
      setStudentOptions([]);
      return () => {
        active = false;
      };
    }
    setStudentLoading(true);
    onLoadClassStudents(form.class_id, form.subject_id)
      .then((snapshot) => {
        if (active) setStudentOptions(snapshot?.students || []);
      })
      .catch(() => {
        if (active) setStudentOptions([]);
      })
      .finally(() => {
        if (active) setStudentLoading(false);
      });
    return () => {
      active = false;
    };
  }, [form.class_id, form.subject_id, onLoadClassStudents]);

  const filteredStudentOptions = useMemo(() => {
    const query = studentSearch.trim().toLowerCase();
    if (!query) {
      return studentOptions;
    }
    return studentOptions.filter((student) =>
      [student.student_id, student.name, student.email, student.class_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [studentOptions, studentSearch]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!onSubmitScore) {
      return;
    }
    if (!form.student_id.trim()) {
      setError("Select a student before submitting.");
      return;
    }
    if (!form.subject_id) {
      setError("Select a subject.");
      return;
    }
    setBusy(true);
    setError("");
    setFeedback("");
    const payload = {
      student_id: form.student_id.trim(),
      subject_id: form.subject_id,
      max_score: Number(form.max_score || 100),
      theory_score: Number(form.theory_score || 0),
      cbt_score: Number(form.cbt_score || 0),
      assessment_score: Number(form.assessment_score || 0),
      assignment_score: Number(form.assignment_score || 0),
      attendance_score: Number(form.attendance_score || 0),
      other_score: Number(form.other_score || 0),
      remarks: form.remarks,
    };
    if (form.class_id) {
      payload.class_id = form.class_id;
    }
    try {
      const result = await onSubmitScore(payload);
      setFeedback(result?.message || "Score recorded.");
      setForm((prev) => ({ ...prev, student_id: "", theory_score: "", cbt_score: "", assessment_score: "", assignment_score: "", attendance_score: "", other_score: "", remarks: "" }));
      refresh();
    } catch (actionError) {
      setError(actionError.message || "Could not submit score.");
    } finally {
      setBusy(false);
    }
  };

  const handlePushResults = async () => {
    setError("");
    setFeedback("");
    try {
      const result = await onPushResults?.({ class_id: form.class_id, title: "Teacher compiled results" });
      setFeedback(result?.message || "Results pushed to admin.");
      refresh();
    } catch (pushError) {
      setError(pushError.message || "Could not push results.");
    }
  };

  const handleGradeScaleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setFeedback("");
    try {
      const result = await onSaveGradeScale?.(gradeForm);
      setFeedback(result?.message || "Grade scale saved.");
      setGradeScales(result?.grades || gradeScales);
      await refresh();
    } catch (gradeError) {
      setError(gradeError.message || "Could not save grade scale.");
    }
  };

  return (
    <section className="screen-grid teacher-results">
      <div className="screen-hero">
        <div>
          <p className="topbar-kicker">Results Workspace</p>
          <h2>Grade &amp; Rankings</h2>
          <p>Submit marks and view standings with the same dashboard styling.</p>
        </div>
      </div>

      <div className="panel-grid">
        <article className="app-panel frosted-card">
          <div className="panel-head">
            <div>
              <h3>Submit subject score</h3>
              <small>Only subjects assigned to you are listed.</small>
            </div>
            <span className="pill">{subjects.length || 0} subjects</span>
          </div>
          <form className="panel-form" onSubmit={handleSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field student-picker-field">
                <span className="student-picker-label">Find student</span>
                <input
                  className="student-picker-search"
                  value={studentSearch}
                  onChange={(event) => setStudentSearch(event.target.value)}
                  placeholder="Search ID, name, or email"
                />
                <select
                  className="student-picker-select"
                  value={form.student_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, student_id: event.target.value }))}
                  disabled={studentLoading || studentOptions.length === 0}
                >
                  <option value="">{studentLoading ? "Loading students..." : studentSearch ? "Select matching student" : "Select student"}</option>
                  {filteredStudentOptions.map((student) => (
                    <option key={student.id || student.student_id} value={student.student_id}>
                      {student.name} - {student.student_id} - {student.email || "No email"} - {student.class_name}
                    </option>
                  ))}
                  {!studentLoading && studentSearch && filteredStudentOptions.length === 0 ? <option value="" disabled>No matching students</option> : null}
                </select>
                <small className="field-note">Students are available when you teach the selected subject.</small>
              </label>
              <label className="panel-field compact-subject-field">
                Subject
                <select
                  className="compact-subject-select"
                  value={form.subject_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, subject_id: event.target.value }))}
                  disabled={subjects.length === 1}
                >
                  {subjects.length === 0 ? <option value="">No subjects assigned</option> : null}
                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
                {subjects.length === 1 ? <small className="field-note">Auto-selected assigned subject.</small> : null}
              </label>
              <label className="panel-field">
                Class (optional)
                <select
                  value={form.class_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, class_id: event.target.value, student_id: "" }))}
                >
                  <option value="">Use student's class</option>
                  {classOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label || item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="panel-field">
                Max score
                <input
                  type="number"
                  value={form.max_score}
                  onChange={(event) => setForm((prev) => ({ ...prev, max_score: event.target.value }))}
                  min="1"
                  step="0.01"
                />
              </label>
              {[
                ["theory_score", "Theory exam"],
                ["cbt_score", "CBT exam"],
                ["assessment_score", "Assessment"],
                ["assignment_score", "Assignment"],
                ["attendance_score", "Attendance"],
                ["other_score", "Other CA"],
              ].map(([key, label]) => (
                <label key={key} className="panel-field">
                  {label}
                  <input type="number" min="0" step="0.01" value={form[key]} onChange={(event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))} />
                </label>
              ))}
              <label className="panel-field full">
                Remarks
                <FormattedTextarea value={form.remarks} onChange={(event) => setForm((prev) => ({ ...prev, remarks: event.target.value }))} />
              </label>
            </div>
            {error ? <p className="form-feedback error">{error}</p> : null}
            {feedback ? <p className="form-feedback success">{feedback}</p> : null}
            <div className="panel-form-actions">
              <button type="submit" disabled={busy || subjects.length === 0}>
                {busy ? "Saving..." : "Save draft score"}
              </button>
              <button type="button" className="table-action" onClick={handlePushResults}>
                Push Result to Admin
              </button>
            </div>
          </form>
        </article>

        <article className="app-panel frosted-card">
          <div className="panel-head">
            <div>
              <h3>CBT results by subject</h3>
              <small>Use online CBT scores when compiling final subject results.</small>
            </div>
            <span className="pill muted">{subjectCbtResults.length || 0} rows</span>
          </div>
          {subjectCbtResults.length ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Subject</th>
                  <th>Class</th>
                  <th>CBT Score</th>
                  <th>Use</th>
                </tr>
              </thead>
              <tbody>
                {subjectCbtResults.slice(0, 30).map((row) => (
                  <tr key={row.attempt_id || row.id}>
                    <td>{row.student_name}<small>{row.student_id || row.student_email}</small></td>
                    <td>{row.subject || "General"}</td>
                    <td>{row.class_name || "-"}</td>
                    <td>{row.score ?? 0}/{row.total_points ?? "-"}</td>
                    <td>
                      <button
                        type="button"
                        className="table-action"
                        onClick={() => {
                          setForm((prev) => ({
                            ...prev,
                            student_id: row.student_id || prev.student_id,
                            subject_id: row.subject_id || prev.subject_id,
                            class_id: row.class_id || prev.class_id,
                            cbt_score: String(row.score ?? ""),
                          }));
                          setStudentSearch(row.student_id || row.student_name || "");
                        }}
                      >
                        Fill
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="panel-empty">No submitted CBT results for your assigned subjects yet.</p>
          )}
        </article>

        <article className="app-panel frosted-card">
          <div className="panel-head">
            <div>
              <h3>Grading scale</h3>
              <small>Use before pushing a result to admin for approval.</small>
            </div>
            <span className="pill muted">{gradeScales.length || 0} ranges</span>
          </div>
          <form className="panel-form" onSubmit={handleGradeScaleSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Letter<input value={gradeForm.letter} onChange={(event) => setGradeForm((prev) => ({ ...prev, letter: event.target.value.toUpperCase() }))} /></label>
              <label className="panel-field">Minimum %<input type="number" min="0" max="100" value={gradeForm.min_percentage} onChange={(event) => setGradeForm((prev) => ({ ...prev, min_percentage: event.target.value }))} /></label>
              <label className="panel-field">Maximum %<input type="number" min="0" max="100" value={gradeForm.max_percentage} onChange={(event) => setGradeForm((prev) => ({ ...prev, max_percentage: event.target.value }))} /></label>
              <label className="panel-field">Remark<input value={gradeForm.remark} onChange={(event) => setGradeForm((prev) => ({ ...prev, remark: event.target.value }))} /></label>
            </div>
            <div className="panel-form-actions"><button type="submit">Save grade range</button></div>
          </form>
          {gradeScales.length ? (
            <div className="subject-chip-grid">
              {gradeScales.map((grade) => (
                <button
                  key={grade.letter}
                  type="button"
                  className="subject-suggestion-chip"
                  onClick={() => setGradeForm({
                    letter: grade.letter,
                    min_percentage: String(grade.min_percentage),
                    max_percentage: String(grade.max_percentage),
                    remark: grade.remark || "",
                  })}
                >
                  <span>{grade.letter}</span>
                  <small>{grade.min_percentage}% - {grade.max_percentage}% - {grade.remark}</small>
                </button>
              ))}
            </div>
          ) : <p className="panel-empty">Grade ranges will appear here.</p>}
        </article>

        <article className="app-panel frosted-card">
          <div className="panel-head">
            <div>
              <h3>Recent rankings</h3>
              <small>Descending order by total score.</small>
            </div>
            <span className="pill muted">{recent.length || 0} rows</span>
          </div>
          {recent.length ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Student</th>
                  <th>Total</th>
                  <th>Average</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((row) => (
                  <tr key={row.student_id}>
                    <td>#{row.rank}</td>
                    <td>{row.student_name}</td>
                    <td>{row.total_score}</td>
                    <td>{row.average_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="panel-empty">Submit a score to see rankings.</p>
          )}
        </article>
      </div>
    </section>
  );
}

function TeacherWorkspace({
  session,
  data = {},
  onCreatePrompt,
  onNotifyExam,
  onMessageSend,
  onMarkMessageRead,
  onDeleteMessage,
  onCreateQuestion,
  onGradeSubmission,
  onClassMessageSend,
  onSubmitScore,
  onLoadResults,
  onLoadClassStudents,
  onPushResults,
  onSaveGradeScale,
  onCreateExam,
  onUpdateExam,
  isRefreshing,
  onRefresh,
  themePreference,
  onThemeChange,
  onNavigate,
  onSignOut,
}) {
  const [activeTab, setActiveTab] = useState("overview");
  const [navOpen, setNavOpen] = useState(false);
  const [editingExam, setEditingExam] = useState(null);
  const [loadingExamId, setLoadingExamId] = useState("");
  const [examEditError, setExamEditError] = useState("");
  const inbox = data?.inbox || [];
  const unreadInbox = Number(data?.metrics?.unread_inbox ?? inbox.filter((item) => !item.is_read).length);
  const recipientContacts = data?.recipients || data?.admin_contacts || [];
  const classOptions = data?.options?.classes || data?.classes || [];
  const questionTemplates = data?.question_prompts || [];
  const pendingSubmissions = data?.pending_submissions || data?.submissions || [];
  const cbtResults = data?.cbt_results || data?.submitted_results || [];
  const subjectOptions = data?.options?.subjects || [];
  const taughtNames = (data?.profile?.subjects_taught || []).map((name) => (name || "").toLowerCase());
  const teacherSubjects =
    taughtNames.length === 0
      ? subjectOptions
      : subjectOptions.filter((subject) => taughtNames.includes(subject.name.toLowerCase()));
  const teacherProfile = data?.profile || data?.teacher || {};
  const teacherName = teacherProfile.name || session?.user?.full_name || session?.user?.email || "Teacher";
  const nonK12 = isNonK12School(session, data);
  const teacherTabs = [
    ["overview", "Home", "overview"],
    ["exam-builder", "Exams", "exam"],
    ["past-exams", "Exam History", "calendar"],
    nonK12 ? ["attendance-info", "Attendance", "attendance"] : ["attendance", "Student Attendance", "attendance"],
    ["planning", nonK12 ? "Course Outline and Notepad" : "Lesson Plans and Notepad", "planning"],
    ["class-messages", "Messages & Notifications", "message"],
    ["results", "Results", "results"],
    ["requests", "HR System", "requests"],
  ];

  const recipientOptions = useMemo(
    () =>
      filterRecipientsForRole(recipientContacts, session?.user)
        .filter((contact) => contact?.email)
        .map((contact) => ({
          value: contact.email,
          label: `${contact.name || contact.email} - ${contact.role || "Contact"}`,
        })),
    [recipientContacts, session?.user]
  );

  const handleCompose = useCallback(
    (recipientValue, subject, body, _selectedRecipient, attachments = []) => {
      return onMessageSend(recipientValue, subject, body, attachments);
    },
    [onMessageSend]
  );

  const handleEditExam = useCallback(
    async (examId) => {
      setLoadingExamId(examId);
      setExamEditError("");
      try {
        const result = await requestJson(session, "GET", `/api/app/exams/${examId}/`);
        setEditingExam(result.exam || null);
        setActiveTab("exam-builder");
        setNavOpen(false);
      } catch (loadError) {
        setExamEditError(loadError.message || "Could not open exam.");
      } finally {
        setLoadingExamId("");
      }
    },
    [session]
  );

  const tabTitle = teacherTabs.find(([key]) => key === activeTab)?.[1] || "Home";
  const renderTeacherContent = () => {
    if (activeTab === "overview") {
      return (
        <TeacherDashboard session={session} data={data} onCreatePrompt={onCreatePrompt} onNotifyExam={onNotifyExam} isRefreshing={isRefreshing} onNavigate={onNavigate} onTabChange={setActiveTab} onRefresh={onRefresh} />
      );
    }
    if (activeTab === "exam-builder") {
      return (
        <TeacherExamBuilder
          session={session}
          classOptions={classOptions}
          subjectOptions={subjectOptions}
          teacherName={teacherName}
          initialExam={editingExam}
          onCreateExam={onCreateExam}
          onUpdateExam={onUpdateExam}
          onBackToList={() => {
            setEditingExam(null);
            setActiveTab("past-exams");
          }}
        />
      );
    }
    if (activeTab === "past-exams") {
      return (
        <TeacherPastExamsPanel
          session={session}
          onEditExam={handleEditExam}
          loadingExamId={loadingExamId}
          editError={examEditError}
        />
      );
    }
    if (activeTab === "attendance") {
      return <TeacherSwipeAttendancePanel session={session} classOptions={classOptions} />;
    }
    if (activeTab === "attendance-info") {
      return (
        <article className="app-panel state-panel">
          <h3>Student Self Attendance</h3>
          <p>For non K-12 schools, students mark attendance themselves from their Attendance page using the student QR scanner.</p>
          <p>Admins generate or print the shared Student QR code from the admin Attendance page.</p>
        </article>
      );
    }
    if (activeTab === "planning") {
      return <TeacherPlanningPanel session={session} onNavigate={onNavigate} />;
    }
    if (activeTab === "class-messages") {
      return (
        <div className="workspace-inbox">
          <ClassMessageComposer classOptions={classOptions} onSend={onClassMessageSend} />
          <MessageInboxPanel
            title="Messages & Notifications"
            messages={inbox}
            recipientOptions={recipientOptions}
            onComposeSubmit={handleCompose}
            onMarkRead={onMarkMessageRead}
            onDelete={onDeleteMessage}
            onRefresh={onRefresh}
          />
        </div>
      );
    }
    if (activeTab === "results") {
      return (
        <TeacherResultsPanel
          subjects={teacherSubjects}
          classOptions={classOptions}
          cbtResults={cbtResults}
          onSubmitScore={onSubmitScore}
          onLoadResults={onLoadResults}
          onLoadClassStudents={onLoadClassStudents}
          onPushResults={onPushResults}
          onSaveGradeScale={onSaveGradeScale}
        />
      );
    }
    if (activeTab === "requests") {
      return <StaffSelfServicePanel session={session} showAttendance={false} onRefresh={null} />;
    }
    return null;
  };

  return (
    <section className={`teacher-workspace-shell ${navOpen ? "nav-open" : ""}`}>
      <button type="button" className="teacher-sidebar-toggle" onClick={() => setNavOpen((current) => !current)}>
        <span className="menu-bars" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>{tabTitle}</span>
      </button>
      <aside className="teacher-sidebar">
        <div className="teacher-sidebar-head">
          <span>Teacher Workspace</span>
          <strong>{teacherName}</strong>
          <small>{data?.school?.name || session?.school?.name || "SchoolDom"}</small>
        </div>
        <nav className="teacher-sidebar-nav" aria-label="Teacher workspace navigation">
          {teacherTabs.map(([key, label, icon]) => (
            <button
              key={key}
              type="button"
              className={activeTab === key ? "active" : ""}
              onClick={() => {
                if (key === "exam-builder") {
                  setEditingExam(null);
                  setExamEditError("");
                }
                setActiveTab(key);
                setNavOpen(false);
              }}
            >
              <DashboardIcon name={icon} className="inline-icon" />
              <span>{label}</span>
              {key === "class-messages" && unreadInbox > 0 ? (
                <strong className="notification-badge">{unreadInbox > 99 ? "99+" : unreadInbox}</strong>
              ) : null}
            </button>
          ))}
          <button type="button" onClick={() => onNavigate?.("/quizzes")}>
            <DashboardIcon name="exam" className="inline-icon" />
            <span>Assessments</span>
          </button>
        </nav>
        <div className="teacher-sidebar-footer">
          <button
            type="button"
            className="theme-icon-toggle"
            onClick={() => onThemeChange?.(themePreference === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${themePreference === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${themePreference === "dark" ? "light" : "dark"} theme`}
          >
            <ThemeModeIcon mode={themePreference} className="inline-icon" />
            <span>{themePreference === "dark" ? "Dark" : "Light"}</span>
          </button>
          {onSignOut ? (
            <button type="button" className="teacher-sidebar-signout" onClick={onSignOut}>
              Sign out
            </button>
          ) : null}
        </div>
      </aside>
      <div className="teacher-sidebar-overlay" role="presentation" onClick={() => setNavOpen(false)} />
      <main className="teacher-workspace-main">
        {renderTeacherContent()}
      </main>
    </section>
  );
}

const ADMIN_NOTIFICATION_FILTERS = ["All", "Students", "Teachers", "Finance", "Exams", "Security", "System"];

function formatNotificationTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) {
    return { date: "Today", time: "Now" };
  }
  return {
    date: date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }),
    time: date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
}

function mapMessageNotification(item) {
  const body = `${item.subject || ""} ${item.body || ""} ${item.title || ""} ${item.message || ""}`.toLowerCase();
  let category = "System";
  let tone = "info";
  let priority = "Medium";
  let module = "Messages";

  if (body.includes("payment") || body.includes("fee") || body.includes("wallet")) {
    category = "Finance";
    module = "Payments";
  } else if (body.includes("exam") || body.includes("result") || body.includes("quiz") || body.includes("cbt")) {
    category = "Exams";
    module = "Exams";
  } else if (body.includes("teacher") || body.includes("staff")) {
    category = "Teachers";
    module = "Teacher Actions";
  } else if (body.includes("student") || body.includes("assignment") || body.includes("profile")) {
    category = "Students";
    module = "Student Activity";
  } else if (body.includes("login") || body.includes("password") || body.includes("security")) {
    category = "Security";
    module = "Security";
    tone = "warning";
    priority = "High";
  }

  return {
    id: `message-${item.id}`,
    sourceId: item.id,
    category,
    module,
    user: item.from || item.from_name || "SchoolDom",
    role: item.from_role || "User",
    action: item.subject || item.body || item.title || item.message || "New platform message received.",
    status: item.is_read ? "Read" : "Unread",
    priority,
    tone,
    createdAt: item.created_at || item.sent_at || new Date().toISOString(),
    isRead: Boolean(item.is_read),
  };
}

function AdminNotificationsCenter({ session, data = {}, activityRecords = [], loading, error, onRetry, onMarkRead, onMarkActivityRead, isPopup = false, onClose }) {
  const notifications = data?.notifications || [];
  const inbox = data?.inbox || data?.messages || [];
  const announcements = data?.announcements || [];
  const messageItems = useMemo(
    () => [
      ...notifications.filter(Boolean).map((item) => ({ ...mapMessageNotification(item), source: "notification" })),
      ...inbox.filter(Boolean).map((item) => ({ ...mapMessageNotification(item), source: "message" })),
      ...announcements.filter(Boolean).map((item) => ({
        id: `announcement-${item.id}`,
        sourceId: item.id,
        source: "announcement",
        category: "System",
        module: "Broadcast",
        user: "SchoolDom",
        role: "Announcement",
        action: item.title || item.message || "Broadcast announcement.",
        status: "Published",
        priority: item.priority || "Normal",
        tone: item.priority === "urgent" || item.priority === "high" ? "warning" : "info",
        createdAt: item.published_at || item.created_at || new Date().toISOString(),
        isRead: true,
      })),
    ],
    [notifications, inbox, announcements]
  );
  const [filter, setFilter] = useState("All");
  const [searchTerm, setSearchTerm] = useState("");
  const [readIds, setReadIds] = useState(() => new Set());
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [busyId, setBusyId] = useState("");

  const playNotificationTone = useCallback(() => {
    if (!soundEnabled || typeof window === "undefined") return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = 720;
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.18);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.2);
  }, [soundEnabled]);

  useEffect(() => {
    playNotificationTone();
  }, [activityRecords, data, playNotificationTone]);

  const allItems = useMemo(() => {
    const merged = [...activityRecords, ...messageItems];
    return merged
      .map((item) => ({ ...item, isRead: readIds.has(item.id) || Boolean(item.isRead) }))
      .sort((a, b) => new Date(b.createdAt || 0) - new Date(a.createdAt || 0));
  }, [activityRecords, messageItems, readIds]);

  const filteredItems = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return allItems.filter((item) => {
      const matchesFilter = filter === "All" || item.category === filter;
      const haystack = `${item.user} ${item.role} ${item.action} ${item.module} ${item.status} ${item.priority}`.toLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
  }, [allItems, filter, searchTerm]);

  const unreadCount = allItems.filter((item) => !item.isRead).length;
  const markRead = async (item) => {
    setBusyId(item.id);
    setReadIds((prev) => {
      const next = new Set(prev);
      next.add(item.id);
      return next;
    });
    try {
      if (item.source === "message" && item.sourceId && onMarkRead && !item.isRead) {
        await onMarkRead(item.sourceId, { refresh: false });
      }
      if (item.source === "notification" && item.sourceId && !item.isRead) {
        await requestJson(session, "POST", `/api/app/notifications/${item.sourceId}/read/`);
      }
      if (item.source === "admin-activity") {
        onMarkActivityRead?.(item.id);
      }
      onRetry?.();
    } finally {
      setBusyId("");
    }
  };

  const markVisibleRead = async () => {
    const unreadItems = allItems.filter((item) => !item.isRead);
    if (!unreadItems.length) return;
    setBusyId("__all__");
    try {
      const unreadMessages = unreadItems.filter((item) => item.source === "message" && item.sourceId && onMarkRead);
      const unreadNotifications = unreadItems.filter((item) => item.source === "notification" && item.sourceId);
      await Promise.all([
        ...unreadMessages.map((item) => onMarkRead(item.sourceId, { refresh: false }).catch(() => null)),
        ...unreadNotifications.map((item) => requestJson(session, "POST", `/api/app/notifications/${item.sourceId}/read/`).catch(() => null)),
      ]);
      setReadIds((prev) => {
        const next = new Set(prev);
        unreadItems.forEach((item) => next.add(item.id));
        return next;
      });
      unreadItems.filter((item) => item.source === "admin-activity").forEach((item) => onMarkActivityRead?.(item.id));
      onRetry?.();
    } finally {
      setBusyId("");
    }
  };

  return (
    <section className={`screen-grid admin-notification-center ${isPopup ? "notification-popup-center" : ""}`}>
      <ScreenState loading={loading} error={error} onRetry={onRetry} />
      <header className="notification-center-hero">
        <div>
          <p className="topbar-kicker">Real-time activity monitor</p>
          <h2>{isPopup ? "Notifications" : "Admin Notifications Center"}</h2>
          <p>Live operational log for registrations, exams, payments, classroom updates, security events, settings, attendance, and system health.</p>
        </div>
        {isPopup ? (
          <button type="button" className="notification-close-button" onClick={onClose}>
            Close
          </button>
        ) : null}
      </header>

      <div className="notification-layout">
        <section className="app-panel notification-feed-panel">
          <div className="notification-toolbar">
            <div className="notification-search">
              <FilterIcon className="inline-icon" />
              <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search user, action, module, status..." />
            </div>
            <button type="button" className="table-action notification-mark-all" disabled={unreadCount === 0 || busyId === "__all__"} onClick={markVisibleRead}>
              {busyId === "__all__" ? "Clearing..." : "Mark all as read"}
            </button>
          </div>

          <div className="notification-card-list">
            {filteredItems.length === 0 ? (
              <p className="panel-empty">No notifications match this view.</p>
            ) : (
              filteredItems.map((item) => {
                const time = formatNotificationTime(item.createdAt);
                return (
                  <article key={item.id} className={`admin-notification-card tone-${item.tone} ${item.isRead ? "is-read" : "is-unread"}`}>
                    <div className="notification-card-marker" />
                    <div className="notification-card-body">
                      <div className="notification-card-topline">
                        <div>
                          <h3>{item.user}</h3>
                          <p>{item.role} - {item.module}</p>
                        </div>
                        <div className="notification-badge-row">
                          <span className={`notification-status status-${item.tone}`}>{item.status}</span>
                          <span className={`notification-priority priority-${String(item.priority).toLowerCase()}`}>{item.priority}</span>
                        </div>
                      </div>
                      <p className="notification-action">{item.action}</p>
                      <div className="notification-card-footer">
                        <span>{time.date}</span>
                        <span>{time.time}</span>
                        <span>{item.category}</span>
                      </div>
                    </div>
                    <button type="button" className="table-action" disabled={item.isRead || busyId === item.id} onClick={() => markRead(item)}>
                      {item.isRead ? "Read" : busyId === item.id ? "Saving..." : "Mark read"}
                    </button>
                  </article>
                );
              })
            )}
          </div>
        </section>

      </div>
    </section>
  );
}

function AdminShell({ session, currentPath, onNavigate, onSignOut, themePreference, onThemeChange, onSessionUpdate }) {
  const isAccountant = session?.user?.role === "accountant";
  const visibleRoutes = isAccountant ? ACCOUNTANT_ROUTES : ADMIN_ROUTES;
  const visibleRouteSet = useMemo(
    () =>
      new Set([
        ...visibleRoutes.map((item) => item.path),
        ...visibleRoutes.filter((item) => item.children).flatMap((item) => item.children.map((child) => child.path)),
      ]),
    [visibleRoutes]
  );
  const activePath = visibleRouteSet.has(currentPath) ? currentPath : visibleRoutes[0]?.path || "/dashboard";
  const [screenData, setScreenData] = useState({});
  const [screenLoading, setScreenLoading] = useState({});
  const [screenError, setScreenError] = useState({});
  const [adminActivityRecords, setAdminActivityRecords] = useState(() => readAdminActivityLog(session));
  const [navOpen, setNavOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(null);
  const messagesPollRef = useRef(null);
  const adminPollRef = useRef(null);
  const MESSAGES_POLL_MS = 20000;
  const ADMIN_ACTIVE_POLL_MS = 5000;

  useEffect(() => {
    if (currentPath !== activePath) {
      onNavigate(activePath, { replace: true });
    }
  }, [activePath, currentPath, onNavigate]);

  useEffect(() => {
    setAdminActivityRecords(readAdminActivityLog(session));
  }, [session]);

  const loadScreen = useCallback(
    async (path, force = false, silent = false) => {
      const endpoint = ADMIN_ENDPOINTS[path];
      if (!endpoint) {
        return;
      }

      if (!force && screenData[path]) {
        return;
      }

      if (!silent || !screenData[path]) {
        setScreenLoading((prev) => ({ ...prev, [path]: true }));
      }
      setScreenError((prev) => ({ ...prev, [path]: "" }));
      try {
        let data = await requestJson(session, "GET", endpoint);
        // /api/app/exams/ already includes submitted_results and auto_submitted_exams.
        if (path === "/finance") {
          try {
            const hrData = await requestJson(session, "GET", "/api/hr/overview/");
            data = {
              ...data,
              hr_snapshot: hrData,
            };
          } catch (hrError) {
            data = {
              ...data,
              hr_snapshot: { staff: [] },
            };
          }
        }
        setScreenData((prev) => ({ ...prev, [path]: data }));
      } catch (requestError) {
        setScreenError((prev) => ({ ...prev, [path]: requestError.message || "Could not load data." }));
      } finally {
        setScreenLoading((prev) => ({ ...prev, [path]: false }));
      }
    },
    [screenData, session]
  );

  useEffect(() => {
    loadScreen(activePath);
  }, [activePath, loadScreen]);

  useEffect(() => {
    if (!screenData["/settings"] && !screenLoading["/settings"] && !screenError["/settings"]) {
      loadScreen("/settings");
    }
  }, [loadScreen, screenData, screenError, screenLoading]);

  useEffect(() => {
    if (!screenData["/messages"] && !screenLoading["/messages"] && !screenError["/messages"]) {
      loadScreen("/messages");
    }
  }, [loadScreen, screenData, screenError, screenLoading]);

  const handleRetry = useCallback(() => {
    loadScreen(activePath, true);
  }, [activePath, loadScreen]);

  const handleNotificationsRefresh = useCallback(() => {
    loadScreen("/messages", true);
  }, [loadScreen]);

  useEffect(() => {
    let refreshTimer = null;
    const handleDataMutation = () => {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        const paths = new Set([...Object.keys(screenData), activePath, "/dashboard", "/messages"]);
        Promise.all(
          Array.from(paths)
            .filter((path) => ADMIN_ENDPOINTS[path])
            .map((path) => loadScreen(path, true))
        ).catch(() => null);
      }, 120);
    };
    window.addEventListener(SCHOOL_DATA_MUTATED_EVENT, handleDataMutation);
    return () => {
      window.clearTimeout(refreshTimer);
      window.removeEventListener(SCHOOL_DATA_MUTATED_EVENT, handleDataMutation);
    };
  }, [activePath, loadScreen, screenData]);

  const addAdminNotification = useCallback(
    (payload) => {
      const nextItem = createAdminActivityNotification(payload, session?.user);
      setAdminActivityRecords((previous) => {
        const next = [nextItem, ...previous].slice(0, 80);
        writeAdminActivityLog(session, next);
        return next;
      });
      return nextItem;
    },
    [session]
  );

  const markAdminActivityRead = useCallback((notificationId) => {
    setAdminActivityRecords((previous) => {
      const next = previous.map((item) => (item.id === notificationId ? { ...item, isRead: true } : item));
      writeAdminActivityLog(session, next);
      return next;
    });
  }, [session]);

  const handleSendMessage = useCallback(
    async (payload, options = {}) => {
      const { refresh = true } = options;
      const result = await requestJson(session, "POST", "/api/app/messages/send/", payload);
      if (refresh) {
        await loadScreen("/messages", true);
      }
      if (["students_teachers_announcement", "school_broadcast"].includes(payload?.target)) {
        await loadScreen("/dashboard", true);
      }
      return result;
    },
    [loadScreen, session]
  );

  // Poll messages inbox so updates arrive without manual refresh
  useEffect(() => {
    if (messagesPollRef.current) {
      clearInterval(messagesPollRef.current);
    }
    messagesPollRef.current = setInterval(() => {
      loadScreen("/messages", true, true);
    }, MESSAGES_POLL_MS);
    return () => {
      if (messagesPollRef.current) {
        clearInterval(messagesPollRef.current);
      }
    };
  }, [loadScreen]);

  useEffect(() => {
    if (adminPollRef.current) {
      clearInterval(adminPollRef.current);
    }
    adminPollRef.current = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      const paths = new Set([activePath, "/dashboard"]);
      if (activePath === "/results" || activePath === "/exams") {
        paths.add("/results");
        paths.add("/exams");
      }
      Promise.all(
        Array.from(paths)
          .filter((path) => ADMIN_ENDPOINTS[path])
          .map((path) => loadScreen(path, true, true))
      ).catch(() => null);
    }, ADMIN_ACTIVE_POLL_MS);
    return () => {
      if (adminPollRef.current) {
        clearInterval(adminPollRef.current);
      }
    };
  }, [activePath, loadScreen]);

  const handleMarkMessageRead = useCallback(
    async (messageId, options = {}) => {
      const { refresh = true } = options;
      const result = await requestJson(session, "POST", `/api/app/messages/${messageId}/read/`);
      if (refresh) {
        await loadScreen("/messages", true);
      }
      return result;
    },
    [loadScreen, session]
  );

  const handleDeleteMessage = useCallback(
    async (messageId, options = {}) => {
      const { refresh = true } = options;
      const result = await requestJson(session, "DELETE", `/api/app/messages/${messageId}/`);
      if (refresh) {
        await loadScreen("/messages", true);
      }
      return result;
    },
    [loadScreen, session]
    );

  const handleCreateStudent = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/students/create/", payload);
      addAdminNotification({
        category: "Students",
        module: "Student Registration",
        action: `Registered student ${payload?.first_name || payload?.name || result?.student?.name || "record"} on the platform.`,
        status: "Success",
        priority: "Medium",
        tone: "success",
      });
      await       Promise.all([
        loadScreen("/students", true),
        loadScreen("/enrollments", true),
        loadScreen("/dashboard", true),
      ]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
    );

  const handleCreateTeacher = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/teachers/create/", payload);
      await       Promise.all([
        loadScreen("/teachers", true),
        loadScreen("/dashboard", true),
        loadScreen("/messages", true),
      ]);
      return result;
    },
    [loadScreen, session]
    );

  const handleCreateEnrollment = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/enrollments/create/", payload);
      addAdminNotification({
        category: "Students",
        module: "Enrollments",
        action: "Created a new student enrollment record.",
        status: "Success",
        priority: "Medium",
        tone: "success",
      });
      await Promise.all([
        loadScreen("/enrollments", true),
        loadScreen("/students", true),
      loadScreen("/messages", true),
      loadScreen("/dashboard", true),
    ]);
    return result;
  },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminWithdraw = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/withdraw/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Withdrawals",
        action: `Recorded withdrawal request${payload?.amount ? ` of ${NAIRA_SYMBOL}${payload.amount}` : ""}.`,
        status: "Pending",
        priority: "High",
        tone: "warning",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminPaymentAccountSave = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/payment-account/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Payment Accounts",
        action: "Updated school payment account settings.",
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminClassFeeSave = useCallback(
    async (payload) => {
      const method = payload.id ? "PATCH" : "POST";
      const url = payload.id ? `/api/finance/admin/class-fees/${payload.id}/` : "/api/finance/admin/class-fees/";
      const { id, ...body } = payload;
      const result = await requestJson(session, method, url, body);
      addAdminNotification({
        category: "Finance",
        module: "Class Fees",
        action: `${payload.id ? "Updated" : "Created"} class fee record${payload?.amount ? ` for ${NAIRA_SYMBOL}${payload.amount}` : ""}.`,
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/expenses", true), loadScreen("/students", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminClassFeeDelete = useCallback(
    async (feeId) => {
      const result = await requestJson(session, "DELETE", `/api/finance/admin/class-fees/${feeId}/`);
      await Promise.all([loadScreen("/finance", true), loadScreen("/expenses", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [loadScreen, session]
  );

  const handleAdminStudentFeeSave = useCallback(
    async (payload) => {
      const { id, ...body } = payload;
      const result = await requestJson(session, "PATCH", `/api/finance/admin/fees/${id}/`, body);
      addAdminNotification({
        category: "Finance",
        module: "Student Fees",
        action: `Updated a student fee${payload?.amount ? ` to ${NAIRA_SYMBOL}${payload.amount}` : ""}.`,
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminExpenseCreate = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/expenses/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Expenses",
        action: `Created expense record${payload?.amount ? ` of ${NAIRA_SYMBOL}${payload.amount}` : ""}.`,
        status: "Success",
        priority: "Medium",
        tone: "info",
      });
      await loadScreen("/expenses", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminExpenseDelete = useCallback(
    async (recordId) => {
      const result = await requestJson(session, "DELETE", `/api/finance/admin/expenses/${recordId}/`);
      await loadScreen("/expenses", true);
      return result;
    },
    [loadScreen, session]
  );

  const handleBankPaymentsIngest = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/bank-payments/ingest/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Bank Payments",
        action: "Imported bank payment records for reconciliation.",
        status: "Success",
        priority: "High",
        tone: "info",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleBankPaymentRecover = useCallback(
    async (paymentId, payload) => {
      const result = await requestJson(session, "POST", `/api/finance/admin/bank-payments/${paymentId}/recover/`, payload);
      addAdminNotification({
        category: "Finance",
        module: "Payment Recovery",
        action: "Recovered or matched a bank payment to a student account.",
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await Promise.all([loadScreen("/finance", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleActivationCreditPurchase = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/activation-credits/purchase/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Activation Tokens",
        action: `Started activation token purchase${payload?.credits ? ` for ${payload.credits} tokens` : ""}.`,
        status: "Pending",
        priority: "High",
        tone: "warning",
      });
      return result;
    },
    [addAdminNotification, session]
  );

  const handleActivationCreditVerify = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/activation-credits/verify/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Activation Tokens",
        action: "Verified activation token purchase.",
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await loadScreen("/finance", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleActivationCreditAssign = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/activation-credits/assign/", payload);
      addAdminNotification({
        category: "Finance",
        module: "Activation Tokens",
        action: "Assigned activation tokens to student accounts.",
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await loadScreen("/finance", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleActivationCreditSettings = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/finance/admin/activation-credits/settings/", payload);
      await loadScreen("/finance", true);
      return result;
    },
    [loadScreen, session]
  );

  const handleActivationCreditRunAuto = useCallback(
    async () => {
      const result = await requestJson(session, "POST", "/api/finance/admin/activation-credits/run-auto/", {});
      addAdminNotification({
        category: "System",
        module: "Auto Activation",
        action: "Ran automatic student activation token deductions.",
        status: "Success",
        priority: "High",
        tone: "info",
      });
      await loadScreen("/finance", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const refreshHr = useCallback(async () => {
    await Promise.all([loadScreen("/hr/activity", true), loadScreen("/non-teaching-staff", true), loadScreen("/dashboard", true)]);
  }, [loadScreen]);

  const handleCreateHrStaff = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/hr/staff/create/", payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleUpdateHrStaff = useCallback(
    async (staffId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/hr/staff/${staffId}/`, payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleMarkHrAttendance = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/hr/attendance/mark/", payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleCreateHrPayroll = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/hr/payroll/create/", payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleCreateHrLeave = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/hr/leave/create/", payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleReviewHrLeave = useCallback(
    async (leaveId, nextStatus) => {
      const result = await requestJson(session, "POST", `/api/hr/leave/${leaveId}/review/`, { status: nextStatus });
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleCreateHrAdvance = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/hr/advances/create/", payload);
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const handleReviewHrAdvance = useCallback(
    async (advanceId, nextStatus) => {
      const result = await requestJson(session, "POST", `/api/hr/advances/${advanceId}/review/`, { status: nextStatus });
      await refreshHr();
      return result;
    },
    [refreshHr, session]
  );

  const downloadHrFile = useCallback(
    async (endpoint, filename) => {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: session?.access ? { Authorization: `Bearer ${session.access}` } : {},
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message || "Download failed.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
    [session]
  );

  const handleDownloadHrTeachers = useCallback(
    () => downloadHrFile("/api/hr/staff/download/?type=teaching", "teaching_staff_data.csv"),
    [downloadHrFile]
  );

  const handleDownloadSharedStaffQr = useCallback(
    () => downloadHrFile(`/api/attendance/qr-code/download/?user_id=${encodeURIComponent(session?.user?.id || "")}`, "staff_attendance_qr.png"),
    [downloadHrFile, session]
  );

  const handleCreateClass = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/classes/create/", payload);
      addAdminNotification({
        category: "System",
        module: "Classes",
        action: `Created class ${payload?.name || payload?.class_name || "record"}.`,
        status: "Success",
        priority: "Medium",
        tone: "success",
      });
      await loadScreen("/classes", true);
      await loadScreen("/dashboard", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleUpdateClass = useCallback(
    async (classId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/app/classes/${classId}/`, payload);
      addAdminNotification({
        category: "System",
        module: "Classes",
        action: `Updated class ${payload?.name || payload?.class_name || classId}.`,
        status: "Success",
        priority: "Medium",
        tone: "info",
      });
      await loadScreen("/classes", true);
      await loadScreen("/dashboard", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleBulkClassPromotion = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/classes/promotions/", payload);
      if (payload?.action === "apply") {
        addAdminNotification({
          category: "Students",
          module: "Class Promotions",
          action: result?.message || "Applied bulk class promotion.",
          status: "Success",
          priority: "High",
          tone: "success",
        });
        await Promise.all([
          loadScreen("/classes", true),
          loadScreen("/students", true),
          loadScreen("/dashboard", true),
          loadScreen("/results", true),
        ]);
      }
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleCreateSubject = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/subjects/create/", payload);
      const savedSubject = result?.subject;
      if (savedSubject?.id) {
        const addSubject = (subjects = []) => {
          const exists = subjects.some((subject) => String(subject.id) === String(savedSubject.id));
          return exists ? subjects : [...subjects, savedSubject].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        };
        setScreenData((previous) => ({
          ...previous,
          "/classes": previous["/classes"]
            ? { ...previous["/classes"], subjects: addSubject(previous["/classes"].subjects || []) }
            : previous["/classes"],
          "/teachers": previous["/teachers"]
            ? {
                ...previous["/teachers"],
                options: {
                  ...(previous["/teachers"].options || {}),
                  subjects: addSubject(previous["/teachers"].options?.subjects || []),
                },
              }
            : previous["/teachers"],
          "/exams": previous["/exams"]
            ? {
                ...previous["/exams"],
                options: {
                  ...(previous["/exams"].options || {}),
                  subjects: addSubject(previous["/exams"].options?.subjects || []),
                },
              }
            : previous["/exams"],
          "/results": previous["/results"]
            ? {
                ...previous["/results"],
                options: {
                  ...(previous["/results"].options || {}),
                  subjects: addSubject(previous["/results"].options?.subjects || []),
                },
              }
            : previous["/results"],
        }));
      }
      await Promise.all([
        loadScreen("/classes", true),
        loadScreen("/teachers", true),
        loadScreen("/exams", true),
        loadScreen("/results", true),
      ]);
      return result;
    },
    [loadScreen, session]
  );

  const handleDeleteSubject = useCallback(
    async (subjectId) => {
      const result = await requestJson(session, "DELETE", `/api/app/subjects/${subjectId}/`);
      await Promise.all([
        loadScreen("/classes", true),
        loadScreen("/teachers", true),
      ]);
      return result;
    },
    [loadScreen, session]
  );

  const handleUpdateStudent = useCallback(
    async (studentId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/app/students/${studentId}/`, payload);
      addAdminNotification({
        category: "Students",
        module: "Profile Updates",
        action: `Updated student profile record ${payload?.student_id || studentId}.`,
        status: "Success",
        priority: "Medium",
        tone: "info",
      });
      await Promise.all([
        loadScreen("/students", true),
        loadScreen("/enrollments", true),
        loadScreen("/dashboard", true),
      ]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleDeleteStudent = useCallback(
    async (studentId) => {
      const result = await requestJson(session, "DELETE", `/api/app/students/${studentId}/`);
      addAdminNotification({
        category: "Students",
        module: "Profile Updates",
        action: `Deleted student profile record ${studentId}.`,
        status: "Deleted",
        priority: "High",
        tone: "warning",
      });
      await Promise.all([
        loadScreen("/students", true),
        loadScreen("/enrollments", true),
        loadScreen("/dashboard", true),
      ]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleUpdateTeacher = useCallback(
    async (teacherId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/app/teachers/${teacherId}/`, payload);
      await Promise.all([
        loadScreen("/teachers", true),
        loadScreen("/dashboard", true),
        loadScreen("/messages", true),
      ]);
      return result;
    },
    [loadScreen, session]
  );

  const handleDeleteTeacher = useCallback(
    async (teacherId) => {
      const result = await requestJson(session, "DELETE", `/api/app/teachers/${teacherId}/`);
      await Promise.all([
        loadScreen("/teachers", true),
        loadScreen("/dashboard", true),
        loadScreen("/messages", true),
      ]);
      return result;
    },
    [loadScreen, session]
  );

  const handleSaveSettings = useCallback(
    async (payload) => {
      const result = await requestJson(session, "PATCH", "/api/app/school/settings/", payload);
      if (result?.school) {
        const nextSession = {
          ...session,
          school: result.school,
          school_code: result.school.school_code || session?.school_code || "",
        };
        writeStoredSession(nextSession);
        onSessionUpdate?.(nextSession);
      }
      setScreenData((previous) => ({ ...previous, "/settings": result }));
      addAdminNotification({
        category: "System",
        module: "Admin Settings",
        action: "Updated school administration settings.",
        status: "Success",
        priority: "High",
        tone: "warning",
      });
      await Promise.all(Object.keys(ADMIN_ENDPOINTS).map((path) => loadScreen(path, true)));
      return result;
    },
    [addAdminNotification, loadScreen, onSessionUpdate, session]
    );

  const handleSubmitSupportTicket = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/support-tickets/", payload);
      if (result?.ticket) {
        setScreenData((previous) => ({
          ...previous,
          "/settings": {
            ...(previous["/settings"] || {}),
            support_tickets: [
              result.ticket,
              ...((previous["/settings"]?.support_tickets || []).filter((item) => item.id !== result.ticket.id)),
            ].slice(0, 8),
          },
        }));
      }
      addAdminNotification({
        category: "System",
        module: "Support Center",
        action: `Submitted support ticket: ${payload.subject || "School support request"}.`,
        status: "Open",
        priority: "High",
        tone: "info",
      });
      return result;
    },
    [addAdminNotification, session]
  );

  const handleUploadExamResults = useCallback(
    async (examId, file) => {
      const parsedId = Number(examId);
      if (!parsedId || Number.isNaN(parsedId)) {
        throw new Error("Select a valid exam before uploading.");
      }
      const formData = new FormData();
      formData.append("file", file);
      const result = await requestJson(session, "POST", `/api/app/exams/${parsedId}/results/upload/`, formData);
      addAdminNotification({
        category: "Exams",
        module: "Result Uploads",
        action: `Uploaded result file for exam ${parsedId}.`,
        status: "Success",
        priority: "High",
        tone: "success",
      });
      await loadScreen("/exams", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleDeleteExamResult = useCallback(
    async (attemptId) => {
      const result = await requestJson(session, "DELETE", `/api/app/exams/results/${attemptId}/`);
      addAdminNotification({
        category: "Exams",
        module: "CBT Results",
        action: `Deleted CBT result attempt ${attemptId}; retake is now available.`,
        status: "Deleted",
        priority: "High",
        tone: "warning",
      });
      await Promise.all([loadScreen("/exams", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleDatabaseImportUpload = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/database-imports/", payload);
      addAdminNotification({
        category: "System",
        module: "Database Import",
        action: `Uploaded ${payload?.file?.name || "migration file"} for validation.`,
        status: result?.success ? "Validated" : "Needs Review",
        priority: "High",
        tone: result?.success ? "success" : "warning",
      });
      await loadScreen("/database-import", true);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminCreateExam = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/exams/create/", payload);
      addAdminNotification({
        category: "Exams",
        module: "CBT Exam Builder",
        action: `Created exam ${payload?.title || "record"}.`,
        status: payload?.is_published ? "Published" : "Draft",
        priority: "High",
        tone: "success",
      });
      await Promise.all([loadScreen("/exams", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminUpdateExam = useCallback(
    async (examId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/app/exams/${examId}/`, payload);
      addAdminNotification({
        category: "Exams",
        module: "CBT Exam Builder",
        action: `Updated exam ${payload?.title || examId}.`,
        status: payload?.is_published ? "Published" : "Updated",
        priority: "High",
        tone: "info",
      });
      await Promise.all([loadScreen("/exams", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleAdminDeleteExam = useCallback(
    async (examId) => {
      const result = await requestJson(session, "DELETE", `/api/app/exams/${examId}/`);
      addAdminNotification({
        category: "Exams",
        module: "CBT Exam Builder",
        action: `Deleted exam ${examId}.`,
        status: "Deleted",
        priority: "High",
        tone: "warning",
      });
      await Promise.all([loadScreen("/exams", true), loadScreen("/results", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleSearchReport = useCallback(
    async (studentId) => {
      const trimmed = String(studentId || "").trim();
      if (!trimmed) {
        throw new Error("Enter a student ID first.");
      }
      const result = await requestJson(session, "GET", `/api/app/results/?student_id=${encodeURIComponent(trimmed)}`);
      setScreenData((previous) => ({ ...previous, "/results": result }));
      return result;
    },
    [session]
  );

  const handleReviewResultBatch = useCallback(
    async (batchId, nextStatus) => {
      const result = await requestJson(session, "POST", `/api/app/results/batches/${batchId}/review/`, { status: nextStatus });
      addAdminNotification({
        category: "Exams",
        module: "Published Student Results",
        action: nextStatus === "published"
          ? `Published student result batch ${batchId}. Students can now view the result.`
          : `Reviewed student result batch ${batchId} and set status to ${nextStatus}.`,
        status: nextStatus === "published" ? "Success" : "Info",
        priority: nextStatus === "published" ? "High" : "Medium",
        tone: nextStatus === "published" ? "success" : "info",
      });
      await Promise.all([loadScreen("/results", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [addAdminNotification, loadScreen, session]
  );

  const handleDeleteResultBatch = useCallback(
    async (batchId) => {
      const result = await requestJson(session, "DELETE", `/api/app/results/batches/${batchId}/`);
      await Promise.all([loadScreen("/results", true), loadScreen("/dashboard", true)]);
      return result;
    },
    [loadScreen, session]
  );

  const handleLoadTranscript = useCallback(
    async (studentId, options = {}) => requestJson(session, "GET", `/api/app/documents/transcripts/${studentId}/${options.generate ? "?generate=true" : ""}`),
    [session]
  );

  const handleSaveTranscript = useCallback(
    async (studentId, payload) => requestJson(session, "PATCH", `/api/app/documents/transcripts/${studentId}/`, payload),
    [session]
  );

  const handleLoadTestimonial = useCallback(
    async (studentId, options = {}) => requestJson(session, "GET", `/api/app/documents/testimonials/${studentId}/${options.generate ? "?generate=true" : ""}`),
    [session]
  );

  const handleSaveTestimonial = useCallback(
    async (studentId, payload) => requestJson(session, "PATCH", `/api/app/documents/testimonials/${studentId}/`, payload),
    [session]
  );

  const data = screenData[activePath];
  const loading = Boolean(screenLoading[activePath]);
  const error = screenError[activePath] || "";
  const activeSchool = data?.school || data?.local_data?.school || null;
  const schoolName =
    activeSchool?.name ||
    screenData["/settings"]?.school?.name ||
    session?.schoolName ||
    session?.school_code ||
session?.schoolCode ||
    "School OS";
  const schoolBrand = resolveSchoolBrand(activeSchool, screenData["/settings"]?.school, screenData["/dashboard"]?.school, session?.school, session);

  useEffect(() => {
    document.title = schoolBrand.name;
    document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", schoolBrand.name);
    window.schoolDomPWA?.setBrand?.(schoolBrand);
  }, [schoolBrand.name, schoolBrand.logo]);

const unreadNotificationsCount =
    Number(screenData["/messages"]?.summary?.unread_notifications ?? screenData["/dashboard"]?.metrics?.unread_notifications ?? 0) +
    Number(screenData["/messages"]?.summary?.unread_inbox ?? 0) +
    adminActivityRecords.filter((item) => !item.isRead).length;

  let content = null;
  if (activePath === "/dashboard") {
        content = (
      <AdminDashboardScreen
        user={session?.user}
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onBroadcastMessage={handleSendMessage}
      />
    );
  } else if (activePath === "/performance-heatmap") {
    content = (
      <AdminPerformanceHeatmapScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
      />
    );
  } else if (activePath === "/finance") {
    content = (
      <AdminFinanceScreen
        data={data}
        school={screenData["/settings"]?.school || screenData["/dashboard"]?.school || session?.school}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onWithdraw={handleAdminWithdraw}
        onPaymentAccountSave={handleAdminPaymentAccountSave}
        onClassFeeSave={handleAdminClassFeeSave}
        onClassFeeDelete={handleAdminClassFeeDelete}
        onStudentFeeSave={handleAdminStudentFeeSave}
        onPurchaseCredits={handleActivationCreditPurchase}
        onVerifyCredits={handleActivationCreditVerify}
        onAssignCredits={handleActivationCreditAssign}
        onCreditSettings={handleActivationCreditSettings}
        onRunAutoCredits={handleActivationCreditRunAuto}
        onBankPaymentsIngest={handleBankPaymentsIngest}
        onBankPaymentRecover={handleBankPaymentRecover}
      />
    );
  } else if (activePath === "/expenses") {
    content = (
      <AdminExpenseTrackerScreen
        data={data}
        school={screenData["/settings"]?.school || screenData["/dashboard"]?.school || session?.school}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleAdminExpenseCreate}
        onDelete={handleAdminExpenseDelete}
        onClassFeeSave={handleAdminClassFeeSave}
        onClassFeeDelete={handleAdminClassFeeDelete}
      />
    );
  } else if (activePath === "/hr-self-service") {
    content = (
      <StaffSelfServicePanel
        session={session}
        initialData={data}
        standalone
        onRefresh={() => loadScreen("/hr-self-service", true)}
      />
    );
  } else if (activePath === "/hr") {
    content = (
      <AdminHRPayrollScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onMarkAttendance={handleMarkHrAttendance}
        onCreateLeave={handleCreateHrLeave}
        onReviewLeave={handleReviewHrLeave}
        onCreateAdvance={handleCreateHrAdvance}
        onReviewAdvance={handleReviewHrAdvance}
      />
    );
  } else if (activePath === "/non-teaching-staff") {
    content = (
      <AdminNonTeachingStaffScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreateStaff={handleCreateHrStaff}
        onUpdateStaff={handleUpdateHrStaff}
        onDownloadTeachers={handleDownloadHrTeachers}
        onDownloadSharedQr={handleDownloadSharedStaffQr}
      />
    );
  } else if (activePath === "/hr/activity") {
    content = (
      <AdminHRPayrollScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onMarkAttendance={handleMarkHrAttendance}
        onCreateLeave={handleCreateHrLeave}
        onReviewLeave={handleReviewHrLeave}
        onCreateAdvance={handleCreateHrAdvance}
        onReviewAdvance={handleReviewHrAdvance}
      />
    );
  } else if (activePath === "/attendance") {
    content = <AttendanceModule session={session} />;
  } else if (activePath === "/messages") {
    content = (
      <AdminMessagesScreen
        user={session?.user}
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onSendMessage={handleSendMessage}
        onMarkRead={handleMarkMessageRead}
        onDelete={handleDeleteMessage}
      />
    );
  } else if (activePath === "/students") {
    content = (
      <AdminStudentsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleCreateStudent}
        onUpdate={handleUpdateStudent}
        onDelete={handleDeleteStudent}
      />
    );
  } else if (activePath === "/id-cards") {
    content = (
      <AdminIdCardsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        session={session}
        school={schoolBrand}
      />
    );
  } else if (activePath === "/documents") {
    content = (
      <AdminDocumentsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        school={schoolBrand}
        onLoadTranscript={handleLoadTranscript}
        onLoadTestimonial={handleLoadTestimonial}
        onSaveTranscript={handleSaveTranscript}
        onSaveTestimonial={handleSaveTestimonial}
      />
    );
  } else if (activePath === "/teachers") {
    content = (
      <AdminTeachersScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleCreateTeacher}
        onUpdate={handleUpdateTeacher}
        onDelete={handleDeleteTeacher}
      />
    );
  } else if (activePath === "/enrollments") {
    content = (
      <AdminEnrollmentsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleCreateEnrollment}
      />
    );
  } else if (activePath === "/classes") {
    content = (
      <AdminClassesScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleCreateClass}
        onUpdate={handleUpdateClass}
        onBulkPromotion={handleBulkClassPromotion}
        onCreateSubject={handleCreateSubject}
        onDeleteSubject={handleDeleteSubject}
      />
    );
  } else if (activePath === "/exams") {
    content = (
      <AdminExamResultsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onUpload={handleUploadExamResults}
        onDeleteResult={handleDeleteExamResult}
        onDeleteExam={handleAdminDeleteExam}
        session={session}
        onCreateExam={handleAdminCreateExam}
        onUpdateExam={handleAdminUpdateExam}
      />
    );
  } else if (activePath === "/results") {
    content = (
      <AdminResultsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onSearch={handleSearchReport}
        onReviewBatch={handleReviewResultBatch}
        onDeleteBatch={handleDeleteResultBatch}
      />
    );
  } else if (activePath === "/database-import") {
    content = (
      <AdminDatabaseImportScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onUpload={handleDatabaseImportUpload}
      />
    );
  } else {
    content = (
      <AdminSettingsScreen
        data={data}
        loading={loading}
        error={error}
        onRetry={handleRetry}
        onSave={handleSaveSettings}
        onSubmitSupportTicket={handleSubmitSupportTicket}
        themePreference={themePreference}
        onThemeChange={onThemeChange}
          />
            );
  }

  return (
    <main className={`app-shell-page ${navOpen ? "nav-open" : ""}`}>
      <aside className="app-sidebar">
        <div className="brand-block">
          <SchoolBrand school={schoolBrand} subtitle={roleLabel(session?.user?.role) || "Staff"} compact />
        </div>

        <nav className="app-nav" aria-label="Main navigation">
          {visibleRoutes.map((route) => {
            if (route.children) {
              const isOpen = dropdownOpen === route.path;
              return (
                <div key={route.path} className="nav-dropdown">
                  <button
                    type="button"
                    className={`nav-item ${isOpen ? "dropdown-open" : ""} ${route.children.some(child => activePath === child.path) ? "active" : ""}`}
                    onClick={() => {
                      setDropdownOpen(isOpen ? null : route.path);
                    }}
                  >
                    {route.label}
                    <span className="dropdown-arrow">{isOpen ? "-" : "+"}</span>
                  </button>
                  {isOpen && (
                    <div className="nav-dropdown-content">
                      {route.children.map((child) => (
                        <button
                          key={child.path}
                          type="button"
                          className={`nav-item nav-dropdown-item ${activePath === child.path ? "active" : ""}`}
                          onClick={() => {
                            onNavigate(child.path);
                            setNavOpen(false);
                            setDropdownOpen(null);
                          }}
                        >
                          {child.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            } else {
              return (
                <button
                  key={route.path}
                  type="button"
                  className={`nav-item ${activePath === route.path ? "active" : ""}`}
                  onClick={() => {
                    onNavigate(route.path);
                    setNavOpen(false);
                  }}
                >
                  {route.label}
                </button>
              );
            }
          })}
        </nav>

        <div className="role-chip">{roleLabel(session?.user?.role)}</div>
      </aside>
      <div
        className="app-sidebar-overlay"
        role="presentation"
        onClick={() => setNavOpen(false)}
      />

      <section className="app-main">
        <header className="app-topbar">
          <div>
            <p className="topbar-kicker">Protected Workspace</p>
            <h2>{(() => {
              const route = visibleRoutes.find((item) => item.path === activePath);
              if (route) return route.label;
              // Check child routes
              for (const parentRoute of visibleRoutes) {
                if (parentRoute.children) {
                  const childRoute = parentRoute.children.find((child) => child.path === activePath);
                  if (childRoute) return childRoute.label;
                }
              }
              return "Dashboard";
            })()}</h2>
          </div>
          <div className="topbar-user">
            <button type="button" className="menu-toggle" onClick={() => setNavOpen((prev) => !prev)}>
              <span className="menu-bars" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
            <button type="button" className="notification-button" onClick={() => setNotificationsOpen(true)}>
              <BellIcon className="inline-icon" />
              <span>Notifications</span>
              {unreadNotificationsCount > 0 ? <strong className="notification-badge">{unreadNotificationsCount}</strong> : null}
            </button>
            <div className="avatar">
              {session?.user?.profile_picture ? (
                <img src={session.user.profile_picture} alt={userDisplayName(session.user)} />
              ) : (
                userInitials(session?.user)
              )}
            </div>
            <div className="user-meta">
              <p>{userDisplayName(session?.user)}</p>
              <span>{session?.user?.email}</span>
            </div>
            <button type="button" className="signout-button" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </header>
        
        <Suspense fallback={<ScreenState loading />}>
          {content}
        </Suspense>
        {notificationsOpen ? (
          <div className="notification-drawer-overlay" role="presentation" onClick={() => setNotificationsOpen(false)}>
            <aside className="notification-drawer" role="dialog" aria-modal="true" aria-label="Admin notifications" onClick={(event) => event.stopPropagation()}>
              <AdminNotificationsCenter
                session={session}
                data={screenData["/messages"]}
                activityRecords={adminActivityRecords}
                loading={Boolean(screenLoading["/messages"])}
                error={screenError["/messages"] || ""}
                onRetry={handleNotificationsRefresh}
                onMarkRead={handleMarkMessageRead}
                onMarkActivityRead={markAdminActivityRead}
                isPopup
                onClose={() => setNotificationsOpen(false)}
              />
            </aside>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function DashboardHome({ session, onSignOut, themePreference, onThemeChange, onNavigate }) {
    const [data, setData] = useState(null);
const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const initialLoadRef = useRef(false);
  const inflightRequestRef = useRef(null);
  const role = session?.user?.role;

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const isErrorPage = Boolean(error && !loading);
    document.body.classList.toggle("dashboard-error-active", isErrorPage);
    return () => document.body.classList.remove("dashboard-error-active");
  }, [error, loading]);

  const pollIntervalMs = useMemo(() => {
    if (role === "student") {
      return STUDENT_POLL_INTERVAL_MS;
    }
    if (role === "teacher") {
      return TEACHER_POLL_INTERVAL_MS;
    }
    return DEFAULT_POLL_INTERVAL_MS;
  }, [role]);

  const loadDashboard = useCallback(async () => {
    if (inflightRequestRef.current) {
      return inflightRequestRef.current;
    }

    setIsRefreshing(true);
    setError("");
    
      const pending = fetchDashboardSnapshot(session)
      .then((snapshot) => {
      setData(snapshot);
        setLastUpdated(new Date());
    return snapshot;
      })
      .catch((requestError) => {
      if (requestError?.authExpired || requestError?.status === 401 || requestError?.statusCode === 401) {
        onSignOut();
        return null;
      }
      setError(requestError.message || "Could not load dashboard.");
    throw requestError;
      })
      .finally(() => {
      setLoading(false);
    setIsRefreshing(false);
        inflightRequestRef.current = null;
      });

    inflightRequestRef.current = pending;
    return pending;
  }, [onSignOut, session]);

  useEffect(() => {
    if (initialLoadRef.current) {
      return;
    }
    initialLoadRef.current = true;
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const handle = setInterval(() => {
      if (document.visibilityState === "visible") {
        loadDashboard();
      }
    }, pollIntervalMs);
    return () => clearInterval(handle);
  }, [loadDashboard, pollIntervalMs]);

  useEffect(() => {
    let refreshTimer = null;
    const handleDataMutation = () => {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        if (document.visibilityState === "visible") {
          loadDashboard();
        }
      }, 120);
    };
    window.addEventListener(SCHOOL_DATA_MUTATED_EVENT, handleDataMutation);
    return () => {
      window.clearTimeout(refreshTimer);
      window.removeEventListener(SCHOOL_DATA_MUTATED_EVENT, handleDataMutation);
    };
  }, [loadDashboard]);

  const handlePromptResponse = useCallback(
    async (promptId, responseText) => {
      await postJson(session, "/api/app/questions/answer/", {
        prompt_id: promptId,
        response_text: responseText,
      });
      await loadDashboard();
  },
    [loadDashboard, session]
  );

  const handleCreatePrompt = useCallback(
    async (payload) => {
      const result = await postJson(session, "/api/app/questions/create/", payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleNotifyExam = useCallback(
async (examId, payload) => {
const result =     await postJson(session, `/api/app/exams/${examId}/notify/`, payload);
    await loadDashboard();
      return result;
  },
    [loadDashboard, session]
  );

  const handleCreateExam = useCallback(
    async (payload) => {
      try {
        const result = await postJson(session, "/api/app/exams/create/", payload);
        await loadDashboard();
        return result;
      } catch (createError) {
        if (!navigator.onLine || String(createError.message || "").toLowerCase().includes("network")) {
          queueOfflineExamCreate(payload);
          return { success: true, offline: true, message: "Exam saved offline. It will sync when internet is available." };
        }
        throw createError;
      }
    },
    [loadDashboard, session]
  );

  useEffect(() => {
    if (!session || session?.user?.role !== "teacher") return undefined;
    let syncing = false;
    const syncOfflineExamCreates = async () => {
      if (syncing || !navigator.onLine) return;
      const queue = readOfflineExamCreateQueue();
      if (!queue.length) return;
      syncing = true;
      const remaining = [];
      for (const item of queue) {
        try {
          await postJson(session, "/api/app/exams/create/", item.payload);
        } catch {
          remaining.push(item);
        }
      }
      writeOfflineExamCreateQueue(remaining);
      syncing = false;
      if (remaining.length !== queue.length) {
        await loadDashboard();
      }
    };
    window.addEventListener("online", syncOfflineExamCreates);
    syncOfflineExamCreates();
    return () => window.removeEventListener("online", syncOfflineExamCreates);
  }, [loadDashboard, session]);

  const handleUpdateExam = useCallback(
    async (examId, payload) => {
      const result = await requestJson(session, "PATCH", `/api/app/exams/${examId}/`, payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleMessageSend = useCallback(
async (recipientValue, subject, body, attachments = []) => {
    const payload = {
        subject,
        body,
      };
      if (recipientValue) {
        payload.recipient_email = recipientValue;
      }
      attachments.forEach((file) => {
        if (!payload.attachments) payload.attachments = [];
        payload.attachments.push(file);
      });
      const result = await postJson(session, "/api/app/messages/send/", payload);
    await loadDashboard();
      return result;
  },
    [loadDashboard, session]
  );

  const handleMarkMessageRead = useCallback(
async (messageId) => {
    await requestJson(session, "POST", `/api/app/messages/${messageId}/read/`);
      await loadDashboard();
    },
    [loadDashboard, session]
  );

  const handleDeleteMessage = useCallback(
    async (messageId) => {
      await requestJson(session, "DELETE", `/api/app/messages/${messageId}/`);
    await loadDashboard();
  },
    [loadDashboard, session]
  );

  const handleStudentOfflineSubmit = useCallback(
async (examId, payload) => {
const result =     await postJson(session, `/api/app/exams/${examId}/offline-submit/`, payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleStudentResults = useCallback(async () => {
    return requestJson(session, "GET", "/api/app/results/my/");
  }, [session]);

  const handleTeacherCreateQuestion = useCallback(
    async (payload) => {
      const result = await postJson(session, "/api/app/exams/questions/", payload);
    await loadDashboard();
      return result;
  },
    [loadDashboard, session]
  );

  const handleTeacherGradeSubmission = useCallback(
    async (submissionId, payload) => {
      const result = await postJson(session, `/api/app/exams/submissions/${submissionId}/grade/`, payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleTeacherSendClassMessage = useCallback(
    async (payload) => {
      const result = await postJson(session, "/api/app/messages/send/", { ...payload, target: "class" });
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleTeacherSubmitScore = useCallback(
    async (payload) => {
      const result = await postJson(session, "/api/app/results/submit/", payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleTeacherResultsSnapshot = useCallback(
    async () => {
      return requestJson(session, "GET", "/api/app/results/?teacher_only=1");
    },
    [session]
  );

  const handleTeacherClassStudents = useCallback(
    async (classId = "", subjectId = "") => {
      const params = new URLSearchParams();
      if (classId) params.set("class_id", classId);
      if (subjectId) {
        params.set("context", "results");
        params.set("subject_id", subjectId);
      }
      const query = params.toString() ? `?${params.toString()}` : "";
      return requestJson(session, "GET", `/api/app/attendance/class-students/${query}`);
    },
    [session]
  );

  const handleTeacherPushResults = useCallback(
    async (payload) => {
      const result = await postJson(session, "/api/app/results/push/", payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const handleSaveTeacherGradeScale = useCallback(
    async (payload) => {
      const result = await requestJson(session, "POST", "/api/app/results/grades/", payload);
      await loadDashboard();
      return result;
    },
    [loadDashboard, session]
  );

  const formatLastUpdated = lastUpdated ? formatDate(lastUpdated) : null;
  const schoolBrand = resolveSchoolBrand(data?.school, session?.school, session);

  useEffect(() => {
    document.title = schoolBrand.name;
    document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", schoolBrand.name);
    window.schoolDomPWA?.setBrand?.(schoolBrand);
  }, [schoolBrand.name, schoolBrand.logo]);

  if (role === "student") {
    return (
<main className="student-page">
        {loading && !data ? (
          <div className="state-panel frosted">
            <h3>Loading dashboard...</h3>
          </div>
        ) : error ? (
      <section className="student-error-scene" aria-live="polite">
        <div className="student-error-bubbles" aria-hidden="true">
          <span className="student-error-bubble bubble-one" />
          <span className="student-error-bubble bubble-two" />
          <span className="student-error-bubble bubble-three" />
          <span className="student-error-bubble bubble-four" />
          <span className="student-error-bubble bubble-five" />
          <span className="student-error-bubble bubble-six" />
        </div>
        <article className="student-error-card">
          <div className="student-error-icon" aria-hidden="true">
            <span />
          </div>
          <p className="topbar-kicker">Connection paused</p>
          <h1>Error</h1>
          <p>{error}</p>
          <div className="student-error-actions">
            <button type="button" className="student-primary-btn" onClick={loadDashboard} disabled={isRefreshing}>
              {isRefreshing ? "Checking..." : "Try again"}
            </button>
          </div>
        </article>
      </section>
    ) : (
      <StudentWorkspace
        session={session}
        data={data}
            onPromptResponse={handlePromptResponse}
        onMessageSend={handleMessageSend}
        onMarkMessageRead={handleMarkMessageRead}
            onDeleteMessage={handleDeleteMessage}
        onOfflineSubmit={handleStudentOfflineSubmit}
        onCheckResults={handleStudentResults}
        onRefresh={loadDashboard}
        onNavigate={onNavigate}
        onSignOut={onSignOut}
        isRefreshing={isRefreshing}
      />
)}
      </main>
    );
  }

  return (
    <main className={`signup-page dashboard-page ${role === "teacher" ? "teacher-dashboard-page" : ""}`}>
      <section className="dashboard-shell">
        {role === "teacher" ? null : (
          <header className="dashboard-header">
            <div>
              <p className="topbar-kicker">{schoolBrand.name}</p>
              <h1>Dashboard</h1>
              <p>
                {session?.user?.full_name || session?.user?.email} - {role}
              </p>
              {formatLastUpdated ? <small>Updated {formatLastUpdated}</small> : null}
            </div>
            <div className="dashboard-actions">
              <button type="button" onClick={loadDashboard} disabled={isRefreshing}>
                {isRefreshing ? "Refreshing..." : "Refresh"}
              </button>
              <button type="button" onClick={onSignOut}>
                Sign out
              </button>
            </div>
          </header>
        )}

        {loading && !data ? (
          <div className="state-panel">
            <h3>Loading dashboard...</h3>
          </div>
        ) : error ? (
          <div className="state-panel">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        ) : role === "teacher" ? (
          <TeacherWorkspace
            session={session}
      data={data}
      onCreatePrompt={handleCreatePrompt}
            onNotifyExam={handleNotifyExam}
            onMessageSend={handleMessageSend}
            onMarkMessageRead={handleMarkMessageRead}
            onDeleteMessage={handleDeleteMessage}
            onCreateQuestion={handleTeacherCreateQuestion}
            onGradeSubmission={handleTeacherGradeSubmission}
            onClassMessageSend={handleTeacherSendClassMessage}
            onSubmitScore={handleTeacherSubmitScore}
            onLoadResults={handleTeacherResultsSnapshot}
            onLoadClassStudents={handleTeacherClassStudents}
            onPushResults={handleTeacherPushResults}
            onSaveGradeScale={handleSaveTeacherGradeScale}
            onCreateExam={handleCreateExam}
            onUpdateExam={handleUpdateExam}
            onRefresh={loadDashboard}
            isRefreshing={isRefreshing}
            themePreference={themePreference}
            onThemeChange={onThemeChange}
            onNavigate={onNavigate}
            onSignOut={onSignOut}
          />
) : role === "staff" ? (
          <StaffSelfServicePanel
            session={session}
            initialData={data}
            standalone
            onRefresh={loadDashboard}
          />
) : (
          <div className="app-panel">
            <h3>Admin dashboard ongoing</h3>
            <p>Reach out to your administrator for additional tools.</p>
          </div>
        )}
      </section>
    </main>
  );
}

export { StudentDashboard, StaffSelfServicePanel, TeacherDashboard, StudentWorkspace, TeacherWorkspace };

function PwaUpdatePrompt() {
  const [status, setStatus] = useState(() =>
    typeof window !== "undefined" && window.schoolDomPWA
      ? window.schoolDomPWA.getStatus()
      : { updateAvailable: false }
  );
  const [message, setMessage] = useState("");

  useEffect(() => {
    const handleStatus = (event) => {
      setStatus((previous) => ({
        ...previous,
        ...(window.schoolDomPWA?.getStatus?.() || {}),
        ...(event?.detail || {}),
      }));
    };
    handleStatus();
    window.addEventListener("schooldom-pwa-install-status", handleStatus);
    return () => window.removeEventListener("schooldom-pwa-install-status", handleStatus);
  }, []);

  const handleUpdate = async () => {
    setMessage("Updating...");
    const result = await window.schoolDomPWA?.updateApp?.();
    if (!result?.updated) {
      setMessage("Reloading the latest version...");
    }
  };

  if (!status.updateAvailable) {
    return null;
  }

  return (
    <div className="pwa-update-prompt" role="status" aria-live="polite">
      <span>{message || "A new SchoolDom update is ready."}</span>
      <button type="button" onClick={handleUpdate}>Update App</button>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(() => readStoredSession());
const [currentPath, setCurrentPath] = useState(() => normalizePath(window.location.pathname || "/"));
  const [themePreference, setThemePreference] = useState(() => readStoredTheme());

  const navigate = useCallback((targetPath, options = {}) => {
    const { replace = false } = options;
    const nextPath = normalizePath(targetPath);
    const current = normalizePath(window.location.pathname || "/");

    if (current === nextPath) {
      setCurrentPath(nextPath);
      return;
    }

    if (replace) {
      window.history.replaceState({}, "", nextPath);
    } else {
      window.history.pushState({}, "", nextPath);
    }
    setCurrentPath(nextPath);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(normalizePath(window.location.pathname || "/"));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

useEffect(() => {
  if (!session) {
    document.body.removeAttribute("data-dashboard-role");
    return;
    }
    const effectiveTheme = session.user?.role === "student" ? "dark" : themePreference;
    document.body.setAttribute("data-theme", effectiveTheme);
    document.body.setAttribute("data-dashboard-role", session.user?.role || "");
    if (session.user?.role !== "student") {
      window.localStorage.setItem(UI_THEME_KEY, themePreference);
    }
  }, [session, themePreference]);

  useEffect(() => {
    if (!session) return;
    const schoolBrand = resolveSchoolBrand(session?.school, session);
    document.title = schoolBrand.name;
    document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", schoolBrand.name);
    window.schoolDomPWA?.setBrand?.(schoolBrand);
  }, [session]);

useEffect(() => {
  let hideTimer = 0;
  let ticking = false;
  const topThreshold = 24;

  const isAtTop = () => Math.max(window.scrollY || 0, 0) <= topThreshold;

  const hideToggleBar = () => {
    window.clearTimeout(hideTimer);
    document.body.classList.add("mobile-toggle-hidden");
  };

  const showToggleBarBriefly = () => {
    if (!isAtTop()) {
      hideToggleBar();
      return;
    }

    document.body.classList.remove("mobile-toggle-hidden");
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      document.body.classList.add("mobile-toggle-hidden");
    }, 2000);
  };

  const updateToggleForScroll = () => {
    if (isAtTop()) {
      showToggleBarBriefly();
    } else {
      hideToggleBar();
    }
    ticking = false;
  };

  const handleScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(updateToggleForScroll);
      ticking = true;
    }
  };

  const handlePageTouch = () => {
    showToggleBarBriefly();
  };

  showToggleBarBriefly();
  window.addEventListener("scroll", handleScroll, { passive: true });
  window.addEventListener("pointerdown", handlePageTouch, { passive: true });
  window.addEventListener("touchstart", handlePageTouch, { passive: true });

  return () => {
    window.clearTimeout(hideTimer);
    window.removeEventListener("scroll", handleScroll);
    window.removeEventListener("pointerdown", handlePageTouch);
    window.removeEventListener("touchstart", handlePageTouch);
    document.body.classList.remove("mobile-toggle-hidden");
  };
}, []);

useEffect(() => {
  if (!session) {
    if (currentPath !== STUDENT_CBT_DESKTOP_PATH && !PUBLIC_ROUTES.has(currentPath)) {
      if (isTeacherAttendanceScanPath(currentPath)) {
        window.sessionStorage.setItem(PENDING_AUTH_REDIRECT_KEY, currentPath);
      }
      navigate("/signin", { replace: true });
    }
    return;
  }

  if (currentPath === ID_CARD_VERIFY_PATH) {
    return;
  }

  if (currentPath !== STUDENT_CBT_DESKTOP_PATH && PUBLIC_ROUTES.has(currentPath)) {
    navigate("/dashboard", { replace: true });
    return;
  }

  if (isTeacherAttendanceScanPath(currentPath)) {
    return;
  }

  const role = session?.user?.role;
  const isAdmin =     role === "school_admin" || role === "principal" || role === "super_admin" || role === "accountant";
if (isAdmin && ADMIN_ROUTE_REDIRECTS[currentPath]) {
      navigate(ADMIN_ROUTE_REDIRECTS[currentPath], { replace: true });
      return;
    }

if (isAdmin && currentPath !== STUDENT_CBT_DESKTOP_PATH && !ADMIN_ROUTE_SET.has(currentPath)) {
      navigate("/dashboard", { replace: true });
      return;
    }

    if (!isAdmin && currentPath !== STUDENT_CBT_DESKTOP_PATH && !STUDENT_ROUTE_SET.has(currentPath) && !isStudentExamPath(currentPath)) {
      navigate("/dashboard", { replace: true });
    }
  }, [currentPath, navigate, session]);

  const handleAuthenticated = useCallback(
    (nextSession) => {
      setSession(nextSession);
      const pendingRedirect = window.sessionStorage.getItem(PENDING_AUTH_REDIRECT_KEY);
      window.sessionStorage.removeItem(PENDING_AUTH_REDIRECT_KEY);
      if (currentPath === STUDENT_CBT_DESKTOP_PATH) {
        navigate(STUDENT_CBT_DESKTOP_PATH, { replace: true });
        return;
      }
      navigate(isTeacherAttendanceScanPath(pendingRedirect) ? pendingRedirect : "/dashboard", { replace: true });
    },
    [currentPath, navigate]
  );

  const handleCbtEntry = useCallback(
    (nextSession, attemptId) => {
      setSession(nextSession);
      navigate(`/exam/${attemptId}`, { replace: true });
    },
    [navigate]
  );

  const handleSignOut = useCallback(() => {
    clearStoredSession();
    setSession(null);
    navigate("/signin", { replace: true });
  }, [navigate]);

  const handleStandaloneMessageSend = useCallback(
    async (recipientValue, subject, body, attachments = []) => {
      return postJson(session, "/api/app/messages/send/", {
        recipient_email: recipientValue,
        subject,
        body,
        attachments,
      });
    },
    [session]
  );

  const withGlobalNotifications = useCallback(
    (content) => (
      <>
        <PwaUpdatePrompt />
        <GlobalHomeButton session={session} currentPath={currentPath} onNavigate={navigate} />
        <GlobalNotificationBell session={session} onNavigate={navigate} />
        {content}
      </>
    ),
    [currentPath, navigate, session]
  );

  const withGlobalHome = useCallback(
    (content) => (
      <>
        <PwaUpdatePrompt />
        <GlobalHomeButton session={session} currentPath={currentPath} onNavigate={navigate} />
        {content}
      </>
    ),
    [currentPath, navigate, session]
  );

  if (currentPath === ID_CARD_VERIFY_PATH) {
    return withGlobalHome(
      <Suspense fallback={<ScreenState loading />}>
        <IdCardVerificationPage />
      </Suspense>
    );
  }

  if (!session) {
    if (currentPath === STUDENT_CBT_DESKTOP_PATH) {
      return (
        <>
          <PwaUpdatePrompt />
          <StudentCbtEntry onEntry={handleCbtEntry} />
        </>
      );
    }
    if (currentPath === "/") {
      return withGlobalHome(<LandingPage onGetStarted={() => navigate("/signin")} />);
    }
    if (currentPath === "/resource") {
      return withGlobalHome(<ResourceCenter onNavigate={navigate} />);
    }
    if (currentPath === "/pricing") {
      return withGlobalHome(<PricingPage onNavigate={navigate} />);
    }
    if (currentPath === "/faq") {
      return withGlobalHome(<FAQPage onNavigate={navigate} />);
    }
    if (currentPath === "/privacy") {
      return withGlobalHome(<PrivacyPolicyPage onNavigate={navigate} />);
    }
    return withGlobalHome(<Signin onAuthenticated={handleAuthenticated} onBack={() => navigate("/")} />);
  }

  const role = session?.user?.role;
  const isAdmin = role === "school_admin" || role === "principal" || role === "super_admin" || role === "accountant";

  if (currentPath === STUDENT_CBT_DESKTOP_PATH) {
    return (
      <>
        <PwaUpdatePrompt />
        <StudentCbtEntry onEntry={handleCbtEntry} />
      </>
    );
  }

  if (isTeacherAttendanceScanPath(currentPath)) {
    return withGlobalNotifications(
      <TeacherQRCodeAttendancePage
        session={session}
        token={getTeacherAttendanceToken(currentPath)}
        onNavigate={navigate}
      />
    );
  }

  if (isAdmin) {
    if (currentPath === STUDENT_CBT_DESKTOP_PATH) {
      return withGlobalHome(
        <ScreenState error="The desktop CBT app is only for student accounts. Sign in as a student on this computer to write an exam." />
      );
    }
    return withGlobalHome(
      <AdminShell
        session={session}
        currentPath={currentPath}
        onNavigate={navigate}
        onSignOut={handleSignOut}
        themePreference={themePreference}
        onThemeChange={setThemePreference}
        onSessionUpdate={setSession}
      />
    );
  }

  if (currentPath === "/quizzes") {
    const content = <QuizHub session={session} onNavigate={navigate} />;
    return role === "student" ? withGlobalHome(content) : withGlobalNotifications(content);
  }

  if (currentPath === "/academic-planning") {
    if (role === "teacher") {
      return withGlobalNotifications(<TeacherPlanningPanel session={session} onNavigate={navigate} standalone />);
    }
    return withGlobalNotifications(<StudentSchemeOfWorkPanel session={session} onNavigate={navigate} standalone />);
  }

  // Exam routes
  if (currentPath === "/exams") {
    const content = <ExamsList session={session} onNavigate={navigate} />;
    return role === "student" ? withGlobalHome(content) : withGlobalNotifications(content);
  }

  if (currentPath.match(/^\/exam\/\d+\/?$/)) {
    const attemptId = parseInt(currentPath.split("/")[2]);
    return withGlobalHome(<ExamCBT attemptId={attemptId} session={session} onNavigate={navigate} />);
  }

  if (currentPath.match(/^\/exam-result\/\d+\/?$/)) {
    const attemptId = parseInt(currentPath.split("/")[2]);
    return withGlobalNotifications(<ExamResult attemptId={attemptId} session={session} onNavigate={navigate} />);
  }

  if (currentPath === "/fees") {
    return withGlobalNotifications(
      <StudentFeesPage
        session={session}
        onNavigate={navigate}
      />
    );
  }

  if (currentPath === "/attendance" && role === "student") {
    return withGlobalNotifications(
      <StudentAttendancePage
        session={session}
        onNavigate={navigate}
      />
    );
  }

  if (currentPath === "/messages") {
    return withGlobalNotifications(
      <StudentMessagesPage
        session={session}
        data={null}
        onMessageSend={handleStandaloneMessageSend}
        onNavigate={navigate}
      />
    );
  }

  if (currentPath === "/results") {
    return withGlobalNotifications(
      <StudentResultsPage
        session={session}
        data={null}
        onNavigate={navigate}
      />
    );
  }

  return withGlobalNotifications(
    <DashboardHome
      session={session}
      onSignOut={handleSignOut}
      themePreference={themePreference}
      onThemeChange={setThemePreference}
      onNavigate={navigate}
    />
  );
}
