import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X, User, MapPin, Users, GraduationCap, Heart, Lock, Activity } from "lucide-react";
import {
  API_BASE_URL,
  ID_CARD_VERIFY_PATH,
  RECOMMENDED_SUBJECT_GROUPS,
  SUPPORT_EMAIL,
} from "./appConstants";
import {
  MultiSelectBox,
  PhoneCountryInput,
  requestJson,
  formatDate,
  userDisplayName,
  userInitials,
  userRoleLabel,
  resolveSchoolBrand,
  academicGroupLabels,
  SchoolBrand,
  roleLabel,
  DashboardIcon,
  FilterIcon,
  MetricCard,
  MessageInboxPanel,
  ScreenState,
  TimetableGridTable,
} from "./AppShared";
import { TeacherExamBuilder } from "./TeacherExamPanels";

function ConfirmModal({ title, message, confirmLabel = "Confirm", danger = false, onConfirm, onCancel }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return createPortal(
    <div className="cfm-overlay" onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="cfm-card" role="alertdialog" aria-modal="true" aria-labelledby="cfm-title">
        <div className={`cfm-icon ${danger ? "cfm-icon--danger" : "cfm-icon--neutral"}`}>
          {danger
            ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          }
        </div>
        <h3 className="cfm-title" id="cfm-title">{title}</h3>
        {message && <p className="cfm-message">{message}</p>}
        <div className="cfm-actions">
          <button type="button" className="cfm-btn cfm-btn--cancel" onClick={onCancel}>Cancel</button>
          <button type="button" className={`cfm-btn cfm-btn--ok${danger ? " cfm-btn--danger" : " cfm-btn--neutral"}`} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function useConfirm() {
  const [state, setState] = useState(null);
  const resolveRef = useRef(null);
  const confirm = useCallback((options) => new Promise((resolve) => {
    resolveRef.current = resolve;
    setState(options);
  }), []);
  const handleConfirm = useCallback(() => { setState(null); resolveRef.current?.(true); }, []);
  const handleCancel = useCallback(() => { setState(null); resolveRef.current?.(false); }, []);
  const dialog = state ? <ConfirmModal {...state} onConfirm={handleConfirm} onCancel={handleCancel} /> : null;
  return [confirm, dialog];
}

const NAIRA_SYMBOL = "\u20A6";
const FINANCE_TABLE_PREVIEW_COUNT = 3;
const ACTIVITY_MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const clampPercent = (value) => Math.max(0, Math.min(100, Number(value || 0)));
const heatTone = (status) => (status === "strong" ? "strong" : status === "watch" ? "watch" : "weak");
const formatAnalyticsAmount = (value) =>
  `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

function CbtStatusPill({ tone = "info", children }) {
  return <span className={`cbt-status-pill tone-${tone}`}>{children}</span>;
}

function EyeIcon({ closed = false }) {
  return (
    <svg className="inline-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {closed ? (
        <>
          <path d="M3 3l18 18" />
          <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
          <path d="M9.9 5.2A8.5 8.5 0 0 1 12 5c5 0 8.5 4.5 9.5 7a12.3 12.3 0 0 1-2.6 3.8" />
          <path d="M6.4 6.4A12.7 12.7 0 0 0 2.5 12c1 2.5 4.5 7 9.5 7 1.5 0 2.8-.4 4-1" />
        </>
      ) : (
        <>
          <path d="M2.5 12c1-2.5 4.5-7 9.5-7s8.5 4.5 9.5 7c-1 2.5-4.5 7-9.5 7s-8.5-4.5-9.5-7Z" />
          <circle cx="12" cy="12" r="2.5" />
        </>
      )}
    </svg>
  );
}

function SchoolDomCbtDesktop({ exams = [], results = [], downloads = {}, school = {}, session = null }) {
  const brand = resolveSchoolBrand(school, session?.school);
  const schoolCode = brand.code || school?.school_code || school?.schema_name || session?.user?.school_code || session?.user?.tenant?.schema_name || "";
  const adminAppDownloadUrl = `${API_BASE_URL}/api/app/admin-desktop/download/${schoolCode ? `?school_code=${encodeURIComponent(schoolCode)}` : ""}`;
  const [downloadNotice, setDownloadNotice] = useState(false);
  const [downloadState, setDownloadState] = useState({ error: "", message: "" });
  const publishedExams = exams.filter((exam) => Boolean(exam.is_published));
  const openExams = publishedExams.filter((exam) => {
    const now = Date.now();
    const starts = new Date(exam.start_date || exam.startDate || 0).getTime();
    const ends = new Date(exam.end_date || exam.endDate || 0).getTime();
    return starts <= now && (!ends || now <= ends);
  });
  const recentExams = [...publishedExams]
    .sort((a, b) => new Date(b.start_date || b.created_at || 0) - new Date(a.start_date || a.created_at || 0))
    .slice(0, 6);

  const downloadAdminSeed = () => {
    if (!schoolCode) return;
    const seed = {
      serverUrl: API_BASE_URL,
      schoolCode,
      school_code: schoolCode,
      school: {
        name: school?.name || session?.school?.name || "",
        school_code: schoolCode,
        logo: school?.logo || school?.logo_url || "",
        email: school?.email || "",
        phone: school?.phone || "",
        address: school?.address || "",
      },
    };
    const blob = new Blob([JSON.stringify(seed, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "SchoolDomAdmin.schooldom.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const downloadAdminApp = () => {
    setDownloadNotice(true);
    setDownloadState({ error: "", message: "Download started. Check your browser downloads." });
    downloadAdminSeed();
    window.location.assign(adminAppDownloadUrl);
  };

  const handleAdminAppDownload = (event) => {
    event.preventDefault();
    downloadAdminApp();
  };

  return (
    <section className="cbt-desktop-app">
      <header className="cbt-desktop-hero">
        <div>
          <p className="quiz-kicker">Desktop CBT deployment</p>
          <h2>{brand.name} Admin App</h2>
          <p>Install the admin app for school-branded CBT setup, then install the student exam app from inside it.</p>
        </div>
      </header>

      <div className="metric-grid cbt-metric-grid">
        <MetricCard label="Exams Ready" value={publishedExams.length} trend="Available to eligible students" icon="exam" tone="violet" />
        <MetricCard label="Open Now" value={openExams.length} trend="Within scheduled exam time" icon="overview" tone="emerald" />
      </div>

      <div className="cbt-admin-layout">
        <article className="app-panel cbt-server-panel">
          <div className="panel-head">
            <h3>{brand.name} Admin installer</h3>
            <small>Install this Windows admin app first, then install the student CBT app from inside it.</small>
          </div>
          <div className="cbt-server-card">
            <div>
              <span>Admin application</span>
              <strong>{brand.name} Admin</strong>
              <small>Download the admin app here. Inside the app, use Install CBT App for student computers.</small>
            </div>
            <CbtStatusPill tone="success">No JWT token needed</CbtStatusPill>
          </div>
          <div className="cbt-action-row">
            <a className="cbt-download-button" href={adminAppDownloadUrl} onClick={handleAdminAppDownload}>
              Download Admin App
            </a>
          </div>
          <div className="cbt-security-grid">
            {[
              ["School Branding", "The admin app shows the school name, details, and uploaded school logo."],
              ["CBT Installer", "Admins install the student CBT app directly from inside the admin app."],
              ["No Token Copying", "The admin app reads public school details from the configured school server."],
              ["Exam Writing", "Students still use the separate CBT app for exams only."],
            ].map(([title, detail]) => (
              <div key={title}>
                <strong>{title}</strong>
                <span>{detail}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="app-panel cbt-session-panel">
          <div className="panel-head">
            <h3>Published CBT exams</h3>
            <small>Only real exams from the database are shown here.</small>
          </div>
          <div className="cbt-session-list">
            {recentExams.length ? recentExams.map((exam) => (
              <div key={exam.id || exam.exam_id} className="cbt-real-session">
                <span>
                  <strong>{exam.title || exam.name || `Exam ${exam.id || exam.exam_id}`}</strong>
                  <small>{exam.class_name || exam.class || "All classes"} - {exam.duration_minutes || exam.duration || "-"} mins</small>
                </span>
                <CbtStatusPill tone={openExams.some((item) => String(item.id || item.exam_id) === String(exam.id || exam.exam_id)) ? "success" : "info"}>
                  {openExams.some((item) => String(item.id || item.exam_id) === String(exam.id || exam.exam_id)) ? "Open" : "Scheduled"}
                </CbtStatusPill>
              </div>
            )) : (
              <p className="panel-empty">Publish a CBT exam to make it available in the student desktop app.</p>
            )}
          </div>
        </article>
      </div>
      {downloadNotice ? (
        <div className="cbt-download-modal" role="dialog" aria-modal="true" aria-labelledby="cbt-download-title">
          <div className="cbt-download-card">
            <div className="cbt-download-check" aria-hidden="true">
              <span />
            </div>
            <p className="cbt-info-kicker">Download requested</p>
            <h3 id="cbt-download-title">{brand.name} Admin App is starting</h3>
            <p>{downloadState.error || downloadState.message || "The download should begin automatically."}</p>
            <div className="cbt-download-actions">
              <button type="button" className="cbt-download-button" onClick={downloadAdminApp}>
                Download Again
              </button>
              <button type="button" onClick={() => setDownloadNotice(false)}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function AdminDashboardScreen({ user, data, loading, error, onRetry, onBroadcastMessage }) {
  const metrics = data?.metrics || {};
  const dashboardSchool = resolveSchoolBrand(data?.school, user?.school, user);
  const displayRole = userRoleLabel(user);
  const announcements = data?.announcements || [];
  const recentStudents = data?.recent_students || [];
  const [recentStudentsOpen, setRecentStudentsOpen] = useState(false);
  const [recentStudentWindow, setRecentStudentWindow] = useState("7d");
  const [broadcastForm, setBroadcastForm] = useState({ subject: "", body: "" });
  const [broadcastBusy, setBroadcastBusy] = useState(false);
  const [broadcastFeedback, setBroadcastFeedback] = useState("");
  const [broadcastError, setBroadcastError] = useState("");
  const recentStudentFilters = [
    ["24h", "Last 24 hrs"],
    ["7d", "Last 7 days"],
    ["30d", "Last 30 days"],
  ];
  const filterRecentStudents = (windowKey) => {
    const now = Date.now();
    const days = windowKey === "24h" ? 1 : windowKey === "30d" ? 30 : 7;
    const threshold = now - days * 24 * 60 * 60 * 1000;
    return recentStudents.filter((student) => {
      const createdTime = new Date(student.created_at || student.createdAt || 0).getTime();
      return !Number.isNaN(createdTime) && createdTime >= threshold;
    });
  };
  const selectedRecentStudents = filterRecentStudents(recentStudentWindow);
  const recentStudentsCount = recentStudents.length || metrics.new_students_7d || 0;

  const handleBroadcastSubmit = async (event) => {
    event.preventDefault();
    const body = broadcastForm.body.trim();
    if (!body) {
      setBroadcastError("Write a broadcast message first.");
      return;
    }
    setBroadcastBusy(true);
    setBroadcastFeedback("");
    setBroadcastError("");
    try {
      const result = await onBroadcastMessage?.({
        target: "school_broadcast",
        subject: broadcastForm.subject.trim(),
        body,
      });
      setBroadcastFeedback(result?.message || "Broadcast sent to staff, students, and teachers.");
      setBroadcastForm({ subject: "", body: "" });
    } catch (actionError) {
      setBroadcastError(actionError.message || "Could not send broadcast.");
    } finally {
      setBroadcastBusy(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Welcome back to {dashboardSchool.name}</h2>
        <p>{displayRole} - {userDisplayName(user)}. Live summary from your school data endpoints.</p>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Active Students"
              value={metrics.active_students ?? 0}
              trend={`${metrics.new_students_7d ?? 0} new in last 7 days`}
            />
            <MetricCard
              label="Total Classes"
              value={metrics.classes ?? 0}
              trend={`${metrics.upcoming_exams ?? 0} upcoming exams`}
            />
            <MetricCard
              label="Pending Submissions"
              value={metrics.pending_submissions ?? 0}
              trend="Exam attempts awaiting submission"
            />
            <MetricCard
              label="Unread Notices"
              value={metrics.unread_notifications ?? 0}
              trend="Notifications still unread"
            />
          </div>

          <div className="panel-grid">
            <button
              type="button"
              className="metric-card tone-emerald dashboard-click-card"
              onClick={() => setRecentStudentsOpen(true)}
            >
              <div className="metric-card-head">
                <span className="metric-icon">
                  <DashboardIcon name="students" className="inline-icon" />
                </span>
                <p className="metric-label">Recently Registered Students</p>
              </div>
              <p className="metric-value">{recentStudentsCount}</p>
              <p className="metric-trend">Click to filter by registration date</p>
            </button>

            <article className="app-panel">
              <h3>Broadcast Message</h3>
              <form className="panel-form" onSubmit={handleBroadcastSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field">
                    Subject
                    <input
                      value={broadcastForm.subject}
                      onChange={(event) => setBroadcastForm((prev) => ({ ...prev, subject: event.target.value }))}
                      placeholder="Optional headline"
                    />
                  </label>
                  <label className="panel-field full">
                    Message
                    <textarea
                      value={broadcastForm.body}
                      onChange={(event) => setBroadcastForm((prev) => ({ ...prev, body: event.target.value }))}
                      placeholder="This will appear in the notification popup for staff, students, and teachers."
                      required
                    />
                  </label>
                </div>
                {broadcastError ? <p className="form-feedback error">{broadcastError}</p> : null}
                {broadcastFeedback ? <p className="form-feedback success">{broadcastFeedback}</p> : null}
                <div className="panel-form-actions">
                  <button type="submit" disabled={broadcastBusy || !onBroadcastMessage}>
                    {broadcastBusy ? "Sending..." : "Send Broadcast"}
                  </button>
                </div>
              </form>
            </article>

            <article className="app-panel admin-announcements-panel">
              <h3>Recent Announcements</h3>
              {announcements.length > 0 ? (
                <ul className="panel-list">
                  {announcements.map((item) => (
                    <li key={item.id}>
                      {item.title} ({formatDate(item.published_at)})
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="panel-empty">No announcements yet.</p>
              )}
            </article>
          </div>

          {recentStudentsOpen ? (
            <div className="notification-drawer-overlay" role="presentation" onClick={() => setRecentStudentsOpen(false)}>
              <aside className="notification-drawer" role="dialog" aria-modal="true" aria-label="Recently registered students" onClick={(event) => event.stopPropagation()}>
                <section className="screen-grid notification-popup-center">
                  <header className="notification-center-hero">
                    <div>
                      <p className="topbar-kicker">Student registrations</p>
                      <h2>Recently Registered Students</h2>
                    </div>
                    <button type="button" className="notification-close-button" onClick={() => setRecentStudentsOpen(false)}>
                      Close
                    </button>
                  </header>
                  <article className="app-panel">
                    <div className="segmented-control">
                      {recentStudentFilters.map(([key, label]) => (
                        <button key={key} type="button" className={recentStudentWindow === key ? "active" : ""} onClick={() => setRecentStudentWindow(key)}>
                          {label}
                        </button>
                      ))}
                    </div>
                    <p className="field-note">{selectedRecentStudents.length} student(s) found.</p>
                    {selectedRecentStudents.length > 0 ? (
                      <div className="person-list">
                        {selectedRecentStudents.map((student) => (
                          <div key={student.id} className="person-row">
                            <div className="person-details">
                              <p>{student.name}</p>
                              <span>
                                {student.student_id} - {student.class_name}
                              </span>
                            </div>
                            <small>{formatDate(student.created_at)}</small>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="panel-empty">No student registrations found for this period.</p>
                    )}
                  </article>
                </section>
              </aside>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function HeatMetric({ label, value, suffix = "%", status = "watch", detail = "" }) {
  return (
    <article className={`heat-metric-card tone-${heatTone(status)}`}>
      <span>{label}</span>
      <strong>{value}{suffix}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  );
}

function HeatBar({ label, value, status, meta = "", right = "" }) {
  const percent = clampPercent(value);
  return (
    <div className={`heat-bar-row tone-${heatTone(status)}`}>
      <div className="heat-bar-label">
        <strong>{label}</strong>
        {meta ? <small>{meta}</small> : null}
      </div>
      <div className="heat-bar-track" aria-hidden="true">
        <i style={{ width: `${percent}%` }} />
      </div>
      <b>{right || `${percent}%`}</b>
    </div>
  );
}

function MiniTrend({ rows = [] }) {
  const maxAmount = Math.max(...rows.map((item) => Number(item.amount || 0)), 1);
  return (
    <div className="heat-mini-trend" aria-label="Fee payment transaction trend">
      {rows.slice(-18).map((item, index) => {
        const height = Math.max(8, Math.round((Number(item.amount || 0) / maxAmount) * 100));
        return (
          <span
            key={`${item.date}-${index}`}
            className={String(item.status || "").toLowerCase().includes("success") ? "paid" : "pending"}
            style={{ height: `${height}%` }}
            title={`${item.date}: ${formatAnalyticsAmount(item.amount)}`}
          />
        );
      })}
    </div>
  );
}

function AdminPerformanceHeatmapScreen({ data = {}, loading, error, onRetry }) {
  if (loading || error) {
    return <ScreenState loading={loading} error={error} onRetry={onRetry} />;
  }

  const summary = data.summary || {};
  const weakSubjects = data.weak_subjects || [];
  const lowClasses = data.low_classes || [];
  const attendanceRows = data.attendance_decline || [];
  const feeTrends = data.fee_trends || {};
  const examStats = data.examination_statistics || {};
  const departments = data.departmental_performance || [];
  const generatedAt = data.generated_at ? formatDate(data.generated_at) : "Live";

  return (
    <section className="performance-heatmap-screen">
      <header className="performance-heatmap-hero">
        <div>
          <p className="topbar-kicker">Real-time analytics</p>
          <h1>School Data Analytics</h1>
          <p>Color-coded signals for academics, attendance, fees, examinations, and departments.</p>
        </div>
        <div className={`heat-risk-orb tone-${heatTone(summary.risk_status)}`}>
          <span>Risk</span>
          <strong>{Number(summary.risk_score || 0).toFixed(1)}%</strong>
          <small>Updated {generatedAt}</small>
        </div>
      </header>

      <div className="heat-metric-grid">
        <HeatMetric label="Weak Subjects" value={summary.weak_subjects ?? 0} suffix="" status={summary.weak_subjects > 0 ? "weak" : "strong"} detail={`${summary.score_entries ?? 0} score entries`} />
        <HeatMetric label="Low Classes" value={summary.low_classes ?? 0} suffix="" status={summary.low_classes > 0 ? "weak" : "strong"} detail={`${summary.students ?? 0} students tracked`} />
        <HeatMetric label="Attendance" value={Number(summary.attendance_current || 0).toFixed(1)} status={summary.attendance_current >= 70 ? "strong" : summary.attendance_current >= 50 ? "watch" : "weak"} detail="Current 14-day rate" />
        <HeatMetric label="Fee Collection" value={Number(summary.fee_collection_rate || 0).toFixed(1)} status={summary.fee_collection_rate >= 70 ? "strong" : summary.fee_collection_rate >= 50 ? "watch" : "weak"} detail="All active fee bills" />
        <HeatMetric label="Exam Average" value={Number(summary.exam_average || 0).toFixed(1)} status={summary.exam_average >= 70 ? "strong" : summary.exam_average >= 50 ? "watch" : "weak"} detail={`${summary.exam_completion ?? 0}% completion`} />
      </div>

      <div className="heatmap-layout">
        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Weak Subject Signals</h3>
            <small>Lowest averages across published result entries.</small>
          </div>
          <div className="heat-bar-list">
            {weakSubjects.length ? weakSubjects.map((item) => (
              <HeatBar
                key={`${item.name}-${item.code}`}
                label={item.name}
                value={item.average}
                status={item.status}
                meta={`${item.entries} entries • ${item.class_count} classes`}
              />
            )) : <p className="panel-empty">No subject scores are available yet.</p>}
          </div>
        </article>

        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Low-Performing Classes</h3>
            <small>Classes sorted by lowest academic average.</small>
          </div>
          <div className="heat-tile-grid">
            {lowClasses.length ? lowClasses.map((item) => (
              <div key={item.name} className={`heat-class-tile tone-${heatTone(item.status)}`}>
                <strong>{item.name}</strong>
                <span>{item.average}%</span>
                <small>{item.subject_count} subjects • {item.entries} entries</small>
              </div>
            )) : <p className="panel-empty">No class performance data yet.</p>}
          </div>
        </article>

        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Attendance Decline</h3>
            <small>Current 14 days compared with the previous 14 days.</small>
          </div>
          <div className="heat-bar-list">
            {attendanceRows.length ? attendanceRows.map((item) => (
              <HeatBar
                key={item.class_name}
                label={item.class_name}
                value={item.current_rate}
                status={item.status}
                meta={`${item.decline > 0 ? "-" : "+"}${Math.abs(Number(item.decline || 0)).toFixed(1)} pts vs previous`}
              />
            )) : <p className="panel-empty">No recent attendance records yet.</p>}
          </div>
        </article>

        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Fee Payment Trends</h3>
            <small>{formatAnalyticsAmount(feeTrends.paid)} collected of {formatAnalyticsAmount(feeTrends.expected)}.</small>
          </div>
          <MiniTrend rows={feeTrends.monthly_transactions || []} />
          <div className="heat-bar-list compact">
            {(feeTrends.class_trends || []).length ? feeTrends.class_trends.map((item) => (
              <HeatBar
                key={item.class_name}
                label={item.class_name}
                value={item.collection_rate}
                status={item.status}
                meta={`${formatAnalyticsAmount(item.paid)} paid`}
              />
            )) : <p className="panel-empty">No fee bills or payment transactions yet.</p>}
          </div>
        </article>

        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Examination Statistics</h3>
            <small>{examStats.attempts ?? 0} attempts this month.</small>
          </div>
          <div className="exam-stat-strip">
            <HeatMetric label="Completion" value={Number(examStats.completion_rate || 0).toFixed(1)} status={examStats.completion_rate >= 70 ? "strong" : "watch"} />
            <HeatMetric label="Average" value={Number(examStats.average || 0).toFixed(1)} status={examStats.average >= 70 ? "strong" : examStats.average >= 50 ? "watch" : "weak"} />
            <HeatMetric label="Auto-submit" value={Number(examStats.auto_submit_rate || 0).toFixed(1)} status={examStats.auto_submit_rate > 20 ? "weak" : examStats.auto_submit_rate > 5 ? "watch" : "strong"} />
          </div>
          <div className="heat-bar-list compact">
            {(examStats.subjects || []).map((item) => (
              <HeatBar key={item.name} label={item.name} value={item.average} status={item.status} meta={`${item.attempts} attempts`} />
            ))}
          </div>
        </article>

        <article className="app-panel heat-panel">
          <div className="panel-head">
            <h3>Departmental Performance</h3>
            <small>Subject clusters grouped for leadership review.</small>
          </div>
          <div className="department-heat-grid">
            {departments.length ? departments.map((item) => (
              <div key={item.name} className={`department-heat-card tone-${heatTone(item.status)}`}>
                <span>{item.name}</span>
                <strong>{item.average}%</strong>
                <small>{item.subject_count} subjects • {item.entries} scores</small>
              </div>
            )) : <p className="panel-empty">No departmental performance data yet.</p>}
          </div>
        </article>
      </div>
    </section>
  );
}

function AdminFinanceScreen({
  data,
  school,
  loading,
  error,
  onRetry,
  onWithdraw,
  onClassFeeSave,
  onClassFeeDelete,
  onStudentFeeSave,
  onPaymentAccountSave,
  onPaystackSubaccountSetup,
  onPurchaseCredits,
  onVerifyCredits,
  onAssignCredits,
  onCreditSettings,
  onRunAutoCredits,
  onBankPaymentsIngest,
  onBankPaymentRecover,
  session,
}) {
  const finance = data?.finance_overview || data || {};
  const schoolBrand = resolveSchoolBrand(finance?.school, data?.school, school, finance?.tenant, data?.tenant);
  const groupLabels = academicGroupLabels(schoolBrand);
  const adminWallet = finance?.admin_wallet || {};
  const classFees = finance?.class_fee_rows || [];
  const studentFeeRows = finance?.student_fee_rows || [];
  const classOptions = finance?.class_options || [];
  const paymentRows = finance?.student_payment_rows || [];
  const creditPool = finance?.activation_credit_pool || {};
  const creditSummary = finance?.activation_credit_summary || {};
  const creditRows = finance?.activation_credit_rows || [];
  const creditPurchaseHistory = finance?.activation_credit_purchase_history || [];
  const bankPaymentRows = finance?.bank_payment_rows || [];
  const transactionHistory = finance?.transaction_history || [];
  const financeLedgerRows = finance?.finance_ledger_logs || [];
  const [withdrawForm, setWithdrawForm] = useState({
    amount: "",
    account_number: "",
    bank_name: "",
    account_name: "",
  });
  const [paymentAccountForm, setPaymentAccountForm] = useState({
    bank_account_name: "",
    bank_account_number: "",
    bank_name: "",
  });
  const [classFeeForm, setClassFeeForm] = useState({
    school_class: "",
    title: "",
    amount: "",
    due_date: "",
  });
  const [editingClassFeeId, setEditingClassFeeId] = useState("");
  const [studentFeeForm, setStudentFeeForm] = useState({
    title: "",
    amount: "",
    due_date: "",
    status: "pending",
    auto_deduct: true,
  });
  const [editingStudentFeeId, setEditingStudentFeeId] = useState("");
  const [bankPaymentForm, setBankPaymentForm] = useState({ amount: "", narration: "", bank_reference: "" });
  const [recoveryForm, setRecoveryForm] = useState({});
  const [creditPurchaseForm, setCreditPurchaseForm] = useState({ credits: "" });
  const [creditPurchaseReference, setCreditPurchaseReference] = useState("");
  const [creditPurchaseUrl, setCreditPurchaseUrl] = useState("");
  const [creditAssignForm, setCreditAssignForm] = useState({ scope: "student", months: "1", student_id: "" });
  const [creditStudentSearch, setCreditStudentSearch] = useState("");
  const [creditSettingsForm, setCreditSettingsForm] = useState({
    enabled: false,
    scope: "all",
  });
  const [mobileFinanceSection, setMobileFinanceSection] = useState("student-payments");
  const [expandedFinanceTables, setExpandedFinanceTables] = useState({});
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [vaAccounts, setVaAccounts] = useState([]);
  const [vaParentsWithoutAccount, setVaParentsWithoutAccount] = useState([]);
  const [vaListLoading, setVaListLoading] = useState(false);
  const [vaListError, setVaListError] = useState("");
  const [vaSearch, setVaSearch] = useState("");
  const [vaBusyParentId, setVaBusyParentId] = useState("");
  const [vaActionMessage, setVaActionMessage] = useState("");
  const [vaActionError, setVaActionError] = useState("");
  const [subaccountForm, setSubaccountForm] = useState({ account_number: "", bank_code: "", account_name: "" });
  const [subaccountBankQuery, setSubaccountBankQuery] = useState("");
  const [subaccountBanks, setSubaccountBanks] = useState([]);
  const [subaccountBanksLoading, setSubaccountBanksLoading] = useState(false);
  const [subaccountBusy, setSubaccountBusy] = useState(false);
  const [subaccountMessage, setSubaccountMessage] = useState("");
  const [subaccountError, setSubaccountError] = useState("");
  const [resolveLoading, setResolveLoading] = useState(false);
  const [resolveError, setResolveError] = useState("");
  const tokenPurchaseRef = useRef(null);

  const loadVirtualAccountsList = useCallback(async () => {
    if (!session) return;
    setVaListLoading(true);
    setVaListError("");
    try {
      const result = await requestJson(session, "GET", "/api/finance/admin/virtual-accounts/");
      setVaAccounts(result?.virtual_accounts || []);
      setVaParentsWithoutAccount(result?.parents_without_account || []);
    } catch (err) {
      setVaListError(err.message || "Could not load virtual accounts.");
    } finally {
      setVaListLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadVirtualAccountsList();
  }, [loadVirtualAccountsList]);

  const handleProvisionVirtualAccount = async (parentId) => {
    if (!parentId) return;
    setVaBusyParentId(parentId);
    setVaActionMessage("");
    setVaActionError("");
    try {
      const result = await requestJson(session, "POST", `/api/finance/admin/virtual-accounts/${parentId}/provision/`);
      setVaActionMessage(result?.message || "Virtual account provisioned.");
      await loadVirtualAccountsList();
    } catch (err) {
      setVaActionError(err.message || "Could not provision virtual account.");
    } finally {
      setVaBusyParentId("");
    }
  };

  const normalizedVaSearch = vaSearch.trim().toLowerCase();
  const filteredVaAccounts = vaAccounts.filter((row) => {
    if (!normalizedVaSearch) return true;
    return [row.parent_name, row.parent_email, row.account_number, row.bank_name]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedVaSearch);
  });
  const filteredVaParentsWithoutAccount = vaParentsWithoutAccount.filter((row) => {
    if (!normalizedVaSearch) return true;
    return [row.parent_name, row.parent_email]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedVaSearch);
  });
  const financeCurrency = "NGN";
  const formatFinanceAmount = (value) =>
    `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  const expectedAmount = Number(finance?.expected_fee_amount || 0);
  const receivedAmount = Number(finance?.amount_received || 0);
  const outstandingAmount = Number(finance?.outstanding_balance || 0);
  const studentCreditBalance = Number(finance?.total_student_credit_balance || 0);
  const receivedPercent = expectedAmount > 0 ? Math.min(100, Math.round((receivedAmount / expectedAmount) * 100)) : 0;
  const outstandingPercent = expectedAmount > 0 ? Math.min(100, Math.round((outstandingAmount / expectedAmount) * 100)) : 0;
  const requestedCreditCount = Number(creditPurchaseForm.credits || 0);
  const tokenUnitPrice = Number(creditSummary.price_per_credit ?? creditPool.price_per_credit ?? 200);
  const tokenDurationMonths = Number(creditSummary.duration_months_per_token ?? (schoolBrand.school_type === "non_k12" ? 1 : 3));
  const tokenDurationDays = Number(creditSummary.duration_days_per_token ?? (schoolBrand.school_type === "non_k12" ? 0 : 15));
  const tokenDurationText = `1 token = ${tokenDurationMonths} month${tokenDurationMonths === 1 ? "" : "s"}${tokenDurationDays ? ` ${tokenDurationDays} days` : ""}`;
  const bonusCreditCount = Math.floor(requestedCreditCount / 100) * 10;
  const totalCreditCount = requestedCreditCount + bonusCreditCount;
  const selectedStudentFee = studentFeeRows.find((fee) => fee.id === editingStudentFeeId);
  const visibleClassFees = expandedFinanceTables.classFees ? classFees : classFees.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const visibleStudentFeeRows = expandedFinanceTables.studentFees ? studentFeeRows : studentFeeRows.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const visiblePaymentRows = expandedFinanceTables.studentPayments ? paymentRows : paymentRows.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const inactiveCreditRows = creditRows.filter((row) => !row.has_login_credit);
  const normalizedCreditStudentSearch = creditStudentSearch.trim().toLowerCase();
  const filteredInactiveCreditRows = inactiveCreditRows.filter((row) => {
    if (!normalizedCreditStudentSearch) {
      return true;
    }
    const searchable = [
      row.student_name,
      row.student_email,
      row.student_identifier,
      row.student_id,
      row.class_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return searchable.includes(normalizedCreditStudentSearch);
  });
  const visibleCreditRows = expandedFinanceTables.activationAlerts ? creditRows : creditRows.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const visibleBankPaymentRows = expandedFinanceTables.bankPaymentHistory
    ? bankPaymentRows
    : bankPaymentRows.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const visibleCreditPurchaseHistory = expandedFinanceTables.creditHistory
    ? creditPurchaseHistory
    : creditPurchaseHistory.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const visibleFinanceLedgerRows = expandedFinanceTables.financeLedger
    ? financeLedgerRows
    : financeLedgerRows.slice(0, FINANCE_TABLE_PREVIEW_COUNT);
  const toggleFinanceTable = (tableKey) => {
    setExpandedFinanceTables((current) => ({
      ...current,
      [tableKey]: !current[tableKey],
    }));
  };
  const renderFinanceMoreButton = (tableKey, rowCount) => {
    if (rowCount <= FINANCE_TABLE_PREVIEW_COUNT) {
      return null;
    }
    const isExpanded = Boolean(expandedFinanceTables[tableKey]);
    return (
      <div className="finance-table-actions">
        <button type="button" className="pill-button ghost" onClick={() => toggleFinanceTable(tableKey)}>
          {isExpanded ? "Show less" : `More (${rowCount - FINANCE_TABLE_PREVIEW_COUNT})`}
        </button>
      </div>
    );
  };
  const scrollToTokenPurchase = () => {
    tokenPurchaseRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    setCreditSettingsForm({
      enabled: Boolean(creditPool.auto_assign_enabled),
      scope: creditPool.auto_assign_scope || "all",
    });
  }, [creditPool.auto_assign_enabled, creditPool.auto_assign_scope]);

  useEffect(() => {
    setPaymentAccountForm({
      bank_account_name: adminWallet.bank_account_name || "",
      bank_account_number: adminWallet.bank_account_number || "",
      bank_name: adminWallet.bank_name || adminWallet.bank_code || "",
    });
    setWithdrawForm((current) => ({
      ...current,
      account_name: current.account_name || adminWallet.bank_account_name || "",
      account_number: current.account_number || adminWallet.bank_account_number || "",
      bank_name: current.bank_name || adminWallet.bank_name || adminWallet.bank_code || "",
    }));
  }, [adminWallet.bank_account_name, adminWallet.bank_account_number, adminWallet.bank_code, adminWallet.bank_name]);

  const handlePaymentAccountSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      await onPaymentAccountSave(paymentAccountForm);
      setFeedback("School fee receiving account saved. Students will see it on their fees page.");
    } catch (err) {
      setFormError(err.message || "Unable to save receiving account.");
    }
  };

  useEffect(() => {
    setSubaccountForm((current) => ({
      account_number: current.account_number || adminWallet.bank_account_number || "",
      bank_code: current.bank_code || adminWallet.bank_code || "",
      account_name: current.account_name || adminWallet.bank_account_name || "",
    }));
  }, [adminWallet.bank_account_number, adminWallet.bank_code, adminWallet.bank_account_name]);

  useEffect(() => {
    if (!session) return;
    setSubaccountBanksLoading(true);
    requestJson(session, "GET", "/api/finance/admin/paystack/banks/")
      .then((result) => setSubaccountBanks(result?.banks || []))
      .catch(() => {})
      .finally(() => setSubaccountBanksLoading(false));
  }, [session]);

  useEffect(() => {
    if (!subaccountBankQuery && subaccountForm.bank_code && subaccountBanks.length) {
      const matched = subaccountBanks.find((bank) => bank.code === subaccountForm.bank_code);
      if (matched) setSubaccountBankQuery(matched.name);
    }
  }, [subaccountBanks, subaccountForm.bank_code, subaccountBankQuery]);

  const handleSubaccountBankQueryChange = (value) => {
    setSubaccountBankQuery(value);
    const matched = subaccountBanks.find((bank) => bank.name.toLowerCase() === value.trim().toLowerCase());
    setSubaccountForm((current) => ({ ...current, bank_code: matched ? matched.code : "", account_name: "" }));
    setResolveError("");
  };

  useEffect(() => {
    const acct = subaccountForm.account_number.replace(/\D/g, "");
    const code = subaccountForm.bank_code;
    if (acct.length !== 10 || !code) return;
    let cancelled = false;
    setResolveLoading(true);
    setResolveError("");
    requestJson(session, "GET", `/api/finance/admin/paystack/resolve-account/?account_number=${acct}&bank_code=${code}`)
      .then((result) => {
        if (cancelled) return;
        if (result?.success && result.account_name) {
          setSubaccountForm((current) => ({ ...current, account_name: result.account_name }));
        } else {
          setResolveError(result?.message || "Could not resolve account.");
        }
      })
      .catch((err) => {
        if (!cancelled) setResolveError(err.message || "Could not resolve account.");
      })
      .finally(() => { if (!cancelled) setResolveLoading(false); });
    return () => { cancelled = true; };
  }, [subaccountForm.account_number, subaccountForm.bank_code, session]);

  const handleSubaccountSetupSubmit = async (event) => {
    event.preventDefault();
    setSubaccountMessage("");
    setSubaccountError("");
    if (!subaccountForm.bank_code) {
      setSubaccountError("Select a valid bank from the list.");
      return;
    }
    setSubaccountBusy(true);
    try {
      const result = await onPaystackSubaccountSetup(subaccountForm);
      setSubaccountMessage(result?.message || "Subaccount created.");
    } catch (err) {
      setSubaccountError(err.message || "Unable to create subaccount.");
    } finally {
      setSubaccountBusy(false);
    }
  };

  const handleWithdrawSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      await onWithdraw({
        ...withdrawForm,
        amount: Number(withdrawForm.amount),
      });
      setFeedback("Withdrawal initiated.");
      setWithdrawForm({ amount: "", account_number: "", bank_name: "", account_name: "" });
    } catch (err) {
      setFormError(err.message || "Unable to withdraw.");
    }
  };

  const handleClassFeeSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      const result = await onClassFeeSave({
        id: editingClassFeeId,
        ...classFeeForm,
        amount: Number(classFeeForm.amount),
      });
      setFeedback(result?.message || (editingClassFeeId ? "Class fee updated." : "Class fee set and synced."));
      setEditingClassFeeId("");
      setClassFeeForm({ school_class: "", title: "", amount: "", due_date: "" });
    } catch (err) {
      setFormError(err.message || "Unable to save class fee.");
    }
  };

  const startEditClassFee = (fee) => {
    setEditingClassFeeId(fee.id);
    setClassFeeForm({
      school_class: fee.school_class || "",
      title: fee.title || "",
      amount: fee.amount || "",
      due_date: fee.due_date || "",
    });
  };

  const handleDeactivateClassFee = async (feeId) => {
    setFeedback("");
    setFormError("");
    try {
      await onClassFeeDelete(feeId);
      setFeedback("Class fee deactivated.");
    } catch (err) {
      setFormError(err.message || "Unable to deactivate class fee.");
    }
  };

  const startEditStudentFee = (fee) => {
    setFeedback("");
    setFormError("");
    setEditingStudentFeeId(fee.id);
    setStudentFeeForm({
      title: fee.title || "",
      amount: fee.amount || "",
      due_date: fee.due_date || "",
      status: fee.status || "pending",
      auto_deduct: fee.auto_deduct !== false,
    });
  };

  const resetStudentFeeForm = () => {
    setEditingStudentFeeId("");
    setStudentFeeForm({ title: "", amount: "", due_date: "", status: "pending", auto_deduct: true });
  };

  const handleStudentFeeSubmit = async (event) => {
    event.preventDefault();
    if (!editingStudentFeeId) return;
    setFeedback("");
    setFormError("");
    try {
      await onStudentFeeSave({
        id: editingStudentFeeId,
        ...studentFeeForm,
        amount: Number(studentFeeForm.amount),
      });
      setFeedback("Student fee updated.");
      resetStudentFeeForm();
    } catch (err) {
      setFormError(err.message || "Unable to update student fee.");
    }
  };

  const handleCreditPurchaseSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      const result = await onPurchaseCredits({ credits: Number(creditPurchaseForm.credits) });
      setCreditPurchaseReference(result?.reference || "");
      const checkoutUrl = result?.authorization_url || result?.link || "";
      setCreditPurchaseUrl(checkoutUrl);
      const providerLabel = result?.provider ? result.provider.charAt(0).toUpperCase() + result.provider.slice(1) : "Payment";
      setFeedback(
        `${providerLabel} checkout initialized. ${Number(result?.total_credits || totalCreditCount).toLocaleString()} tokens will be added after payment.`
      );
      if (checkoutUrl) {
        window.open(checkoutUrl, "_blank", "noopener");
      }
    } catch (err) {
      setFormError(err.message || "Unable to start token payment.");
    }
  };

  useEffect(() => {
    if (!creditPurchaseReference) return undefined;
    let cancelled = false;
    const confirmCreditPurchase = async () => {
      try {
        await onVerifyCredits({ reference: creditPurchaseReference });
        if (cancelled) return;
        setFeedback("Activation token payment confirmed and tokens added.");
        setFormError("");
        setCreditPurchaseReference("");
        setCreditPurchaseUrl("");
        setCreditPurchaseForm({ credits: "" });
      } catch {
        if (!cancelled) {
          setFormError("");
        }
      }
    };
    const intervalId = window.setInterval(confirmCreditPurchase, 5000);
    confirmCreditPurchase();
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [creditPurchaseReference, onVerifyCredits]);

  const handleCreditAssignSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      if (creditAssignForm.scope === "student" && !creditAssignForm.student_id) {
        setFormError("Select an inactive student before assigning tokens.");
        return;
      }
      const result = await onAssignCredits({
        scope: creditAssignForm.scope,
        months: Number(creditAssignForm.months),
        student_id: creditAssignForm.scope === "student" ? creditAssignForm.student_id : undefined,
      });
      setFeedback(`${result.assigned || 0} student accounts activated.`);
    } catch (err) {
      setFormError(err.message || "Unable to assign activation tokens.");
    }
  };

  const handleCreditSettingsSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      await onCreditSettings(creditSettingsForm);
      setFeedback("Auto-assignment settings saved.");
    } catch (err) {
      setFormError(err.message || "Unable to save token settings.");
    }
  };

  const handleRunAutoCredits = async () => {
    setFeedback("");
    setFormError("");
    try {
      const result = await onRunAutoCredits();
      setFeedback(`${result.assigned || 0} student accounts activated by auto-assignment.`);
    } catch (err) {
      setFormError(err.message || "Unable to run auto-assignment.");
    }
  };

  const handleBankPaymentSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    try {
      await onBankPaymentsIngest({ ...bankPaymentForm, currency: financeCurrency });
      setFeedback("Bank transaction checked and matched.");
      setBankPaymentForm({ amount: "", narration: "", bank_reference: "" });
    } catch (err) {
      setFormError(err.message || "Unable to process bank transaction.");
    }
  };

  const handleRecoverPayment = async (paymentId) => {
    setFeedback("");
    setFormError("");
    try {
      await onBankPaymentRecover(paymentId, recoveryForm[paymentId] || {});
      setFeedback("Payment recovered and applied.");
      setRecoveryForm((current) => ({ ...current, [paymentId]: { student_id: "", reference_code: "" } }));
    } catch (err) {
      setFormError(err.message || "Unable to recover payment.");
    }
  };

  const openFinancePrintout = ({ title, reference, metaRows = [], tableRows = [], totalLabel = "Total", total = 0, footer = "" }) => {
    const printWindow = window.open("", "_blank", "width=900,height=1100");
    if (!printWindow) {
      setFormError("Allow popups to print this document.");
      return;
    }
    const metaMarkup = metaRows
      .map(([label, value]) => `<div><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value || "-")}</div>`)
      .join("");
    const rowMarkup = tableRows
      .map(([label, value]) => `<tr><td>${escapeHtml(label)}</td><td>${escapeHtml(value)}</td></tr>`)
      .join("");
    const footerText = footer === "" ? "" : footer || "Generated from SchoolDom Finance.";
    const footerMarkup = footerText ? `<p class="footer">${escapeHtml(footerText)}</p>` : "";
    const schoolLogoMarkup = schoolBrand.logo
      ? `<img src="${escapeHtml(schoolBrand.logo)}" alt="${escapeHtml(schoolBrand.name)} logo" />`
      : `<span>${escapeHtml(schoolBrand.initials || "S")}</span>`;
    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>${escapeHtml(reference || title)}</title>
          <style>
            *{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#111827;font-family:Arial,sans-serif}.sheet{width:min(100%,900px);margin:14px auto;background:#fff;padding:34px 42px;border:1px solid #d8e0ea}.brand{display:flex;align-items:center;gap:12px;margin-bottom:28px}.brand-logo{width:56px;height:56px;border:1px solid #d8e0ea;border-radius:12px;display:grid;place-items:center;overflow:hidden;background:#fff;color:#0f3d5e;font-weight:900}.brand-logo img{width:100%;height:100%;object-fit:contain}.brand strong{display:block;font-size:20px}.doc-title{font-size:38px;letter-spacing:0;text-transform:uppercase;margin:0 0 18px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:10px 22px;margin-bottom:20px;font-size:12px}table{width:100%;border-collapse:collapse;margin:12px 0 18px}th,td{border-bottom:1px dashed #9ca3af;padding:10px;text-align:left}th{text-transform:uppercase;font-size:11px}td:last-child,th:last-child{text-align:right}.total{display:flex;justify-content:flex-end;gap:34px;font-size:20px;font-weight:900;margin-top:14px}.footer{border-top:1px dashed #9ca3af;margin-top:28px;padding-top:12px;text-align:center;color:#64748b;font-size:11px}@media print{@page{size:A4 portrait;margin:10mm}body{background:#fff}.sheet{width:100%;margin:0;border:none;padding:18px 22px}}
          </style>
        </head>
        <body>
          <main class="sheet">
            <header class="brand">
              <div class="brand-logo">${schoolLogoMarkup}</div>
              <strong>${escapeHtml(schoolBrand.name)}</strong>
            </header>
            <h1 class="doc-title">${escapeHtml(title)}</h1>
            <section class="meta">${metaMarkup}</section>
            <table>
              <thead><tr><th>Description</th><th>Amount</th></tr></thead>
              <tbody>${rowMarkup}</tbody>
            </table>
            <div class="total"><span>${escapeHtml(totalLabel)}</span><span>${escapeHtml(formatFinanceAmount(total))}</span></div>
            ${footerMarkup}
          </main>
          <script>window.onload=function(){window.print();};</script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  const handlePrintClassBill = (fee) => {
    const reference = `BILL-${String(fee.id || Date.now()).slice(0, 8).toUpperCase()}`;
    openFinancePrintout({
      title: "Bill",
      reference,
      metaRows: [
        ["Bill No", reference],
        [groupLabels.singular, fee.class_label],
        ["Fee", fee.title],
        ["Due Date", formatDate(fee.due_date)],
      ],
      tableRows: [[fee.title || "School fee", formatFinanceAmount(fee.amount)]],
      totalLabel: "Expected Total",
      total: fee.expected_amount ?? fee.amount,
      footer: "",
    });
  };

  const handlePrintTransactionReceipt = (item) => {
    const reference = item.reference || item.bank_reference || item.id || `RCPT-${Date.now()}`;
    openFinancePrintout({
      title: "Receipt",
      reference,
      metaRows: [
        ["Receipt No", reference],
        ["Date", formatDate(item.created_at || item.matched_at || item.date)],
        ["Status", item.status || "pending"],
        ["Type", item.tx_type || item.type || "School finance transaction"],
      ],
      tableRows: [[item.narration || item.description || item.reference || "Payment received", formatFinanceAmount(item.amount || item.value)]],
      totalLabel: "Amount Paid",
      total: item.amount || item.value,
      footer: "This receipt confirms the recorded finance transaction.",
    });
  };

  const classStats = classFees.map((fee) => {
    const expected = Number(fee.expected_amount || 0);
    const received = Number(fee.amount_received || 0);
    return {
      ...fee,
      collectionRate: expected > 0 ? Math.min(100, Math.round((received / expected) * 100)) : 0,
    };
  });
  const topClassStats = classStats.slice(0, 6);
  const recentTransactions = transactionHistory.slice(0, 6);
  const payrollRows = data?.hr_snapshot?.payroll || [];
  const pendingPayroll = payrollRows.filter((item) => item.status !== "paid").length;

  return (
    <section className="screen-grid finance-dashboard">
      <div className="school-finance-hero">
        <div>
          <p>SchoolDom Finance</p>
          <h2>Finance Dashboard</h2>
          <span>School fees, class collections, expenses, payroll, student payments, and reports in one workspace.</span>
        </div>
        <div className="school-finance-hero-stat">
          <small>Collection Rate</small>
          <strong>{receivedPercent}%</strong>
          <span>{formatFinanceAmount(receivedAmount)} collected</span>
        </div>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />
      {data ? (
        <>
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {formError ? <p className="form-feedback error">{formError}</p> : null}

          <div className="finance-summary-grid">
            <article className="finance-summary-card tone-expected">
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="currency-naira" className="inline-icon" />
              </div>
              <div>
                <p>Expected Fees</p>
                <strong>{formatFinanceAmount(expectedAmount)}</strong>
              </div>
            </article>
            <article className="finance-summary-card tone-received">
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="check" className="inline-icon" />
              </div>
              <div>
                <p>Fees Collected</p>
                <strong>{formatFinanceAmount(receivedAmount)}</strong>
              </div>
            </article>
            <article className="finance-summary-card tone-outstanding">
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="pending" className="inline-icon" />
              </div>
              <div>
                <p>Outstanding</p>
                <strong>{formatFinanceAmount(outstandingAmount)}</strong>
              </div>
            </article>
            <article className="finance-summary-card tone-received" title="Prepaid balances held for future fees">
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="money" className="inline-icon" />
              </div>
              <div>
                <p>Student Credit Balance</p>
                <strong>{formatFinanceAmount(studentCreditBalance)}</strong>
              </div>
            </article>
            <article
              className="finance-summary-card tone-received dashboard-click-card"
              role="button"
              tabIndex="0"
              onClick={scrollToTokenPurchase}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  scrollToTokenPurchase();
                }
              }}
              title="Buy activation tokens"
            >
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="check" className="inline-icon" />
              </div>
              <div>
                <p>Available Tokens</p>
                <strong>{Number(creditSummary.available_credits ?? creditPool.balance ?? 0).toLocaleString()}</strong>
              </div>
            </article>
            <article className="finance-summary-card tone-outstanding">
              <div className="finance-summary-icon" aria-hidden="true">
                <DashboardIcon name="requests" className="inline-icon" />
              </div>
              <div>
                <p>Inactive Students</p>
                <strong>{Number(creditSummary.inactive_students || 0).toLocaleString()}</strong>
              </div>
            </article>
          </div>

          {editingStudentFeeId ? (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="student-fee-edit-title" onClick={(e) => { if (e.target === e.currentTarget) resetStudentFeeForm(); }}>
              <article className="app-panel edit-modal-card student-fee-modal">
                <div className="edit-modal-head">
                  <div>
                    <h3 id="student-fee-edit-title">Edit Payment Record</h3>
                    <p>{selectedStudentFee?.student_name || "Selected student"}{selectedStudentFee?.student_identifier ? ` · ${selectedStudentFee.student_identifier}` : ""}</p>
                  </div>
                  <button type="button" className="edit-modal-close" onClick={resetStudentFeeForm} aria-label="Close"><X size={16} /></button>
                </div>
                <form className="modal-form-wrap" onSubmit={handleStudentFeeSubmit}>
                  <div className="form-section">
                    <div className="panel-form-grid">
                      <label className="panel-field">Fee title<input value={studentFeeForm.title} onChange={(e) => setStudentFeeForm((c) => ({ ...c, title: e.target.value }))} required /></label>
                      <label className="panel-field">Amount<input type="number" min="0" step="0.01" value={studentFeeForm.amount} onChange={(e) => setStudentFeeForm((c) => ({ ...c, amount: e.target.value }))} required /></label>
                      <label className="panel-field">Due date<input type="date" value={studentFeeForm.due_date} onChange={(e) => setStudentFeeForm((c) => ({ ...c, due_date: e.target.value }))} required /></label>
                      <label className="panel-field">Status<select value={studentFeeForm.status} onChange={(e) => setStudentFeeForm((c) => ({ ...c, status: e.target.value }))}><option value="pending">Pending</option><option value="paid">Paid</option><option value="overdue">Overdue</option></select></label>
                    </div>
                  </div>
                  <div className="panel-form-actions" style={{margin:"0.75rem 1.5rem 0",paddingTop:"1rem",borderTop:"1px solid #f1f5f9"}}>
                    <button type="submit" disabled={!onStudentFeeSave}>Update record</button>
                    <button type="button" className="btn-secondary" onClick={resetStudentFeeForm}>Cancel</button>
                  </div>
                </form>
              </article>
            </div>
          ) : null}

          <div className="finance-analytics-grid">
            <article className="app-panel finance-chart-panel">
              <div className="panel-head">
                <h3>Fee Analytics</h3>
                <small>{finance?.pending_payments ?? 0} pending student payments</small>
              </div>
              <div className="finance-chart-bars" aria-label="School fee collection analytics">
                <div>
                  <span>Received</span>
                  <strong>{receivedPercent}%</strong>
                  <div className="finance-chart-track"><i style={{ width: `${receivedPercent}%` }} /></div>
                </div>
                <div>
                  <span>Outstanding</span>
                  <strong>{outstandingPercent}%</strong>
                  <div className="finance-chart-track warning"><i style={{ width: `${outstandingPercent}%` }} /></div>
                </div>
              </div>
            </article>

            <article className="app-panel">
              <div className="panel-head">
                <h3>{groupLabels.singular} Finance Statistics</h3>
                <small>{classFees.length} fee schedules</small>
              </div>
              <div className="class-finance-stat-list">
                {topClassStats.length ? topClassStats.map((fee) => (
                  <div key={fee.id} className="class-finance-stat">
                    <div>
                      <strong>{fee.class_label}</strong>
                      <span>{fee.title} - {fee.student_count || 0} students</span>
                    </div>
                    <div className="class-finance-meter"><i style={{ width: `${fee.collectionRate}%` }} /></div>
                    <small>{fee.collectionRate}% collected</small>
                  </div>
                )) : <p className="panel-empty">No {groupLabels.fee.toLowerCase()} statistics yet.</p>}
              </div>
            </article>
          </div>

          {editingClassFeeId && <div className="modal-overlay-bg" onClick={() => { setEditingClassFeeId(""); setClassFeeForm({ school_class: "", title: "", amount: "", due_date: "" }); }} />}

          <div className="finance-workspace">
            <article
              className={`app-panel ${editingClassFeeId ? "edit-modal-card class-fee-edit-modal" : ""}`}
              role={editingClassFeeId ? "dialog" : undefined}
              aria-modal={editingClassFeeId ? "true" : undefined}
              aria-labelledby="class-fee-form-title"
            >
              <div className="edit-modal-head">
                <div>
                  <h3 id="class-fee-form-title">{editingClassFeeId ? `Update ${groupLabels.fee}` : `Create ${groupLabels.fee}`}</h3>
                  <p className="panel-sub">Create school-focused bills for each {groupLabels.singular.toLowerCase()}.</p>
                </div>
                {editingClassFeeId ? (
                  <button type="button" className="edit-modal-close" onClick={() => { setEditingClassFeeId(""); setClassFeeForm({ school_class: "", title: "", amount: "", due_date: "" }); }} aria-label="Close"><X size={16} /></button>
                ) : null}
              </div>
              <form className="panel-form" onSubmit={handleClassFeeSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field full">{groupLabels.singular}<select value={classFeeForm.school_class} onChange={(event) => setClassFeeForm((current) => ({ ...current, school_class: event.target.value }))} required><option value="">{groupLabels.select}</option>{classOptions.map((item) => (<option key={item.id || item.value || item.name} value={item.id || item.value || item.school_class || item.name}>{item.label || item.name || item.class_label || item.value}</option>))}</select></label>
                  <label className="panel-field">Fee title<input value={classFeeForm.title} onChange={(event) => setClassFeeForm((current) => ({ ...current, title: event.target.value }))} placeholder="Term school fees" required /></label>
                  <label className="panel-field">Amount<input type="number" min="0" step="0.01" value={classFeeForm.amount} onChange={(event) => setClassFeeForm((current) => ({ ...current, amount: event.target.value }))} required /></label>
                  <label className="panel-field">Due date<input type="date" value={classFeeForm.due_date} onChange={(event) => setClassFeeForm((current) => ({ ...current, due_date: event.target.value }))} required /></label>
                </div>
                <div className="panel-form-actions">
                  <button type="submit" disabled={!onClassFeeSave}>{editingClassFeeId ? `Update ${groupLabels.fee.toLowerCase()}` : `Create ${groupLabels.fee.toLowerCase()}`}</button>
                  {editingClassFeeId ? <button type="button" className="btn-secondary" onClick={() => { setEditingClassFeeId(""); setClassFeeForm({ school_class: "", title: "", amount: "", due_date: "" }); }}>Cancel</button> : null}
                </div>
              </form>
            </article>

            <article className="app-panel">
              <div className="panel-head">
                <h3>Settlement Bank Account</h3>
                <small>
                  {adminWallet.subaccount_code
                    ? "Configured - parents' bank transfers split automatically to this account."
                    : "Required before parent virtual accounts can be provisioned."}
                </small>
              </div>
              {subaccountMessage ? <p className="form-feedback success">{subaccountMessage}</p> : null}
              {subaccountError ? <p className="form-feedback error">{subaccountError}</p> : null}
              <form className="panel-form" onSubmit={handleSubaccountSetupSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field full">
                    Settlement bank
                    <input
                      list="settlement-bank-options"
                      value={subaccountBankQuery}
                      onChange={(event) => handleSubaccountBankQueryChange(event.target.value)}
                      placeholder={subaccountBanksLoading ? "Loading banks..." : "Start typing to search banks"}
                      autoComplete="off"
                      required
                    />
                    <datalist id="settlement-bank-options">
                      {subaccountBanks.map((bank) => (
                        <option key={bank.code} value={bank.name} />
                      ))}
                    </datalist>
                    {subaccountBankQuery && !subaccountForm.bank_code ? (
                      <small className="field-note">No matching bank - pick one from the suggestions.</small>
                    ) : null}
                  </label>
                  <label className="panel-field">
                    Account number
                    <input
                      value={subaccountForm.account_number}
                      onChange={(event) => setSubaccountForm((current) => ({ ...current, account_number: event.target.value.replace(/\D/g, "").slice(0, 10), account_name: "" }))}
                      placeholder="0123456789"
                      maxLength={10}
                      inputMode="numeric"
                      required
                    />
                  </label>
                  <label className="panel-field">
                    Account name
                    <input
                      value={resolveLoading ? "" : subaccountForm.account_name}
                      onChange={(event) => setSubaccountForm((current) => ({ ...current, account_name: event.target.value }))}
                      placeholder={resolveLoading ? "Fetching account name…" : "Auto-filled after account number"}
                      readOnly={resolveLoading}
                      required
                    />
                    {resolveError ? <small className="field-note" style={{ color: "#ef4444" }}>{resolveError}</small> : null}
                  </label>
                </div>
                <div className="panel-form-actions">
                  <button type="submit" disabled={!onPaystackSubaccountSetup || subaccountBusy}>
                    {subaccountBusy ? "Saving..." : adminWallet.subaccount_code ? "Update bank account" : "Create subaccount"}
                  </button>
                </div>
              </form>
            </article>

          </div>

          <article className="app-panel">
            <div className="mobile-section-head">
              <h3>Student Bank Payment History</h3>
              <small>{bankPaymentRows.length} bank payment records</small>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Student</th><th>Reference</th><th>Bank Ref</th><th>Narration</th><th>Amount</th><th>Applied</th><th>Balance</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
                <tbody>{bankPaymentRows.length ? visibleBankPaymentRows.map((payment) => {
                  const recovery = recoveryForm[payment.id] || {};
                  const canRecover = ["unmatched", "pending"].includes(payment.status);
                  return (
                    <tr key={payment.id}>
                      <td>{payment.student_name || "Unmatched"}<small>{payment.student_id || "No student linked"}</small></td>
                      <td>{payment.reference_code || "-"}</td>
                      <td>{payment.bank_reference || "-"}</td>
                      <td>{payment.narration || "-"}</td>
                      <td>{formatFinanceAmount(payment.amount)}</td>
                      <td>{formatFinanceAmount(payment.applied_amount)}</td>
                      <td>{formatFinanceAmount(payment.unapplied_amount)}</td>
                      <td><span className={`finance-status status-${payment.status || "pending"}`}>{payment.status || "pending"}</span></td>
                      <td>{formatDate(payment.matched_at || payment.created_at)}</td>
                      <td>
                        {canRecover ? (
                          <div className="table-actions-inline">
                            <input
                              className="table-inline-input"
                              value={recovery.reference_code || recovery.student_id || ""}
                              onChange={(event) => setRecoveryForm((current) => ({ ...current, [payment.id]: { reference_code: event.target.value } }))}
                              placeholder="Student ref"
                              aria-label="Student payment reference"
                            />
                            <button type="button" className="table-action" onClick={() => handleRecoverPayment(payment.id)} disabled={!onBankPaymentRecover}>Match</button>
                          </div>
                        ) : (
                          <span className="field-note">Matched</span>
                        )}
                      </td>
                    </tr>
                  );
                }) : <tr><td colSpan="10">No student bank payments found.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("bankPaymentHistory", bankPaymentRows.length)}
            </div>
          </article>

          <article className="app-panel">
            <div className="mobile-section-head">
              <h3>Student Payment Records</h3>
              <select value={mobileFinanceSection} onChange={(event) => setMobileFinanceSection(event.target.value)}>
                <option value="student-payments">Student Payment Records</option>
                <option value="student-fees">Student Fees</option>
                <option value="class-fees">{groupLabels.fee} Schedule</option>
                <option value="transactions">Transaction History</option>
              </select>
            </div>
            <div className={`table-scroll mobile-finance-panel ${mobileFinanceSection === "student-payments" ? "active" : ""}`}>
              <table className="data-table">
                <thead><tr><th>Student</th><th>{groupLabels.singular}</th><th>Status</th><th>Expected</th><th>Paid</th><th>Balance</th></tr></thead>
                <tbody>{paymentRows.length ? visiblePaymentRows.map((row) => (<tr key={row.id}><td>{row.name}<small>{row.student_id}</small></td><td>{row.class_name}</td><td><span className={`finance-status status-${row.payment_status}`}>{row.payment_status}</span></td><td>{formatFinanceAmount(row.expected_amount)}</td><td>{formatFinanceAmount(row.amount_paid)}</td><td>{formatFinanceAmount(row.remaining_balance)}</td></tr>)) : <tr><td colSpan="6">No student payments found.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("studentPayments", paymentRows.length)}
            </div>
            <div className={`table-scroll mobile-finance-panel ${mobileFinanceSection === "student-fees" ? "active" : ""}`}>
              <table className="data-table">
                <thead><tr><th>Student</th><th>{groupLabels.singular}</th><th>Fee</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Status</th><th>Edit</th></tr></thead>
                <tbody>{studentFeeRows.length ? visibleStudentFeeRows.map((fee) => (<tr key={fee.id}><td>{fee.student_name}<small>{fee.student_identifier}</small></td><td>{fee.class_label}</td><td>{fee.title}</td><td>{formatFinanceAmount(fee.amount)}</td><td>{formatFinanceAmount(fee.amount_paid)}</td><td>{formatFinanceAmount(fee.remaining_balance)}</td><td><span className={`finance-status status-${fee.payment_status || fee.status}`}>{fee.payment_status || fee.status}</span></td><td><button type="button" className="table-action" onClick={() => startEditStudentFee(fee)}>Edit</button></td></tr>)) : <tr><td colSpan="8">No student fees generated yet.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("studentFees", studentFeeRows.length)}
            </div>
            <div className={`table-scroll mobile-finance-panel ${mobileFinanceSection === "class-fees" ? "active" : ""}`}>
              <table className="data-table">
                <thead><tr><th>{groupLabels.singular}</th><th>Fee</th><th>Students</th><th>Expected</th><th>Received</th><th>Due</th><th>Action</th></tr></thead>
                <tbody>{classFees.length ? visibleClassFees.map((fee) => (<tr key={fee.id}><td>{fee.class_label}</td><td>{fee.title}<small>{formatFinanceAmount(fee.amount)}</small></td><td>{fee.student_count}</td><td>{formatFinanceAmount(fee.expected_amount)}</td><td>{formatFinanceAmount(fee.amount_received)}</td><td>{formatDate(fee.due_date)}</td><td><div className="table-actions-inline"><button type="button" className="table-action" onClick={() => handlePrintClassBill(fee)}>Bill</button><button type="button" className="table-action" onClick={() => startEditClassFee(fee)}>Edit</button><button type="button" className="table-action danger" onClick={() => handleDeactivateClassFee(fee.id)}>Deactivate</button></div></td></tr>)) : <tr><td colSpan="7">No {groupLabels.fee.toLowerCase()} configured yet.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("classFees", classFees.length)}
            </div>
            <div className={`table-scroll mobile-finance-panel ${mobileFinanceSection === "transactions" ? "active" : ""}`}>
              <table className="data-table">
                <thead><tr><th>Date</th><th>Description</th><th>Status</th><th>Amount</th><th>Action</th></tr></thead>
                <tbody>{recentTransactions.length ? recentTransactions.map((item) => (<tr key={item.id || item.reference || item.description}><td>{formatDate(item.created_at || item.date)}</td><td>{item.narration || item.description || item.tx_type || item.type || item.reference || "School finance transaction"}</td><td><span className={`finance-status status-${item.status || "pending"}`}>{item.status || "pending"}</span></td><td>{formatFinanceAmount(item.amount || item.value)}</td><td><button type="button" className="table-action" onClick={() => handlePrintTransactionReceipt(item)}>Receipt</button></td></tr>)) : <tr><td colSpan="5">No transactions yet.</td></tr>}</tbody>
              </table>
            </div>
          </article>

          <section className="activation-credit-grid">
            <article className="app-panel activation-credit-panel" ref={tokenPurchaseRef} style={{ order: 2 }}>
              <div className="panel-head">
                <h3>Activation Tokens</h3>
                <small>Buy tokens, verify payments, and activate student access from this finance page. {tokenDurationText}.</small>
              </div>
              <div className="activation-credit-summary">
                <span>Balance <strong>{Number(creditSummary.available_credits ?? creditPool.balance ?? 0).toLocaleString()}</strong></span>
                <span>Active <strong>{Number(creditSummary.active_students || 0).toLocaleString()}</strong></span>
                <span>Inactive <strong>{Number(creditSummary.inactive_students || 0).toLocaleString()}</strong></span>
                <span>Excluded <strong>{Number(creditSummary.excluded_students || 0).toLocaleString()}</strong></span>
              </div>
              <form className="panel-form" onSubmit={handleCreditPurchaseSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field">Tokens to buy<input type="number" min="1" value={creditPurchaseForm.credits} onChange={(event) => setCreditPurchaseForm({ credits: event.target.value })} placeholder="100" /></label>
                  <label className="panel-field">Estimated total<input value={formatFinanceAmount(Math.max(requestedCreditCount, 0) * tokenUnitPrice)} readOnly /></label>
                  <label className="panel-field">Bonus tokens<input value={bonusCreditCount ? `${bonusCreditCount} bonus` : "No bonus"} readOnly /></label>
                </div>
                <div className="panel-form-actions">
                  <button type="submit" disabled={!onPurchaseCredits || requestedCreditCount < 1}>Buy tokens</button>
                  {creditPurchaseUrl ? <a className="table-action" href={creditPurchaseUrl} target="_blank" rel="noreferrer">Open checkout</a> : null}
                </div>
              </form>
              <form className="panel-form inline-credit-form" onSubmit={(event) => { event.preventDefault(); if (creditPurchaseReference && onVerifyCredits) onVerifyCredits({ reference: creditPurchaseReference }); }}>
                <label className="panel-field full">Payment reference<input value={creditPurchaseReference} onChange={(event) => setCreditPurchaseReference(event.target.value)} placeholder="Flutterwave reference" /></label>
                <button type="submit" disabled={!onVerifyCredits || !creditPurchaseReference}>Verify payment</button>
              </form>
            </article>

            <article className="app-panel activation-credit-panel" style={{ order: 1 }}>
              <div className="panel-head">
                <h3>Assign Tokens</h3>
                <small>Activate all eligible students or students who have paid at least 50%.</small>
              </div>
              <form className="panel-form" onSubmit={handleCreditAssignSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field">Scope<select value={creditAssignForm.scope} onChange={(event) => setCreditAssignForm((current) => ({ ...current, scope: event.target.value, student_id: event.target.value === "student" ? current.student_id : "" }))}><option value="student">Selected inactive student</option><option value="all">All inactive students ({creditSummary.eligible_all || 0})</option><option value="paid_50">Paid 50% and above ({creditSummary.eligible_paid_50 || 0})</option></select></label>
                  <label className="panel-field">Tokens to assign<input type="number" min="1" value={creditAssignForm.months} onChange={(event) => setCreditAssignForm((current) => ({ ...current, months: event.target.value }))} /></label>
                  {creditAssignForm.scope === "student" && (
                    <>
                      <label className="panel-field">Search inactive student<input value={creditStudentSearch} onChange={(event) => setCreditStudentSearch(event.target.value)} placeholder="Name, email, or student ID" /></label>
                      <label className="panel-field">Assign to inactive student<select value={creditAssignForm.student_id} onChange={(event) => setCreditAssignForm((current) => ({ ...current, student_id: event.target.value }))}><option value="">Select inactive student</option>{filteredInactiveCreditRows.map((row) => (<option key={row.student_id} value={row.student_id}>{row.student_name || "Unnamed student"}{row.student_identifier ? ` - ${row.student_identifier}` : ""}{row.student_email ? ` - ${row.student_email}` : ""}</option>))}</select></label>
                    </>
                  )}
                </div>
                {creditAssignForm.scope === "student" && !filteredInactiveCreditRows.length && (
                  <p className="form-hint">No inactive student matches that search.</p>
                )}
                <div className="panel-form-actions">
                  <button type="submit" disabled={!onAssignCredits}>Assign tokens</button>
                  <button type="button" className="table-action" onClick={handleRunAutoCredits} disabled={!onRunAutoCredits}>Run auto assign</button>
                </div>
              </form>
              <form className="panel-form" onSubmit={handleCreditSettingsSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field">Auto assignment<select value={creditSettingsForm.enabled ? "on" : "off"} onChange={(event) => setCreditSettingsForm((current) => ({ ...current, enabled: event.target.value === "on" }))}><option value="off">Off</option><option value="on">On</option></select></label>
                  <label className="panel-field">Auto scope<select value={creditSettingsForm.scope} onChange={(event) => setCreditSettingsForm((current) => ({ ...current, scope: event.target.value }))}><option value="all">All inactive students</option><option value="paid_50">Paid 50% and above</option></select></label>
                </div>
                <div className="panel-form-actions">
                  <button type="submit" disabled={!onCreditSettings}>Save token settings</button>
                </div>
              </form>
            </article>
          </section>

          <article className="app-panel">
            <div className="mobile-section-head">
              <h3>Finance Ledger Log</h3>
              <small>Append-only record of financial activity</small>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Date</th><th>Action</th><th>Description</th><th>Amount</th><th>Reference</th><th>Actor</th></tr></thead>
                <tbody>{financeLedgerRows.length ? visibleFinanceLedgerRows.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDate(item.created_at)}</td>
                    <td>{item.action}</td>
                    <td>{item.description}</td>
                    <td>{formatFinanceAmount(item.amount)}</td>
                    <td>{item.reference || "-"}</td>
                    <td>{item.actor_name || "System"}</td>
                  </tr>
                )) : <tr><td colSpan="6">No finance activity logged yet.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("financeLedger", financeLedgerRows.length)}
            </div>
          </article>

          <article className="app-panel">
            <div className="mobile-section-head">
              <h3>Token Activity</h3>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Student</th><th>Status</th><th>Assigned</th><th>Active Until</th><th>Inactive Since</th><th>Excluded</th></tr></thead>
                <tbody>{creditRows.length ? visibleCreditRows.map((row) => (<tr key={row.id}><td>{row.student_name}<small>{row.student_id}</small></td><td><span className={`finance-status status-${row.active_until ? "paid" : "pending"}`}>{row.active_until ? "active" : "inactive"}</span></td><td>{row.credits_assigned}</td><td>{formatDate(row.active_until)}</td><td>{formatDate(row.inactive_since)}</td><td>{row.is_excluded_from_auto_deductions ? "Yes" : "No"}</td></tr>)) : <tr><td colSpan="6">No activation token records yet.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("activationAlerts", creditRows.length)}
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Date</th><th>Reference</th><th>Tokens</th><th>Amount</th><th>Status</th></tr></thead>
                <tbody>{creditPurchaseHistory.length ? visibleCreditPurchaseHistory.map((row) => (<tr key={row.id || row.reference}><td>{formatDate(row.created_at)}</td><td>{row.reference}</td><td>{Number(row.total_credits || row.credits || 0).toLocaleString()}<small>{Number(row.bonus_credits || 0) ? `${row.bonus_credits} bonus` : ""}</small></td><td>{formatFinanceAmount(row.amount)}</td><td><span className={`finance-status status-${row.status || "pending"}`}>{row.status || "pending"}</span></td></tr>)) : <tr><td colSpan="5">No token purchases yet.</td></tr>}</tbody>
              </table>
              {renderFinanceMoreButton("creditHistory", creditPurchaseHistory.length)}
            </div>
          </article>

          <article className="app-panel">
            <div className="mobile-section-head">
              <h3>Virtual Accounts</h3>
              <small>Auto-generate a dedicated account number per parent for bank-transfer fee payments.</small>
            </div>
            {vaActionMessage ? <p className="form-feedback success">{vaActionMessage}</p> : null}
            {vaActionError ? <p className="form-feedback error">{vaActionError}</p> : null}
            {vaListError ? <p className="form-feedback error">{vaListError}</p> : null}
            <div className="panel-form-actions" style={{ margin: "0.5rem 0 0.75rem" }}>
              <input
                type="text"
                placeholder="Search parent by name, email, or account number"
                value={vaSearch}
                onChange={(event) => setVaSearch(event.target.value)}
                style={{ maxWidth: "320px" }}
              />
              <button type="button" onClick={loadVirtualAccountsList} disabled={vaListLoading}>
                {vaListLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {filteredVaParentsWithoutAccount.length ? (
              <div className="table-scroll">
                <table className="data-table">
                  <thead><tr><th>Parent (no account yet)</th><th>Email</th><th>Action</th></tr></thead>
                  <tbody>
                    {filteredVaParentsWithoutAccount.map((row) => (
                      <tr key={row.parent_id}>
                        <td>{row.parent_name}</td>
                        <td>{row.parent_email}</td>
                        <td>
                          <button
                            type="button"
                            className="table-action active"
                            onClick={() => handleProvisionVirtualAccount(row.parent_id)}
                            disabled={vaBusyParentId === row.parent_id}
                          >
                            {vaBusyParentId === row.parent_id ? "Provisioning..." : "Provision Account"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Parent</th><th>Account Number</th><th>Bank</th><th>Provider</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                  {filteredVaAccounts.length ? filteredVaAccounts.map((row) => (
                    <tr key={row.parent_id}>
                      <td>{row.parent_name}<small>{row.parent_email}</small></td>
                      <td>{row.account_number}</td>
                      <td>{row.bank_name}</td>
                      <td>{row.provider === "paystack" ? "Automated" : row.provider}</td>
                      <td><span className={`finance-status status-${row.is_active ? "paid" : "pending"}`}>{row.is_active ? "active" : "inactive"}</span></td>
                      <td>
                        {row.provider === "paystack" ? (
                          <button
                            type="button"
                            className="table-action"
                            onClick={() => handleProvisionVirtualAccount(row.parent_id)}
                            disabled={vaBusyParentId === row.parent_id}
                          >
                            {vaBusyParentId === row.parent_id ? "Working..." : "Re-provision"}
                          </button>
                        ) : (
                          <small>Manually assigned</small>
                        )}
                      </td>
                    </tr>
                  )) : <tr><td colSpan="6">No virtual accounts assigned yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </article>
        </>
      ) : null}
    </section>
  );

}

function AdminExamResultsScreen({ data = {}, loading, error, onRetry, onUpload, onDeleteResult, onDeleteExam, session, onCreateExam, onUpdateExam }) {
  const results = data?.exam_results || data?.submitted_results || data?.cbt_results || data?.results || [];
  const autoSubmissions = data?.auto_submitted_exams || data?.auto_submissions || [];
  const exams = data?.exams || data?.available_exams || [];
  const classOptions = data?.options?.classes || data?.classes || [];
  const subjectOptions = (data?.options?.subjects || data?.subjects || []).filter((subject) => {
    const code = `${subject?.code || ""}`.trim().toUpperCase();
    const name = `${subject?.name || ""}`.trim().toLowerCase();
    return !["PHY", "CHEM"].includes(code) && !["physics", "chemistry"].includes(name);
  });
  const broadsheetSchool = resolveSchoolBrand(data?.school, session?.school, session?.user?.school);

  const [activeView, setActiveView] = useState("desktop");
  const [editingExam, setEditingExam] = useState(null);
  const [editError, setEditError] = useState("");
  const [loadingExamId, setLoadingExamId] = useState("");
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [subjectFilter, setSubjectFilter] = useState("all");
  const [sortKey, setSortKey] = useState("score");
  const [broadsheetExamId, setBroadsheetExamId] = useState("all");
  const [broadsheetClassName, setBroadsheetClassName] = useState("all");
  const [broadsheetType, setBroadsheetType] = useState("Examination broadsheet");
  const [uploadExamId, setUploadExamId] = useState(exams[0]?.id || exams[0]?.exam_id || "");
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [deleteBusyId, setDeleteBusyId] = useState("");
  const [deleteFeedback, setDeleteFeedback] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [pendingDeleteResult, setPendingDeleteResult] = useState(null);
  const [examPins, setExamPins] = useState({});
  const [visiblePins, setVisiblePins] = useState({});
  const [pinBusyId, setPinBusyId] = useState("");
  const [pinFeedback, setPinFeedback] = useState("");
  const [pinError, setPinError] = useState("");
  const [deleteExamBusyId, setDeleteExamBusyId] = useState("");
  const [deleteExamError, setDeleteExamError] = useState("");
  const [deleteExamFeedback, setDeleteExamFeedback] = useState("");
  const fileInputRef = useRef(null);
  const [confirm, confirmDialog] = useConfirm();

  useEffect(() => {
    setUploadExamId((previous) => previous || exams[0]?.id || exams[0]?.exam_id || "");
  }, [exams]);

  const handleEditExam = async (examId) => {
    setLoadingExamId(examId);
    setEditError("");
    try {
      const result = await requestJson(session, "GET", `/api/app/exams/${examId}/`);
      setEditingExam(result.exam || null);
      setActiveView("builder");
    } catch (loadError) {
      setEditError(loadError.message || "Could not open exam.");
    } finally {
      setLoadingExamId("");
    }
  };

  const generateExamPin = async (exam) => {
    const examId = exam.id || exam.exam_id;
    if (!examId) return;
    setPinBusyId(String(examId));
    setPinFeedback("");
    setPinError("");
    try {
      const result = await requestJson(session, "POST", "/api/app/exams/pins/", {
        exam_id: examId,
        usage_policy: "reusable",
        expires_at: exam.end_date || exam.endDate || "",
      });
      const plainPin = result.plain_pin || "";
      setExamPins((previous) => ({
        ...previous,
        [examId]: {
          plain: result.pin?.plain_pin || plainPin,
          preview: result.pin?.pin_preview || plainPin.slice(-4),
        },
      }));
      setVisiblePins((previous) => ({ ...previous, [examId]: false }));
      setPinFeedback(`PIN generated for ${exam.title || exam.name || "exam"}.`);
      onRetry?.();
    } catch (pinGenerateError) {
      setPinError(pinGenerateError.message || "Could not generate PIN.");
    } finally {
      setPinBusyId("");
    }
  };

  const toggleExamPin = (examId) => {
    setVisiblePins((previous) => ({ ...previous, [examId]: !previous[examId] }));
  };

  const handlePinEyeClick = (examId, canReveal) => {
    if (!canReveal) {
      setPinError("This PIN was created before full PIN viewing was enabled. Generate a new PIN once to make it viewable anytime.");
      return;
    }
    setPinError("");
    toggleExamPin(examId);
  };

  const renderExamPinCell = (exam) => {
    const examId = exam.id || exam.exam_id;
    const generated = examPins[examId];
    const revealablePin = generated?.plain || exam.active_pin_plain || exam.plain_pin || "";
    const hasActivePin = Boolean(exam.pin_required || generated?.plain);
    const preview = generated?.preview || exam.active_pin_preview || "";
    const canReveal = Boolean(revealablePin);
    const isVisible = Boolean(visiblePins[examId] && canReveal);
    const displayValue = isVisible
      ? revealablePin
      : hasActivePin
        ? "\u2022".repeat(Math.max(6, String(preview || revealablePin || "").length || 6))
        : "No PIN";

    return (
      <div className="exam-pin-cell">
        <span className={`exam-pin-code ${hasActivePin ? "" : "empty"}`}>{displayValue}</span>
        {hasActivePin ? (
          <button
            type="button"
            className="exam-pin-eye"
            onClick={() => handlePinEyeClick(examId, canReveal)}
            title={canReveal ? (isVisible ? "Hide PIN" : "Show PIN") : "Regenerate this old PIN once to view it anytime"}
            aria-label={canReveal ? (isVisible ? "Hide PIN" : "Show PIN") : "PIN cannot be revealed yet"}
          >
            <EyeIcon closed={isVisible} />
          </button>
        ) : null}
        {exam.is_published ? (
          <button
            type="button"
            className={`table-action ${hasActivePin ? "active" : ""}`}
            onClick={() => generateExamPin(exam)}
            disabled={pinBusyId === String(examId)}
          >
            {pinBusyId === String(examId) ? "Generating..." : hasActivePin ? "New PIN" : "Generate"}
          </button>
        ) : (
          <small>Publish first</small>
        )}
      </div>
    );
  };

  const handleDeleteExam = async (exam) => {
    const examId = exam.id || exam.exam_id;
    if (!examId || !onDeleteExam) return;
    const title = exam.title || exam.name || "this exam";
    const ok = await confirm({ title: "Delete Exam", message: `Delete "${title}"? Students will no longer see this exam.`, confirmLabel: "Delete", danger: true });
    if (!ok) {
      return;
    }
    setDeleteExamBusyId(String(examId));
    setDeleteExamError("");
    setDeleteExamFeedback("");
    try {
      const result = await onDeleteExam(examId);
      setDeleteExamFeedback(result?.message || "Exam deleted.");
      if (editingExam?.id === examId) {
        setEditingExam(null);
      }
    } catch (deleteError) {
      setDeleteExamError(deleteError.message || "Could not delete exam.");
    } finally {
      setDeleteExamBusyId("");
    }
  };

  const uniqueClasses = useMemo(() => {
    return Array.from(
      new Set(
        results
          .map((row) => row.class_name || row.class || row.class_label)
          .filter(Boolean)
      )
    );
  }, [results]);

  const uniqueSubjects = useMemo(() => {
    const subjects = new Set();
    results.forEach((row) => {
      if (Array.isArray(row.subjects)) {
        row.subjects.forEach((item) => subjects.add(item));
      } else if (row.subject) {
        subjects.add(row.subject);
      }
    });
    return Array.from(subjects);
  }, [results]);

  const filteredResults = useMemo(() => {
    const searchLower = search.trim().toLowerCase();
    return [...results]
      .filter((row) => {
        const matchesSearch =
          !searchLower ||
          `${row.student_name || ""}`.toLowerCase().includes(searchLower) ||
          `${row.reg_no || row.registration_no || ""}`.toLowerCase().includes(searchLower) ||
          `${row.exam_title || row.exam || ""}`.toLowerCase().includes(searchLower);

        const matchesClass =
          classFilter === "all" ||
          (row.class_name || row.class || "").toString().toLowerCase() === classFilter;

        const subjectSet = Array.isArray(row.subjects)
          ? row.subjects.map((item) => `${item}`.toLowerCase())
          : row.subject
            ? [`${row.subject}`.toLowerCase()]
            : [];
        const matchesSubject =
          subjectFilter === "all" ||
          subjectSet.includes(subjectFilter);

        return matchesSearch && matchesClass && matchesSubject;
      })
      .sort((a, b) => {
        if (sortKey === "name") {
          return (a.student_name || "").localeCompare(b.student_name || "");
        }
        if (sortKey === "time") {
          const aTime = parseFloat(a.total_time) || 0;
          const bTime = parseFloat(b.total_time) || 0;
          return bTime - aTime;
        }
        const aScore = parseFloat(a.score ?? a.obtained) || 0;
        const bScore = parseFloat(b.score ?? b.obtained) || 0;
        return bScore - aScore;
      });
  }, [classFilter, results, search, sortKey, subjectFilter]);

  const averageScore = useMemo(() => {
    if (!results.length) {
      return null;
    }
    const numeric = results
      .map((row) => parseFloat(row.score ?? row.obtained))
      .filter((value) => !Number.isNaN(value));
    if (!numeric.length) {
      return null;
    }
    return Math.round(numeric.reduce((sum, value) => sum + value, 0) / numeric.length);
  }, [results]);

  const topScore = useMemo(() => {
    const numeric = results
      .map((row) => parseFloat(row.score ?? row.obtained))
      .filter((value) => !Number.isNaN(value));
    return numeric.length ? Math.max(...numeric) : null;
  }, [results]);

  const broadsheetData = useMemo(() => {
    const selectedExam = String(broadsheetExamId || "all");
    const selectedClass = String(broadsheetClassName || "all").toLowerCase();
    const sourceRows = results.filter((row) => {
      const rowExamId = String(row.exam_id || row.examId || "");
      const rowClass = String(row.class_name || row.class || row.class_label || "").toLowerCase();
      const matchesExam = selectedExam === "all" || rowExamId === selectedExam;
      const matchesClass = selectedClass === "all" || rowClass === selectedClass;
      return matchesExam && matchesClass;
    });
    const subjects = new Set();
    const students = new Map();

    const subjectScoreEntries = (row) => {
      const breakdown = row.score_by_subject || row.correct_attempt_by_subject || row.attempt_by_subject;
      if (breakdown && typeof breakdown === "object" && !Array.isArray(breakdown)) {
        return Object.entries(breakdown).map(([subject, value]) => [subject, typeof value === "object" ? value.score ?? value.percentage ?? value.total ?? "" : value]);
      }
      const subject = row.subject || (Array.isArray(row.subjects) ? row.subjects[0] : "") || "Score";
      return [[subject, row.score ?? row.obtained ?? row.percentage ?? ""]];
    };

    sourceRows.forEach((row) => {
      const studentId = row.student_id || row.admission_number || row.reg_no || row.registration_no || row.student_email || row.student_name || "Unknown";
      const key = String(studentId);
      const className = row.class_name || row.class || row.class_label || "";
      const department = row.department || row.stream || row.section || String(className).split("-").slice(1).join("-").trim() || "";
      if (!students.has(key)) {
        students.set(key, {
          studentId,
          name: row.student_name || row.name || "Student",
          className,
          department,
          scores: {},
        });
      }
      const student = students.get(key);
      subjectScoreEntries(row).forEach(([subject, value]) => {
        const label = String(subject || "Score").trim() || "Score";
        subjects.add(label);
        const numeric = Number(value);
        student.scores[label] = Number.isFinite(numeric) ? numeric : value;
      });
    });

    const subjectList = Array.from(subjects).sort((a, b) => a.localeCompare(b));
    const rows = Array.from(students.values())
      .map((student) => {
        const total = subjectList.reduce((sum, subject) => {
          const value = Number(student.scores[subject]);
          return sum + (Number.isFinite(value) ? value : 0);
        }, 0);
        return { ...student, total };
      })
      .sort((a, b) => String(a.className).localeCompare(String(b.className)) || String(a.name).localeCompare(String(b.name)));

    return { rows, subjects: subjectList };
  }, [broadsheetClassName, broadsheetExamId, results]);

  const broadsheetFileName = () => {
    const selectedExam = exams.find((exam) => String(exam.id || exam.exam_id) === String(broadsheetExamId));
    const examPart = selectedExam?.title || selectedExam?.name || (broadsheetExamId === "all" ? "all-exams" : "exam");
    const classPart = broadsheetClassName === "all" ? "all-classes" : broadsheetClassName;
    return `${String(examPart).replace(/[^a-z0-9]+/gi, "-")}-${String(classPart).replace(/[^a-z0-9]+/gi, "-")}-broadsheet`;
  };

  const openBroadsheet = () => {
    const printWindow = window.open("", "_blank", "width=1200,height=800");
    if (!printWindow) {
      setUploadError("Allow popups to open the broadsheet.");
      return;
    }
    const headers = ["Student ID", "Name", "Class", "Department", ...broadsheetData.subjects, "Total"];
    const rows = broadsheetData.rows.map((student) => [
      student.studentId,
      student.name,
      student.className,
      student.department || "-",
      ...broadsheetData.subjects.map((subject) => student.scores[subject] ?? ""),
      student.total,
    ]);
    const tableHead = headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("");
    const tableRows = rows.length
      ? rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")
      : `<tr><td colspan="${headers.length}">No result records found for this selection.</td></tr>`;
    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>${escapeHtml(broadsheetType || "Exam Broadsheet")}</title>
          <style>
            *{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#111827;font-family:Arial,sans-serif}.sheet{width:max-content;min-width:100%;padding:24px}.paper{background:#fff;border:1px solid #cbd5e1;padding:24px;box-shadow:0 18px 45px rgba(15,23,42,.12)}.school-name{margin:0 0 4px;font-size:18px;font-weight:900;text-transform:uppercase;color:#0f172a}h1{margin:0 0 6px;font-size:24px;text-transform:uppercase}p{margin:0 0 18px;color:#475569}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #94a3b8;padding:8px 10px;text-align:left;white-space:nowrap}th{background:#e8f2fb;text-transform:uppercase;font-size:11px}td:last-child,th:last-child{font-weight:900;background:#f8fafc}.actions{margin:0 0 14px;display:flex;gap:10px}.actions button{border:0;border-radius:8px;background:#0f3d5e;color:#fff;padding:10px 14px;font-weight:800;cursor:pointer}@media print{body{background:#fff}.actions{display:none}.sheet{padding:0}.paper{box-shadow:none;border:0}}
          </style>
        </head>
        <body>
          <main class="sheet">
            <div class="paper">
              <div class="actions"><button onclick="window.print()">Print / Save PDF</button></div>
              <div class="school-name">${escapeHtml(broadsheetSchool.name)}</div>
              <h1>${escapeHtml(broadsheetType || "Exam Broadsheet")}</h1>
              <p>${escapeHtml(broadsheetData.rows.length)} student${broadsheetData.rows.length === 1 ? "" : "s"} shown</p>
              <table><thead><tr>${tableHead}</tr></thead><tbody>${tableRows}</tbody></table>
            </div>
          </main>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  const downloadBroadsheetCsv = () => {
    const headers = ["Student ID", "Name", "Class", "Department", ...broadsheetData.subjects, "Total"];
    const csvEscape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const lines = [
      [broadsheetSchool.name],
      [broadsheetType || "Exam Broadsheet"],
      headers,
      ...broadsheetData.rows.map((student) => [
        student.studentId,
        student.name,
        student.className,
        student.department || "",
        ...broadsheetData.subjects.map((subject) => student.scores[subject] ?? ""),
        student.total,
      ]),
    ].map((row) => row.map(csvEscape).join(","));
    const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${broadsheetFileName()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleUploadSubmit = async (event) => {
    event.preventDefault();
    if (!onUpload) {
      return;
    }
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setUploadError("Attach a file first.");
      return;
    }
    if (!uploadExamId) {
      setUploadError("Select an exam before uploading.");
      return;
    }
    setUploadBusy(true);
    setUploadError("");
    setUploadFeedback("");
    try {
      await onUpload(uploadExamId, file);
      setUploadFeedback("Upload processed. Refreshing results...");
      fileInputRef.current.value = "";
    } catch (actionError) {
      setUploadError(actionError.message || "Upload failed.");
    } finally {
      setUploadBusy(false);
    }
  };

  const requestDeleteResult = (row) => {
    const attemptId = row.attempt_id || row.id;
    if (!attemptId) {
      setDeleteError("This result does not have a CBT attempt ID.");
      return;
    }
    setDeleteError("");
    setDeleteFeedback("");
    setPendingDeleteResult(row);
  };

  const confirmDeleteResult = async () => {
    const row = pendingDeleteResult;
    if (!row) return;
    const attemptId = row.attempt_id || row.id;
    const studentName = row.student_name || "this student";
    const examTitle = row.exam_title || row.exam || "this exam";
    setDeleteBusyId(String(attemptId));
    setDeleteError("");
    setDeleteFeedback("");
    try {
      const result = await onDeleteResult?.(attemptId);
      setDeleteFeedback(result?.message || "Result deleted. The student can retake the exam.");
      setPendingDeleteResult(null);
    } catch (actionError) {
      setDeleteError(actionError.message || "Could not delete result.");
    } finally {
      setDeleteBusyId("");
    }
  };

  const renderScoreBlock = (row) => {
    const rawScore = row.score ?? row.obtained;
    const scoreValue = typeof rawScore === "number" ? rawScore : rawScore || "-";
    const questionCount = row.question_count || row.questions || null;
    return (
      <div className="score-cell">
        <strong>{scoreValue}</strong>
        {questionCount ? <small>{questionCount} questions</small> : null}
      </div>
    );
  };

  const renderSubjectBreakdown = (value) => {
    if (!value) {
      return "-";
    }
    if (Array.isArray(value)) {
      return value.join(", ");
    }
    if (typeof value === "object") {
      return Object.entries(value)
        .map(([key, val]) => `${key}: ${val}`)
        .join("; ");
    }
    return value;
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Exam Results</h2>
        <p>Set CBT exams, publish them, and review student submissions for exams you own or shared CBT bank exams.</p>
      </div>

      <ScreenState loading={loading && !results.length} error={error} onRetry={onRetry} />

      <div className="table-actions-inline">
        <button type="button" className={`table-action ${activeView === "desktop" ? "active" : ""}`} onClick={() => setActiveView("desktop")}>
          CBT Desktop
        </button>
        <button type="button" className={`table-action ${activeView === "builder" ? "active" : ""}`} onClick={() => setActiveView("builder")}>
          Set Exam
        </button>
        <button type="button" className={`table-action ${activeView === "results" ? "active" : ""}`} onClick={() => setActiveView("results")}>
          View Results
        </button>
        <button type="button" className={`table-action ${activeView === "auto-submissions" ? "active" : ""}`} onClick={() => setActiveView("auto-submissions")}>
          Auto Submissions
        </button>
      </div>

      {activeView === "desktop" ? <SchoolDomCbtDesktop exams={exams} results={results} downloads={data?.downloads || {}} school={broadsheetSchool} session={session} /> : null}

      {activeView === "builder" ? (
        <>
          <TeacherExamBuilder
            session={session}
            classOptions={classOptions}
            subjectOptions={subjectOptions}
            teacherName={userDisplayName(session?.user) || "Admin"}
            initialExam={editingExam}
            onCreateExam={onCreateExam}
            onUpdateExam={onUpdateExam}
            onBackToList={() => {
              setEditingExam(null);
              setActiveView("results");
            }}
          />
          <article className="app-panel">
            <div className="panel-head">
              <h3>Admin CBT exams</h3>
              <small>Open an exam to publish it or update questions.</small>
            </div>
            {editError ? <p className="form-feedback error">{editError}</p> : null}
            {pinError ? <p className="form-feedback error">{pinError}</p> : null}
            {pinFeedback ? <p className="form-feedback success">{pinFeedback}</p> : null}
            {deleteExamError ? <p className="form-feedback error">{deleteExamError}</p> : null}
            {deleteExamFeedback ? <p className="form-feedback success">{deleteExamFeedback}</p> : null}
            {exams.length ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Exam</th>
                    <th>Class</th>
                    <th>Questions</th>
                    <th>Status</th>
                    <th>PIN</th>
                    <th>Submissions</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {exams.map((exam) => (
                    <tr key={exam.id || exam.exam_id}>
                      <td>{exam.title || exam.name || `Exam ${exam.id || exam.exam_id}`}</td>
                      <td>{exam.class_name || exam.class || "All classes"}</td>
                      <td>{exam.question_count ?? "-"}</td>
                      <td>{exam.is_published ? "Published" : "Draft"}</td>
                      <td>{renderExamPinCell(exam)}</td>
                      <td>{exam.submissions ?? 0}</td>
                      <td>
                        <button
                          type="button"
                          className="table-action"
                          disabled={String(loadingExamId) === String(exam.id || exam.exam_id)}
                          onClick={() => handleEditExam(exam.id || exam.exam_id)}
                        >
                          {String(loadingExamId) === String(exam.id || exam.exam_id) ? "Opening..." : "Open"}
                        </button>
                        <button
                          type="button"
                          className="table-action danger"
                          disabled={deleteExamBusyId === String(exam.id || exam.exam_id)}
                          onClick={() => handleDeleteExam(exam)}
                        >
                          {deleteExamBusyId === String(exam.id || exam.exam_id) ? "Deleting..." : "Delete"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="panel-empty">No admin CBT exams yet.</p>
            )}
          </article>
        </>
      ) : null}

      {activeView === "results" && Boolean(results.length) ? (
        <div className="metric-grid">
          <MetricCard
            label="Results Uploaded"
            value={results.length}
            trend="Rows currently available"
          />
          <MetricCard
            label="Average Score"
            value={averageScore !== null ? `${averageScore}%` : "-"}
            trend={averageScore !== null ? "Across all students" : "No scores yet"}
          />
          <MetricCard
            label="Top Score"
            value={topScore !== null ? `${topScore}%` : "-"}
            trend="Highest recent result"
          />
        </div>
      ) : null}

      {activeView === "results" ? <article className="app-panel">
        <div className="panel-head">
          <h3>Download result broadsheet</h3>
          <small>Select an exam or class, add the broadsheet type, then open or download an Excel-friendly sheet.</small>
        </div>
        <div className="panel-form">
          <div className="panel-form-grid">
            <label className="panel-field">
              Exam
              {exams.length > 0 ? (
                <select value={broadsheetExamId} onChange={(event) => setBroadsheetExamId(event.target.value)}>
                  <option value="all">All exams</option>
                  {exams.map((exam) => (
                    <option key={exam.id || exam.exam_id} value={exam.id || exam.exam_id}>
                      {exam.title || exam.name || `Exam ${exam.id || exam.exam_id}`}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={broadsheetExamId}
                  onChange={(event) => setBroadsheetExamId(event.target.value)}
                  placeholder="Enter exam ID or use all"
                />
              )}
            </label>
            <label className="panel-field">
              Class
              <select value={broadsheetClassName} onChange={(event) => setBroadsheetClassName(event.target.value)}>
                <option value="all">All classes</option>
                {uniqueClasses.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="panel-field full">
              Broadsheet type / nature
              <input
                value={broadsheetType}
                onChange={(event) => setBroadsheetType(event.target.value)}
                placeholder="e.g. 1st Term Exam Broadsheet, Mock Exam, Entrance Exam"
              />
            </label>
          </div>
          {uploadError ? <p className="form-feedback error">{uploadError}</p> : null}
          <p className="field-note">
            {broadsheetData.rows.length} student{broadsheetData.rows.length === 1 ? "" : "s"} and {broadsheetData.subjects.length} subject column{broadsheetData.subjects.length === 1 ? "" : "s"} will be included.
          </p>
          <div className="panel-form-actions">
            <button type="button" onClick={openBroadsheet}>
              Open broadsheet
            </button>
            <button type="button" onClick={downloadBroadsheetCsv}>
              Download result
            </button>
          </div>
        </div>
      </article> : null}

      {activeView === "results" ? <article className="app-panel">
        <div className="results-toolbar">
          <div className="results-filters">
            <input
              className="toolbar-input"
              type="search"
              value={search}
              placeholder="Search by student, reg no, or exam"
              onChange={(event) => setSearch(event.target.value)}
            />
            <select
              className="toolbar-select"
              value={classFilter}
              onChange={(event) => setClassFilter(event.target.value.toLowerCase())}
            >
              <option value="all">All classes</option>
              {uniqueClasses.map((item) => (
                <option key={item} value={item.toString().toLowerCase()}>
                  {item}
                </option>
              ))}
            </select>
            <select
              className="toolbar-select"
              value={subjectFilter}
              onChange={(event) => setSubjectFilter(event.target.value.toLowerCase())}
            >
              <option value="all">All subjects</option>
              {uniqueSubjects.map((item) => (
                <option key={item} value={item.toString().toLowerCase()}>
                  {item}
                </option>
              ))}
            </select>
            <select
              className="toolbar-select"
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value)}
            >
              <option value="score">Sort by score</option>
              <option value="name">Sort by name</option>
              <option value="time">Sort by time</option>
            </select>
          </div>
          <div className="results-meta">
            <span className="pill">{filteredResults.length} shown</span>
            {results.length ? <span className="pill muted">{results.length} total</span> : null}
          </div>
        </div>
        {deleteError ? <p className="form-feedback error">{deleteError}</p> : null}
        {deleteFeedback ? <p className="form-feedback success">{deleteFeedback}</p> : null}

        {filteredResults.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Reg No</th>
                <th>Exam</th>
                <th>Class</th>
                <th>Score</th>
                <th>Total Time</th>
                <th>Subjects</th>
                <th>Breakdown</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((row, index) => {
                const subjectList = Array.isArray(row.subjects) ? row.subjects.join(", ") : row.subject || row.subjects || "-";
                const examTitle = row.exam_title || row.exam || row.title || `Exam ${index + 1}`;
                return (
                  <tr key={row.id || row.attempt_id || row.reg_no || index}>
                    <td>
                      <div className="stacked">
                        <strong>{row.student_name || "Student"}</strong>
                        <small>{row.batch_no ? `Batch ${row.batch_no}` : ""}</small>
                      </div>
                    </td>
                    <td>{row.reg_no || row.registration_no || "-"}</td>
                    <td>{examTitle}</td>
                    <td>{row.class_name || row.class || "-"}</td>
                    <td>{renderScoreBlock(row)}</td>
                    <td>{row.total_time || row.duration || "-"}</td>
                    <td>{subjectList}</td>
                    <td>{renderSubjectBreakdown(row.score_by_subject || row.correct_attempt_by_subject || row.attempt_by_subject)}</td>
                    <td>
                      <button
                        type="button"
                        className="table-action danger"
                        onClick={() => requestDeleteResult(row)}
                        disabled={deleteBusyId === String(row.attempt_id || row.id)}
                      >
                        {deleteBusyId === String(row.attempt_id || row.id) ? "Deleting..." : "Delete"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="panel-empty">{loading ? "Loading results..." : "No results match your filters."}</p>
        )}
      </article> : null}

      {pendingDeleteResult ? (
        <div className="result-delete-modal" role="dialog" aria-modal="true" aria-labelledby="result-delete-title">
          <div className="result-delete-card">
            <div className="result-delete-icon" aria-hidden="true">
              <DashboardIcon name="exam" className="inline-icon" />
            </div>
            <p className="result-delete-kicker">Delete CBT result</p>
            <h3 id="result-delete-title">
              Delete {pendingDeleteResult.student_name || "this student's"} result?
            </h3>
            <p>
              This will remove the result for <strong>{pendingDeleteResult.exam_title || pendingDeleteResult.exam || "this exam"}</strong>.
              The student will be able to retake the exam.
            </p>
            {deleteError ? <p className="form-feedback error">{deleteError}</p> : null}
            <div className="result-delete-actions">
              <button
                type="button"
                className="table-action"
                onClick={() => setPendingDeleteResult(null)}
                disabled={deleteBusyId === String(pendingDeleteResult.attempt_id || pendingDeleteResult.id)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="table-action danger"
                onClick={confirmDeleteResult}
                disabled={deleteBusyId === String(pendingDeleteResult.attempt_id || pendingDeleteResult.id)}
              >
                {deleteBusyId === String(pendingDeleteResult.attempt_id || pendingDeleteResult.id) ? "Deleting..." : "Delete result"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {activeView === "auto-submissions" ? (
        <article className="app-panel">
          <div className="panel-head">
            <h3>Auto-submission monitoring</h3>
            <small>{autoSubmissions.length} recorded security or timer-triggered submission{autoSubmissions.length === 1 ? "" : "s"}</small>
          </div>
          {autoSubmissions.length ? (
            <div className="auto-submit-report-list">
              {autoSubmissions.map((item) => (
                <section key={item.attempt_id || item.id} className="auto-submit-report-card">
                  <div className="auto-submit-report-head">
                    <div>
                      <p className="quiz-kicker">{item.subject || "General"} - {item.class_name || "All classes"}</p>
                      <h4>{item.student_name || "Student"}: {item.exam_title || "Exam"}</h4>
                    </div>
                    <span className="pill danger">{item.reason || "Auto-submitted"}</span>
                  </div>
                  <div className="auto-submit-report-grid">
                    <div><span>Submitted</span><strong>{formatDate(item.submitted_at)}</strong></div>
                    <div><span>Warnings</span><strong>{item.warning_count ?? item.warning_history?.length ?? 0}</strong></div>
                    <div><span>Activity logs</span><strong>{item.activity_count ?? item.activity_logs?.length ?? 0}</strong></div>
                    <div><span>Student email</span><strong>{item.student_email || "-"}</strong></div>
                  </div>
                  {item.details ? <p className="field-note">{item.details}</p> : null}
                  <div className="auto-submit-log-columns">
                    <div>
                      <strong>Warning history</strong>
                      {(item.warning_history || []).length ? (
                        <ul>
                          {(item.warning_history || []).slice(0, 6).map((log, index) => (
                            <li key={`${item.attempt_id}-warning-${index}`}>
                              <span>{formatDate(log.time)}</span>
                              {log.message || log.reason || "-"}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="panel-empty compact">No warning history was recorded.</p>
                      )}
                    </div>
                    <div>
                      <strong>Activity logs</strong>
                      {(item.activity_logs || []).length ? (
                        <ul>
                          {(item.activity_logs || []).slice(0, 8).map((log, index) => (
                            <li key={`${item.attempt_id}-activity-${index}`}>
                              <span>{formatDate(log.time)}</span>
                              {log.message || log.type || "-"}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="panel-empty compact">No related activity logs were recorded.</p>
                      )}
                    </div>
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <p className="panel-empty">{loading ? "Loading auto-submission report..." : "No auto-submitted exams have been recorded."}</p>
          )}
        </article>
      ) : null}
      {confirmDialog}
    </section>
  );
}

function AdminResultsScreen({ data = {}, loading, error, onRetry, onSearch, onReviewBatch, onDeleteBatch, onSendSms }) {
  const summary = data?.summary || {};
  const leaderboard = data?.leaderboard || [];
  const batches = data?.result_batches || [];
  const [studentId, setStudentId] = useState("");
  const [report, setReport] = useState(data?.report_card || null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [searchError, setSearchError] = useState("");
  const [showSmsModal, setShowSmsModal] = useState(false);
  const [confirm, confirmDialog] = useConfirm();
  const [smsPhone, setSmsPhone] = useState("");
  const [smsBusy, setSmsBusy] = useState(false);
  const [smsFeedback, setSmsFeedback] = useState("");
  const [smsError, setSmsError] = useState("");

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!onSearch) return;
    const trimmed = studentId.trim();
    if (!trimmed) {
      setSearchError("Enter a student ID to search.");
      return;
    }
    setBusy(true);
    setSearchError("");
    setFeedback("");
    setReport(null);
    try {
      const result = await onSearch(trimmed);
      const card = result?.report_card || result?.report || result?.reportCard || null;
      setReport(card);
      if (card) {
        setSmsPhone(card.student?.guardian_phone || "");
        setFeedback("Report card generated.");
      }
    } catch (actionError) {
      setSearchError(actionError.message || "Could not fetch report card.");
    } finally {
      setBusy(false);
    }
  };

  const handlePrintReport = () => {
    window.print();
  };

  const handleOpenSms = () => {
    setSmsPhone(report?.student?.guardian_phone || "");
    setSmsError("");
    setSmsFeedback("");
    setShowSmsModal(true);
  };

  const handleSendSms = async (event) => {
    event.preventDefault();
    // Split on commas/semicolons and strip internal spaces so "0801 234 5678" stays one number
    const phones = smsPhone.split(/[,;]+/).map((p) => p.replace(/\s+/g, "").trim()).filter(Boolean);
    if (!phones.length) {
      setSmsError("Enter at least one phone number.");
      return;
    }
    setSmsBusy(true);
    setSmsError("");
    setSmsFeedback("");
    try {
      const result = await onSendSms?.({ phones, report });
      setSmsFeedback(result?.message || "SMS sent successfully.");
    } catch (err) {
      setSmsError(err.message || "Could not send SMS.");
    } finally {
      setSmsBusy(false);
    }
  };

  const handleDeleteBatch = async (batch) => {
    const ok = await confirm({ title: "Delete Results Batch", message: `Delete "${batch.title}" and all ${batch.score_count || 0} score record(s)?`, confirmLabel: "Delete", danger: true });
    if (!ok) {
      return;
    }
    setBusy(true);
    setSearchError("");
    setFeedback("");
    try {
      const result = await onDeleteBatch?.(batch.id);
      setFeedback(result?.message || "Result batch deleted.");
    } catch (actionError) {
      setSearchError(actionError.message || "Could not delete result batch.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Results &amp; Report Cards</h2>
        <p>Search by student ID, view subject scores, and export report details.</p>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <div className="metric-grid">
        <MetricCard label="Result Records" value={summary.total_records ?? 0} trend="Stored subject scores" />
        <MetricCard
          label="Students with Scores"
          value={summary.students_with_scores ?? 0}
          trend="Unique students graded"
        />
        <MetricCard label="Pending Review" value={summary.pending_batches ?? 0} trend="Teacher pushes awaiting admin" />
      </div>

      <article className="app-panel">
        <div className="panel-head"><h3>Result approval queue</h3><small>Review teacher submissions before publishing live.</small></div>
        {batches.length ? (
          <table className="data-table">
            <thead><tr><th>Batch</th><th>Class</th><th>Teacher</th><th>Scores</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {batches.map((batch) => (
                <tr key={batch.id}>
                  <td>{batch.title}<br /><small>{formatDate(batch.submitted_at)}</small></td>
                  <td>{batch.class_name}</td>
                  <td>{batch.teacher || "-"}</td>
                  <td>{batch.score_count}</td>
                  <td>{batch.status}</td>
                  <td>
                    <button type="button" className="table-action" onClick={() => onReviewBatch?.(batch.id, "approved")}>Approve</button>
                    <button type="button" className="table-action" onClick={() => onReviewBatch?.(batch.id, "published")}>Publish live</button>
                    <button type="button" className="table-action danger" onClick={() => onReviewBatch?.(batch.id, "rejected")}>Reject</button>
                    <button type="button" className="table-action danger" onClick={() => handleDeleteBatch(batch)} disabled={busy}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="panel-empty">No pushed result batches yet.</p>}
      </article>

      <article className="app-panel">
        <form className="panel-form" onSubmit={handleSearch}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Student ID
              <input
                value={studentId}
                onChange={(event) => setStudentId(event.target.value)}
                placeholder="e.g. STU2026-001"
              />
            </label>
          </div>
          {searchError ? <p className="form-feedback error">{searchError}</p> : null}
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={busy}>
              {busy ? "Searching..." : "Generate report"}
            </button>
          </div>
        </form>
      </article>

      {report ? (
        <article className="app-panel report-card" id="report-card-printable">
          <div className="report-card-topbar no-print">
            <div className="report-school-brand">
              <SchoolBrand school={report.school} subtitle="Official report card" compact />
            </div>
            <div className="report-card-actions">
              <button type="button" className="btn-secondary report-action-btn" onClick={handleOpenSms}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                Send Report Card
              </button>
              <button type="button" className="btn-primary report-action-btn" onClick={handlePrintReport}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                Print Report
              </button>
            </div>
          </div>
          {(() => {
            const brand = resolveSchoolBrand(report.school);
            const student = report.student || {};
            const scores = report.scores || [];
            const termLabel = scores.find((row) => row.term)?.term || "";
            const gradeScales = data?.grade_scales || [];
            const gradeTone = (letter) => {
              const first = (letter || "").trim().charAt(0).toUpperCase();
              if (first === "A") return "excellent";
              if (first === "B") return "good";
              if (first === "C") return "average";
              if (first === "D") return "weak";
              return "poor";
            };
            return (
              <div className="report-sheet">
                <div className="report-sheet-inner">
                  <header className="report-letterhead">
                    <div className="report-letterhead-logo">
                      {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
                    </div>
                    <div className="report-letterhead-text">
                      <h1>{brand.name}</h1>
                      {brand.address ? <p className="report-letterhead-line">{brand.address}</p> : null}
                      {(brand.phone || brand.email) ? (
                        <p className="report-letterhead-line">
                          {[brand.phone, brand.email].filter(Boolean).join("  ·  ")}
                        </p>
                      ) : null}
                      {brand.motto ? <p className="report-letterhead-motto">&ldquo;{brand.motto}&rdquo;</p> : null}
                    </div>
                    <div className="report-letterhead-seal">
                      <div className="report-seal-ring">
                        <span>Academic<br />Report</span>
                      </div>
                    </div>
                  </header>

                  <div className="report-title-bar">
                    <span>Student Academic Report</span>
                    <span>{termLabel || "Current Term"}</span>
                  </div>

                  <section className="report-student-block">
                    <div className="report-student-photo">
                      {student.profile_picture ? (
                        <img src={student.profile_picture} alt={student.name || "Student"} />
                      ) : (
                        <span>{(student.name || "Student").slice(0, 2).toUpperCase()}</span>
                      )}
                    </div>
                    <dl className="report-student-info">
                      <div><dt>Name</dt><dd>{student.name || "-"}</dd></div>
                      <div><dt>Student ID</dt><dd>{student.student_id || "-"}</dd></div>
                      <div><dt>Class</dt><dd>{student.class_name || "-"}</dd></div>
                      <div><dt>Gender</dt><dd>{student.gender || "-"}</dd></div>
                      <div><dt>Term</dt><dd>{termLabel || "-"}</dd></div>
                      <div><dt>Position</dt><dd>{report.class_position ? `${report.class_position} of ${report.class_size}` : "N/A"}</dd></div>
                    </dl>
                  </section>

                  <div className="report-table-scroll">
                    <table className="report-subject-table">
                      <thead>
                        <tr>
                          <th>S/N</th>
                          <th>Subject</th>
                          <th>Score</th>
                          <th>Max</th>
                          <th>%</th>
                          <th>Grade</th>
                          <th>Teacher</th>
                          <th>Remark</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scores.length ? (
                          scores.map((row, index) => (
                            <tr key={row.id}>
                              <td>{index + 1}</td>
                              <td className="report-subject-name">{row.subject}</td>
                              <td>{row.score}</td>
                              <td>{row.max_score}</td>
                              <td>{row.percentage != null ? `${row.percentage}%` : "-"}</td>
                              <td>
                                <span className={`report-grade-badge tone-${gradeTone(row.grade)}`}>{row.grade || "-"}</span>
                              </td>
                              <td>{row.teacher || "-"}</td>
                              <td>{row.performance_remark || "-"}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="8">No subject scores found.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="report-summary-strip">
                    <div><span>Grand Total</span><strong>{report.total_score ?? 0}</strong></div>
                    <div><span>Average</span><strong>{report.average_score ?? 0}%</strong></div>
                    <div><span>Subjects</span><strong>{scores.length}</strong></div>
                    <div><span>Class Position</span><strong>{report.class_position ? `${report.class_position} / ${report.class_size}` : "N/A"}</strong></div>
                  </div>

                  <div className="report-key-remarks-grid">
                    <div className="report-grade-key">
                      <h4>Grading Key</h4>
                      {gradeScales.length ? (
                        <table>
                          <tbody>
                            {gradeScales.map((scale) => (
                              <tr key={scale.letter}>
                                <td><span className={`report-grade-badge tone-${gradeTone(scale.letter)}`}>{scale.letter}</span></td>
                                <td>{scale.min_percentage}&ndash;{scale.max_percentage}%</td>
                                <td>{scale.remark || ""}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p className="report-grade-key-empty">No grading scale configured.</p>
                      )}
                    </div>
                    <div className="report-signature-block">
                      <div className="report-signature-line"><span>Class Teacher&apos;s Signature</span></div>
                      <div className="report-signature-line"><span>Head Teacher&apos;s Signature</span></div>
                      <div className="report-date-line"><span>Date Issued: {formatDate(new Date())}</span></div>
                    </div>
                  </div>

                  <footer className="report-sheet-footer">
                    {brand.motto || `${brand.name} · Excellence in Education`}
                  </footer>
                </div>
              </div>
            );
          })()}
        </article>
      ) : null}

      {showSmsModal && report ? (
        <>
          <div className="modal-overlay-bg" onClick={() => setShowSmsModal(false)} />
          <article className="edit-modal-card">
            <div className="edit-modal-head">
              <div>
                <h3>Send Result via SMS</h3>
                <p>Send a link to {report.student?.name}&apos;s report card to their parent/guardian.</p>
              </div>
              <button type="button" className="edit-modal-close" onClick={() => setShowSmsModal(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div style={{ padding: "1rem 1.5rem 1.5rem" }}>
              <form onSubmit={handleSendSms}>
                <div className="panel-form-grid">
                  <label className="panel-field full">
                    Parent / Guardian phone number
                    <input
                      value={smsPhone}
                      onChange={(e) => setSmsPhone(e.target.value)}
                      placeholder="e.g. 08012345678"
                    />
                    <small className="field-note">Pre-filled from student record. SMS will be sent via Sendchamp.</small>
                  </label>
                  <div className="panel-field full">
                    <p style={{ margin: 0, fontSize: "0.83rem", color: "#64748b" }}>
                      <strong>Message preview:</strong> The SMS will contain the school name, student name, scores summary and a link to the full report card.
                    </p>
                  </div>
                </div>
                {smsError ? <p className="form-feedback error">{smsError}</p> : null}
                {smsFeedback ? <p className="form-feedback success">{smsFeedback}</p> : null}
                <div className="panel-form-actions">
                  <button type="button" className="btn-secondary" onClick={() => setShowSmsModal(false)}>Cancel</button>
                  <button type="submit" disabled={smsBusy}>{smsBusy ? "Sending..." : "Send SMS"}</button>
                </div>
              </form>
            </div>
          </article>
        </>
      ) : null}

      <article className="app-panel">
        <div className="panel-head">
          <h3>Class Rankings</h3>
          <small>Highest totals listed first.</small>
        </div>
        {leaderboard.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Student</th>
                <th>Class</th>
                <th>Total</th>
                <th>Average</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((row) => (
                <tr key={row.student_id}>
                  <td>#{row.rank}</td>
                  <td>{row.student_name}</td>
                  <td>{row.class_name || "Class"}</td>
                  <td>{row.total_score}</td>
                  <td>{row.average_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="panel-empty">No rankings available yet.</p>
        )}
      </article>
      {confirmDialog}
    </section>
  );
}

function AdminTableScreen({ title, description, loading, error, onRetry, columns, rows }) {
  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <ScreenState loading={loading && !rows} error={error} onRetry={onRetry} />

          <article className="app-panel">
            {rows && rows.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.id || row.user_id || row.email || `${title}-${index}`}>
                  {columns.map((column) => (
                    <td key={column.key}>
                      {typeof column.render === "function" ? column.render(row) : row[column.key] ?? "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="panel-empty">No records found.</p>
        )}
      </article>
    </section>
  );
}

const TIMETABLE_DAY_FALLBACK = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
];

function AdminTimetablesScreen({ data = {}, loading, error, onRetry, onCreate, onUpdate, onDelete }) {
  const entries = data?.entries || [];
  const classes = data?.classes || [];
  const subjects = data?.subjects || [];
  const teachers = data?.teachers || [];
  const days = data?.days?.length ? data.days : TIMETABLE_DAY_FALLBACK;

  const [filterClassId, setFilterClassId] = useState("");
  const [form, setForm] = useState({
    class_id: "", subject_id: "", title: "", teacher_id: "", day_of_week: "0",
    start_time: "", end_time: "", room: "",
  });
  const [editingEntry, setEditingEntry] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [confirm, confirmDialog] = useConfirm();

  const dayLabel = (value) => days.find((item) => String(item.value) === String(value))?.label || "-";

  const filteredEntries = useMemo(() => {
    const list = filterClassId ? entries.filter((item) => String(item.class_id) === String(filterClassId)) : entries;
    return [...list].sort((a, b) => {
      if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
      return String(a.start_time).localeCompare(String(b.start_time));
    });
  }, [entries, filterClassId]);

  const resetForm = () => {
    setForm({ class_id: "", subject_id: "", title: "", teacher_id: "", day_of_week: "0", start_time: "", end_time: "", room: "" });
    setEditingEntry(null);
  };

  const handleEdit = (entry) => {
    setEditingEntry(entry);
    setForm({
      class_id: String(entry.class_id || ""),
      subject_id: String(entry.subject_id || ""),
      title: entry.title || "",
      teacher_id: entry.teacher_id || "",
      day_of_week: String(entry.day_of_week),
      start_time: entry.start_time || "",
      end_time: entry.end_time || "",
      room: entry.room || "",
    });
    setFormError("");
    setFormSuccess("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.class_id) {
      setFormError("Select a class.");
      return;
    }
    if (!form.subject_id && !form.title.trim()) {
      setFormError("Select a subject or enter a title (e.g. Break, Assembly) for this slot.");
      return;
    }
    if (!form.start_time || !form.end_time) {
      setFormError("Enter a start and end time.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        class_id: form.class_id,
        subject_id: form.subject_id || null,
        title: form.title.trim(),
        teacher_id: form.teacher_id || null,
        day_of_week: Number(form.day_of_week),
        start_time: form.start_time,
        end_time: form.end_time,
        room: form.room.trim(),
      };
      const result = editingEntry ? await onUpdate?.(editingEntry.id, payload) : await onCreate?.(payload);
      setFormSuccess(result?.message || "Saved.");
      resetForm();
    } catch (actionError) {
      setFormError(actionError.message || "Could not save timetable entry.");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (entry) => {
    const ok = await confirm({
      title: "Remove Timetable Entry",
      message: `Remove ${entry.display_label || entry.subject_name} for ${entry.class_name} on ${dayLabel(entry.day_of_week)}?`,
      confirmLabel: "Remove",
      danger: true,
    });
    if (!ok) return;
    setFormError("");
    try {
      const result = await onDelete?.(entry.id);
      setFormSuccess(result?.message || "Timetable entry removed.");
    } catch (actionError) {
      setFormError(actionError.message || "Could not remove timetable entry.");
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Timetables</h2>
        <p>Build and manage each class's weekly timetable. Teachers and students automatically see their relevant schedule.</p>
      </div>

      <ScreenState loading={loading && !entries.length} error={error} onRetry={onRetry} />

      <article className="app-panel">
        <div className="panel-head">
          <h3>{editingEntry ? "Edit Timetable Entry" : "Add Timetable Entry"}</h3>
          <small>Assign a subject and teacher to a class for a specific day and time.</small>
        </div>
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Class
              <select value={form.class_id} onChange={(event) => setForm((current) => ({ ...current, class_id: event.target.value }))} disabled={busy}>
                <option value="">Select class</option>
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>{item.label || item.name}</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Subject (optional)
              <select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value }))} disabled={busy}>
                <option value="">No subject</option>
                {subjects.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Title
              <input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="e.g. Break, Assembly, Lunch" disabled={busy} />
              <span className="field-note">Used for breaks or non-subject slots. Falls back to the subject name if left blank.</span>
            </label>
            <label className="panel-field">
              Teacher
              <select value={form.teacher_id} onChange={(event) => setForm((current) => ({ ...current, teacher_id: event.target.value }))} disabled={busy}>
                <option value="">Unassigned</option>
                {teachers.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Day
              <select value={form.day_of_week} onChange={(event) => setForm((current) => ({ ...current, day_of_week: event.target.value }))} disabled={busy}>
                {days.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Start Time
              <input type="time" value={form.start_time} onChange={(event) => setForm((current) => ({ ...current, start_time: event.target.value }))} disabled={busy} />
            </label>
            <label className="panel-field">
              End Time
              <input type="time" value={form.end_time} onChange={(event) => setForm((current) => ({ ...current, end_time: event.target.value }))} disabled={busy} />
            </label>
            <label className="panel-field">
              Room (optional)
              <input value={form.room} onChange={(event) => setForm((current) => ({ ...current, room: event.target.value }))} placeholder="e.g. Block A, Room 3" disabled={busy} />
            </label>
          </div>
          {formError ? <p className="form-feedback error">{formError}</p> : null}
          {formSuccess ? <p className="form-feedback success">{formSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={busy}>{busy ? "Saving..." : editingEntry ? "Update Entry" : "Add Entry"}</button>
            {editingEntry ? (
              <button type="button" className="table-action" onClick={resetForm} disabled={busy}>Cancel</button>
            ) : null}
          </div>
        </form>
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Weekly Schedule</h3>
          <label className="panel-field">
            Filter by class
            <select value={filterClassId} onChange={(event) => setFilterClassId(event.target.value)}>
              <option value="">All Classes</option>
              {classes.map((item) => (
                <option key={item.id} value={item.id}>{item.label || item.name}</option>
              ))}
            </select>
          </label>
        </div>
        <TimetableGridTable
          entries={filteredEntries}
          days={days}
          emptyMessage="No timetable entries yet. Add one above to get started."
          renderCell={(entry) => (
            <div className="timetable-grid-entry-body">
              <strong>{entry.display_label || entry.subject_name}</strong>
              {!filterClassId ? <span>{entry.class_name}</span> : null}
              <span>{entry.teacher_name || "Unassigned"}</span>
              {entry.room ? <span className="timetable-grid-room">{entry.room}</span> : null}
              <div className="timetable-grid-entry-actions">
                <button type="button" onClick={() => handleEdit(entry)}>Edit</button>
                <button type="button" onClick={() => handleDelete(entry)}>Remove</button>
              </div>
            </div>
          )}
        />
      </article>

      {confirmDialog}
    </section>
  );
}

function AdminClassesScreen({ data, school, loading, error, onRetry, onCreate, onUpdate, onDelete, onBulkPromotion, onCreateSubject, onDeleteSubject }) {
  const classes = data?.classes || [];
  const subjects = data?.subjects || [];
  const terms = data?.terms || [];
  const promotionHistory = data?.promotion_history || [];
  const groupLabels = academicGroupLabels(data?.school, school);
  const [name, setName] = useState("");
  const [section, setSection] = useState("");
  const [selectedSubjectIds, setSelectedSubjectIds] = useState([]);
  const [editingClass, setEditingClass] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [subjectBusy, setSubjectBusy] = useState(false);
  const [subjectStreamBusy, setSubjectStreamBusy] = useState("");
  const [subjectError, setSubjectError] = useState("");
  const [subjectSuccess, setSubjectSuccess] = useState("");
  const [promotionForm, setPromotionForm] = useState({
    scope: "class",
    source_class_id: "",
    source_department: "",
    source_level: "",
    source_term_id: "",
    target_class_id: "",
    target_term_id: "",
    note: "",
  });
  const [promotionPreview, setPromotionPreview] = useState(null);
  const [promotionBusy, setPromotionBusy] = useState(false);
  const [promotionError, setPromotionError] = useState("");
  const [promotionSuccess, setPromotionSuccess] = useState("");
  const [promotionConfirmed, setPromotionConfirmed] = useState(false);
  const [confirm, confirmDialog] = useConfirm();

  const departmentOptions = useMemo(
    () => Array.from(new Set(classes.map((item) => item.section).filter(Boolean))).sort(),
    [classes]
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!name.trim()) {
      setFormError(`${groupLabels.singular} name is required.`);
      return;
    }
    setBusy(true);
    try {
      const payload = { name: name.trim(), section: section.trim() || null, subject_ids: selectedSubjectIds };
      const result = editingClass ? await onUpdate?.(editingClass.id, payload) : await onCreate?.(payload);
      setFormSuccess(result?.message || "Saved.");
      setName("");
      setSection("");
      setSelectedSubjectIds([]);
      setEditingClass(null);
    } catch (actionError) {
      setFormError(actionError.message || `Could not save ${groupLabels.singular.toLowerCase()}.`);
    } finally {
      setBusy(false);
    }
  };

  const handleEditClass = (item) => {
    setFormError("");
    setFormSuccess("");
    setEditingClass(item);
    setName(item.name || "");
    setSection(item.section || "");
    setSelectedSubjectIds(
      Array.isArray(item.subjects)
        ? item.subjects.map((subject) => String(subject.id))
        : []
    );
  };

  const handleCancelEdit = () => {
    setEditingClass(null);
    setName("");
    setSection("");
    setSelectedSubjectIds([]);
    setFormError("");
    setFormSuccess("");
  };

  const handleDeleteClass = async (item) => {
    const ok = await confirm({
      title: `Delete ${groupLabels.singular}`,
      message: `Delete "${item.label || item.name}"? Students in this ${groupLabels.singular.toLowerCase()} will lose their class assignment. This cannot be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setFormError("");
    setFormSuccess("");
    try {
      await onDelete?.(item.id);
      setFormSuccess(`${groupLabels.singular} deleted.`);
    } catch (deleteError) {
      setFormError(deleteError.message || `Could not delete ${groupLabels.singular.toLowerCase()}.`);
    }
  };

  const handleSubjectSubmit = async (event) => {
    event.preventDefault();
    setSubjectError("");
    setSubjectSuccess("");
    if (!subjectName.trim()) {
      setSubjectError("Subject name is required.");
      return;
    }
    setSubjectBusy(true);
    try {
      const payload = { name: subjectName.trim(), code: subjectCode.trim() };
      const result = await onCreateSubject?.(payload);
      setSubjectSuccess(result?.message || "Subject saved.");
      setSubjectName("");
      setSubjectCode("");
    } catch (actionError) {
      setSubjectError(actionError.message || "Could not save subject.");
    } finally {
      setSubjectBusy(false);
    }
  };

  const handleSubjectDelete = async (subjectId) => {
    setSubjectError("");
    setSubjectSuccess("");
    try {
      await onDeleteSubject?.(subjectId);
      setSubjectSuccess("Subject removed.");
    } catch (actionError) {
      setSubjectError(actionError.message || "Could not delete subject.");
    }
  };

  const handleRecommendedSubject = (nameValue, codeValue) => {
    setSubjectName(nameValue);
    setSubjectCode(codeValue);
    setSubjectError("");
    setSubjectSuccess("");
  };

  const handleSelectAllRecommendedSubjects = async (group) => {
    setSubjectError("");
    setSubjectSuccess("");
    const existingNames = new Set(subjects.map((subject) => String(subject.name || "").trim().toLowerCase()).filter(Boolean));
    const existingCodes = new Set(subjects.map((subject) => String(subject.code || "").trim().toLowerCase()).filter(Boolean));
    const missingSubjects = group.subjects.filter(([subjectLabel, subjectShortCode]) => {
      const normalizedName = String(subjectLabel || "").trim().toLowerCase();
      const normalizedCode = String(subjectShortCode || "").trim().toLowerCase();
      return normalizedName && !existingNames.has(normalizedName) && !existingCodes.has(normalizedCode);
    });

    if (!missingSubjects.length) {
      setSubjectSuccess(`All ${group.stream} subjects are already available.`);
      return;
    }

    setSubjectStreamBusy(group.stream);
    try {
      for (const [subjectLabel, subjectShortCode] of missingSubjects) {
        await onCreateSubject?.({ name: subjectLabel, code: subjectShortCode });
      }
      setSubjectSuccess(`${missingSubjects.length} ${group.stream} subject${missingSubjects.length === 1 ? "" : "s"} added.`);
    } catch (actionError) {
      setSubjectError(actionError.message || `Could not add all ${group.stream} subjects.`);
    } finally {
      setSubjectStreamBusy("");
    }
  };

  const buildPromotionPayload = (action) => ({
    action,
    scope: promotionForm.scope,
    source_class_id: promotionForm.scope === "class" ? promotionForm.source_class_id : "",
    source_department: promotionForm.scope === "department" ? promotionForm.source_department.trim() : "",
    source_level: promotionForm.scope === "level" ? promotionForm.source_level.trim() : "",
    source_term_id: promotionForm.source_term_id,
    target_class_id: promotionForm.target_class_id,
    target_term_id: promotionForm.target_term_id,
    note: promotionForm.note.trim(),
    confirm: action === "apply" ? promotionConfirmed : false,
  });

  const handlePromotionPreview = async (event) => {
    event.preventDefault();
    setPromotionError("");
    setPromotionSuccess("");
    setPromotionPreview(null);
    setPromotionConfirmed(false);
    setPromotionBusy(true);
    try {
      const result = await onBulkPromotion?.(buildPromotionPayload("preview"));
      setPromotionPreview(result?.preview || null);
      setPromotionSuccess(result?.message || "Promotion preview ready.");
    } catch (actionError) {
      setPromotionError(actionError.message || "Could not preview promotion.");
    } finally {
      setPromotionBusy(false);
    }
  };

  const handlePromotionApply = async () => {
    setPromotionError("");
    setPromotionSuccess("");
    if (!promotionPreview?.summary?.eligible_students) {
      setPromotionError("Preview a promotion with eligible students first.");
      return;
    }
    if (!promotionConfirmed) {
      setPromotionError("Confirm the promotion before applying.");
      return;
    }
    const targetName = promotionPreview?.target_class?.label || "the destination class";
    const count = promotionPreview?.summary?.eligible_students || 0;
    const ok = await confirm({ title: "Apply Bulk Promotion", message: `Promote ${count} student(s) to ${targetName}? This will update their class assignment.`, confirmLabel: "Promote", danger: false });
    if (!ok) {
      return;
    }
    setPromotionBusy(true);
    try {
      const result = await onBulkPromotion?.(buildPromotionPayload("apply"));
      setPromotionSuccess(result?.message || "Promotion applied.");
      setPromotionPreview(result?.preview || null);
      setPromotionConfirmed(false);
    } catch (actionError) {
      setPromotionError(actionError.message || "Could not apply promotion.");
    } finally {
      setPromotionBusy(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>{groupLabels.plural}</h2>
        <p>Create or list academic groups.</p>
      </div>

      <ScreenState loading={loading && !classes.length} error={error} onRetry={onRetry} />

      {editingClass && <div className="modal-overlay-bg" onClick={handleCancelEdit} />}

      <article
        className={`app-panel ${editingClass ? "edit-modal-card" : ""}`}
        role={editingClass ? "dialog" : undefined}
        aria-modal={editingClass ? "true" : undefined}
        aria-labelledby={editingClass ? "edit-class-title" : undefined}
      >
        <div className="edit-modal-head">
          <div>
            <h3 id={editingClass ? "edit-class-title" : undefined}>{editingClass ? `Edit ${groupLabels.singular.toLowerCase()}` : `Create ${groupLabels.singular.toLowerCase()}`}</h3>
            <p>{editingClass ? `Updating ${editingClass.label || editingClass.name}.` : `Name is required; ${groupLabels.singular === "Class" ? "section" : "faculty"} is optional.`}</p>
          </div>
          {editingClass ? <button type="button" className="edit-modal-close" onClick={handleCancelEdit} disabled={busy} aria-label="Close"><X size={16} /></button> : null}
        </div>
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              {groupLabels.singular === "Class" ? "Name" : "Department"}
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder={groupLabels.singular === "Class" ? "e.g., Grade 10 or Science Dept" : "e.g., Computer Science"} />
            </label>
            <label className="panel-field">
              {groupLabels.singular === "Class" ? "Section / Department" : "Faculty"}
              <input value={section} onChange={(e) => setSection(e.target.value)} placeholder={groupLabels.singular === "Class" ? "e.g., Blue, Science" : "e.g., Faculty of Science"} />
            </label>
            <label className="panel-field full">
              Subjects
              <MultiSelectBox
                options={subjects}
                selected={selectedSubjectIds}
                onChange={setSelectedSubjectIds}
                labelForOption={(subject) => `${subject.name}${subject.code ? ` (${subject.code})` : ""}`}
                emptyText="Add subjects below before assigning them."
              />
              <small className="field-note">
                {subjects.length ? `Tick every subject that belongs to this ${groupLabels.singular.toLowerCase()}.` : "Add subjects below before assigning them."}
              </small>
            </label>
          </div>
          {formError ? <p className="form-feedback error">{formError}</p> : null}
          {formSuccess ? <p className="form-feedback success">{formSuccess}</p> : null}
          <div className="panel-form-actions">
            {editingClass ? (
              <button type="button" className="table-action" onClick={handleCancelEdit} disabled={busy}>
                Cancel
              </button>
            ) : null}
            <button type="submit" disabled={busy}>
              {busy ? "Saving..." : editingClass ? "Save changes" : "Create"}
            </button>
          </div>
        </form>
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Bulk {groupLabels.singular.toLowerCase()} promotion</h3>
          <small>Preview and promote or transfer students in one controlled batch.</small>
        </div>
        <form className="panel-form" onSubmit={handlePromotionPreview}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Promotion Scope
              <select
                value={promotionForm.scope}
                onChange={(event) => {
                  setPromotionForm((prev) => ({ ...prev, scope: event.target.value }));
                  setPromotionPreview(null);
                  setPromotionConfirmed(false);
                }}
              >
                <option value="class">{groupLabels.singular}</option>
                <option value="department">Department</option>
                <option value="level">Academic level</option>
                <option value="session">Academic session</option>
              </select>
            </label>
            {promotionForm.scope === "class" ? (
              <label className="panel-field">
                From {groupLabels.singular}
                <select value={promotionForm.source_class_id} onChange={(event) => setPromotionForm((prev) => ({ ...prev, source_class_id: event.target.value }))}>
                  <option value="">{groupLabels.select}</option>
                  {classes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </label>
            ) : null}
            {promotionForm.scope === "department" ? (
              <label className="panel-field">
                Department / Section
                <select value={promotionForm.source_department} onChange={(event) => setPromotionForm((prev) => ({ ...prev, source_department: event.target.value }))}>
                  <option value="">Select department</option>
                  {departmentOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
            ) : null}
            {promotionForm.scope === "level" ? (
              <label className="panel-field">
                Academic Level
                <input value={promotionForm.source_level} onChange={(event) => setPromotionForm((prev) => ({ ...prev, source_level: event.target.value }))} placeholder="e.g., Grade 9, JSS2, SSS1" />
              </label>
            ) : null}
            <label className="panel-field">
              Current Session / Term
              <select value={promotionForm.source_term_id} onChange={(event) => setPromotionForm((prev) => ({ ...prev, source_term_id: event.target.value }))}>
                <option value="">Active / any term</option>
                {terms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}
              </select>
            </label>
            <label className="panel-field">
              Promote / Transfer To
              <select value={promotionForm.target_class_id} onChange={(event) => setPromotionForm((prev) => ({ ...prev, target_class_id: event.target.value }))}>
                <option value="">Select destination</option>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="panel-field">
              New Session / Term
              <select value={promotionForm.target_term_id} onChange={(event) => setPromotionForm((prev) => ({ ...prev, target_term_id: event.target.value }))}>
                <option value="">Use active term</option>
                {terms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}
              </select>
            </label>
            <label className="panel-field full">
              Promotion Note
              <textarea value={promotionForm.note} onChange={(event) => setPromotionForm((prev) => ({ ...prev, note: event.target.value }))} placeholder="Optional batch note" />
            </label>
          </div>
          {promotionError ? <p className="form-feedback error">{promotionError}</p> : null}
          {promotionSuccess ? <p className="form-feedback success">{promotionSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={promotionBusy}>{promotionBusy ? "Checking..." : "Preview promotion"}</button>
          </div>
        </form>

        {promotionPreview ? (
          <div className="promotion-preview">
            <div className="metric-grid compact">
              <MetricCard label="Matched" value={promotionPreview.summary?.matched_students ?? 0} trend="Students found" />
              <MetricCard label="Eligible" value={promotionPreview.summary?.eligible_students ?? 0} trend="Ready to promote" />
              <MetricCard label="Blocked" value={promotionPreview.summary?.blocked_students ?? 0} trend="Needs review" />
              <MetricCard label="Duplicates" value={promotionPreview.summary?.duplicate_promotions ?? 0} trend="Already promoted" />
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>From</th>
                    <th>To</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(promotionPreview.students || []).slice(0, 12).map((student) => (
                    <tr key={student.id}>
                      <td>{student.name}<small>{student.student_id}</small></td>
                      <td>{student.from_class_name}</td>
                      <td>{student.to_class_name}</td>
                      <td><span className="finance-status status-paid">eligible</span></td>
                    </tr>
                  ))}
                  {(promotionPreview.blocked_students || []).slice(0, 8).map((student) => (
                    <tr key={`blocked-${student.id}`}>
                      <td>{student.name}<small>{student.student_id}</small></td>
                      <td>{student.from_class_name}</td>
                      <td>{student.to_class_name}</td>
                      <td><span className="finance-status status-pending">{student.reason}</span></td>
                    </tr>
                  ))}
                  {!(promotionPreview.students || []).length && !(promotionPreview.blocked_students || []).length ? (
                    <tr><td colSpan="4">No students matched this promotion.</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <label className="panel-field checkbox-field">
              <input type="checkbox" checked={promotionConfirmed} onChange={(event) => setPromotionConfirmed(event.target.checked)} />
              I confirm this bulk promotion is correct.
            </label>
            <div className="panel-form-actions">
              <button type="button" disabled={promotionBusy || !promotionConfirmed || !promotionPreview.summary?.eligible_students} onClick={handlePromotionApply}>
                {promotionBusy ? "Applying..." : "Apply promotion"}
              </button>
            </div>
          </div>
        ) : null}
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Existing {groupLabels.plural.toLowerCase()}</h3>
          <small>Total: {classes.length}</small>
        </div>
        {classes.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>{groupLabels.singular === "Class" ? "Section/Department" : "Faculty"}</th>
                <th>Subjects</th>
                <th>Students</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((item) => (
                <tr key={item.id || item.label}>
                  <td>{item.name || item.label}</td>
                  <td>{item.section || "-"}</td>
                  <td>
                    {Array.isArray(item.subjects) && item.subjects.length
                      ? item.subjects.map((subject) => subject.name).join(", ")
                      : "-"}
                  </td>
                  <td>{item.student_count ?? 0}</td>
                  <td>
                    <button className="table-action" type="button" onClick={() => handleEditClass(item)}>
                      Edit
                    </button>
                    <button className="table-action danger" type="button" onClick={() => handleDeleteClass(item)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="panel-empty">No {groupLabels.shortPlural.toLowerCase()} found.</p>
        )}
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Subjects</h3>
          <small>Add or remove subjects available to this school.</small>
        </div>
        <div className="subject-stream-list">
          {RECOMMENDED_SUBJECT_GROUPS.map((group) => (
            <section key={group.stream} className="subject-stream-card">
              <div className="subject-stream-head">
                <h4>{group.stream}</h4>
                <div>
                  <span>{group.subjects.length} common subjects</span>
                  <button
                    type="button"
                    className="subject-select-all"
                    onClick={() => handleSelectAllRecommendedSubjects(group)}
                    disabled={Boolean(subjectStreamBusy)}
                  >
                    {subjectStreamBusy === group.stream ? "Adding..." : "Select all"}
                  </button>
                </div>
              </div>
              <div className="subject-chip-grid">
                {group.subjects.map(([subjectLabel, subjectShortCode]) => (
                  <button
                    key={`${group.stream}-${subjectLabel}`}
                    type="button"
                    className="subject-suggestion-chip"
                    onClick={() => handleRecommendedSubject(subjectLabel, subjectShortCode)}
                  >
                    <span>{subjectLabel}</span>
                    <small>{subjectShortCode}</small>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
        <form className="panel-form" onSubmit={handleSubjectSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Name
              <input value={subjectName} onChange={(e) => setSubjectName(e.target.value)} placeholder="e.g., Physics" />
            </label>
            <label className="panel-field">
              Code
              <input value={subjectCode} onChange={(e) => setSubjectCode(e.target.value)} placeholder="e.g., PHY" />
            </label>
          </div>
          {subjectError ? <p className="form-feedback error">{subjectError}</p> : null}
          {subjectSuccess ? <p className="form-feedback success">{subjectSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={subjectBusy}>
              {subjectBusy ? "Saving..." : "Add subject"}
            </button>
          </div>
        </form>

        {subjects.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((subject) => (
                <tr key={subject.id}>
                  <td>{subject.name}</td>
                  <td>{subject.code}</td>
                  <td>
                    <button className="table-action danger" type="button" onClick={() => handleSubjectDelete(subject.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="panel-empty">No subjects yet.</p>
        )}
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Promotion history</h3>
          <small>{promotionHistory.length} latest movement(s)</small>
        </div>
        {promotionHistory.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Session</th>
                  <th>Batch</th>
                </tr>
              </thead>
              <tbody>
                {promotionHistory.map((item) => (
                  <tr key={item.id}>
                    <td>{item.student_name}<small>{item.student_code}</small></td>
                    <td>{item.from_class_name}</td>
                    <td>{item.to_class_name}</td>
                    <td>{item.to_term_name || item.to_academic_year_name || "-"}</td>
                    <td>{item.batch_reference}<small>{formatDate(item.created_at)}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="panel-empty">No class promotions recorded yet.</p>
        )}
      </article>
      {confirmDialog}
    </section>
  );
}

function ReadOnlyPersonProfile({ person, title = "Profile", onClose, codeLabel = "ID", codeValue = "" }) {
  if (!person) return null;
  const cvUrl = person.cv_url || person.cv || person.resume || "";
  const fields = [
    [codeLabel, codeValue || person.employee_id || person.staff_code],
    ["Email", person.email],
    ["Phone", person.phone],
    ["Gender", genderDisplay(person.gender)],
    ["Date of birth", person.date_of_birth ? formatDate(person.date_of_birth) : ""],
    ["Role", person.role || person.specialization],
    ["Department", person.department],
    ["Qualification", person.qualification],
    ["Employment type", person.employment_type],
    ["Monthly salary", person.monthly_salary !== undefined ? `${NAIRA_SYMBOL}${Number(person.monthly_salary || 0).toLocaleString()}` : ""],
    ["Hire date", person.hire_date ? formatDate(person.hire_date) : ""],
    ["Address", person.address],
    ["Next of kin", person.emergency_contact_name],
    ["Next of kin phone", person.emergency_contact_phone],
    ["Relationship", person.emergency_contact_relation],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");

  return (
    <article className="app-panel edit-modal-card record-detail-panel" role="dialog" aria-modal="true" aria-labelledby="readonly-profile-title">
      <div className="edit-modal-head">
        <div><h3 id="readonly-profile-title">{title}</h3><p>Read-only profile view</p></div>
        {onClose ? <button type="button" className="edit-modal-close" onClick={onClose} aria-label="Close"><X size={16} /></button> : null}
      </div>
      <div style={{padding:"0.75rem 1.5rem 1.5rem"}}>
        <dl className="record-detail-grid">
          <div>
            <dt>Name</dt>
            <dd>{person.name || `${person.first_name || ""} ${person.last_name || ""}`.trim() || "-"}</dd>
          </div>
          {fields.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value || "-"}</dd>
            </div>
          ))}
          <div>
            <dt>CV</dt>
            <dd>{cvUrl ? <a href={cvUrl} target="_blank" rel="noreferrer">Open CV</a> : "-"}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}

function AdminHRPayrollScreen({
  data,
  loading,
  error,
  onRetry,
  onMarkAttendance,
  onCreateLeave,
  onReviewLeave,
  onCreateAdvance,
  onReviewAdvance,
}) {
  const summary = data?.summary || {};
  const staff = data?.staff || [];
  const payroll = data?.payroll || [];
  const attendance = data?.attendance || [];
  const leaves = data?.leaves || [];
  const advances = data?.advances || [];
  const activity = data?.activity || [];
  const [attendanceForm, setAttendanceForm] = useState({ staff_id: "", qr_token: "", date: "", notes: "" });
  const [leaveForm, setLeaveForm] = useState({ staff_id: "", leave_type: "Annual", start_date: "", end_date: "", reason: "" });
  const [advanceForm, setAdvanceForm] = useState({ staff_id: "", amount: "", reason: "" });
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [activityExpanded, setActivityExpanded] = useState(false);

  const staffOptions = staff.map((item) => ({ id: item.id, label: `${item.name} (${item.staff_code})` }));
  const formatMoney = (value) => `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString()}`;
  const visibleActivity = activityExpanded ? activity : activity.slice(0, 3);

  const runAction = async (key, action, successMessage) => {
    setBusy(key);
    setFeedback("");
    setFormError("");
    try {
      const result = await action();
      setFeedback(result?.message || successMessage);
      return result;
    } catch (actionError) {
      setFormError(actionError.message || "Action failed.");
      return null;
    } finally {
      setBusy("");
    }
  };

  const handleAttendanceSubmit = async (event) => {
    event.preventDefault();
    const result = await runAction("attendance", () => onMarkAttendance(attendanceForm), "Attendance saved.");
    if (result) setAttendanceForm((prev) => ({ ...prev, qr_token: "", notes: "" }));
  };

  const handleLeaveSubmit = async (event) => {
    event.preventDefault();
    const result = await runAction("leave", () => onCreateLeave(leaveForm), "Leave request created.");
    if (result) setLeaveForm((prev) => ({ ...prev, start_date: "", end_date: "", reason: "" }));
  };

  const handleAdvanceSubmit = async (event) => {
    event.preventDefault();
    const result = await runAction("advance", () => onCreateAdvance(advanceForm), "Advance request created.");
    if (result) setAdvanceForm((prev) => ({ ...prev, amount: "", reason: "" }));
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>HR Management</h2>
        <p>Manage staff records, payroll, attendance, leave, and salary advances.</p>
      </div>

      <ScreenState loading={loading && !staff.length} error={error} onRetry={onRetry} />

      {(feedback || formError) ? (
        <article className="app-panel">
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {formError ? <p className="form-feedback error">{formError}</p> : null}
        </article>
      ) : null}

      <section className="panel-grid">
        <article className="app-panel">
          <div className="panel-head"><h3>QR attendance</h3><small>Use the same shared QR code used by teaching staff.</small></div>
          <form className="panel-form" onSubmit={handleAttendanceSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Staff<select value={attendanceForm.staff_id} onChange={(e) => setAttendanceForm((p) => ({ ...p, staff_id: e.target.value }))}><option value="">Select staff</option>{staffOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label className="panel-field full">Shared QR token or URL<input value={attendanceForm.qr_token} onChange={(e) => setAttendanceForm((p) => ({ ...p, qr_token: e.target.value.split("/").filter(Boolean).pop() || e.target.value }))} placeholder="Scan the shared staff QR code here" /></label>
              <label className="panel-field">Date<input type="date" value={attendanceForm.date} onChange={(e) => setAttendanceForm((p) => ({ ...p, date: e.target.value }))} /></label>
              <label className="panel-field">Notes<input value={attendanceForm.notes} onChange={(e) => setAttendanceForm((p) => ({ ...p, notes: e.target.value }))} /></label>
            </div>
            <div className="panel-form-actions"><button type="submit" disabled={busy === "attendance" || !attendanceForm.qr_token || !attendanceForm.staff_id}>Mark from shared QR</button></div>
          </form>
        </article>

      </section>

      <section className="panel-grid">
        <article className="app-panel">
          <div className="panel-head"><h3>Leave requests</h3><small>{summary.pending_leaves ?? 0} pending</small></div>
          <form className="panel-form" onSubmit={handleLeaveSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Staff<select value={leaveForm.staff_id} onChange={(e) => setLeaveForm((p) => ({ ...p, staff_id: e.target.value }))}><option value="">Select staff</option>{staffOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label className="panel-field">Type<input value={leaveForm.leave_type} onChange={(e) => setLeaveForm((p) => ({ ...p, leave_type: e.target.value }))} /></label>
              <label className="panel-field">Start<input type="date" value={leaveForm.start_date} onChange={(e) => setLeaveForm((p) => ({ ...p, start_date: e.target.value }))} /></label>
              <label className="panel-field">End<input type="date" value={leaveForm.end_date} onChange={(e) => setLeaveForm((p) => ({ ...p, end_date: e.target.value }))} /></label>
              <label className="panel-field full">Reason<input value={leaveForm.reason} onChange={(e) => setLeaveForm((p) => ({ ...p, reason: e.target.value }))} /></label>
            </div>
            <div className="panel-form-actions"><button type="submit" disabled={busy === "leave" || !leaveForm.staff_id}>Request leave</button></div>
          </form>
        </article>

        <article className="app-panel">
          <div className="panel-head"><h3>Salary advance</h3><small>{summary.pending_advances ?? 0} pending</small></div>
          <form className="panel-form" onSubmit={handleAdvanceSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">Staff<select value={advanceForm.staff_id} onChange={(e) => setAdvanceForm((p) => ({ ...p, staff_id: e.target.value }))}><option value="">Select staff</option>{staffOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label className="panel-field">Amount<input type="number" value={advanceForm.amount} onChange={(e) => setAdvanceForm((p) => ({ ...p, amount: e.target.value }))} /></label>
              <label className="panel-field full">Reason<input value={advanceForm.reason} onChange={(e) => setAdvanceForm((p) => ({ ...p, reason: e.target.value }))} /></label>
            </div>
            <div className="panel-form-actions"><button type="submit" disabled={busy === "advance" || !advanceForm.staff_id}>Request advance</button></div>
          </form>
        </article>
      </section>

      <section className="panel-grid">
        <RecordList title="Payroll history" rows={payroll.slice(0, 8)} render={(item) => `${item.staff_name} - ${item.period} - ${formatMoney(item.net_salary)} - ${item.status}`} />
        <RecordList title="Attendance history" rows={attendance.slice(0, 8)} render={(item) => `${item.staff_name} - ${item.date} - ${item.status}`} />
        <RecordList
          title="Leave history"
          rows={leaves.slice(0, 8)}
          render={(item) => (
            <span>
              {item.staff_name} - {item.leave_type} - {item.status}
              {item.status === "pending" ? (
                <>
                  {" "}
                  <button type="button" className="table-action" onClick={() => runAction("leave-review", () => onReviewLeave(item.id, "approved"), "Leave approved.")}>Approve</button>
                  <button type="button" className="table-action danger" onClick={() => runAction("leave-review", () => onReviewLeave(item.id, "rejected"), "Leave rejected.")}>Reject</button>
                </>
              ) : null}
            </span>
          )}
        />
        <RecordList
          title="Advance requests"
          rows={advances.slice(0, 8)}
          render={(item) => (
            <span>
              {item.staff_name} - {formatMoney(item.amount)} - {item.status}
              {item.status === "pending" ? (
                <>
                  {" "}
                  <button type="button" className="table-action" onClick={() => runAction("advance-review", () => onReviewAdvance(item.id, "approved"), "Advance approved.")}>Approve</button>
                  <button type="button" className="table-action" onClick={() => runAction("advance-review", () => onReviewAdvance(item.id, "paid"), "Advance paid.")}>Pay</button>
                  <button type="button" className="table-action danger" onClick={() => runAction("advance-review", () => onReviewAdvance(item.id, "rejected"), "Advance rejected.")}>Reject</button>
                </>
              ) : null}
            </span>
          )}
        />
        <RecordList title="Absent records" rows={(data?.absences || []).slice(0, 8)} render={(item) => `${item.staff_name} - ${item.date} - ${item.notes || "Absent"}`} />
      </section>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Activity log</h3>
          <small>{activity.length} latest records</small>
        </div>
        {activity.length ? (
          <>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Date</th><th>Staff</th><th>Action</th><th>Details</th><th>Actor</th></tr></thead>
                <tbody>
                  {visibleActivity.map((item) => (
                    <tr key={item.id}>
                      <td>{formatDate(item.created_at)}</td>
                      <td>{item.staff_name || "-"}</td>
                      <td>{item.action}</td>
                      <td>{item.details || "-"}</td>
                      <td>{item.actor || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {activity.length > 3 ? (
              <div className="finance-table-actions">
                <button type="button" className="pill-button ghost" onClick={() => setActivityExpanded((current) => !current)}>
                  {activityExpanded ? "Show less" : `More (${activity.length - 3})`}
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <p className="panel-empty">No activity records yet.</p>
        )}
      </article>
    </section>
  );
}

function AdminNonTeachingStaffScreen({
  data,
  loading,
  error,
  onRetry,
  onCreateStaff,
  onUpdateStaff,
  onDownloadTeachers,
  onDownloadSharedQr,
  countries = [],
  defaultCountryCode = "NG",
}) {
  const summary = data?.summary || {};
  const staff = data?.staff || [];
  const payroll = data?.payroll || [];
  const attendance = data?.attendance || [];
  const leaves = data?.leaves || [];
  const advances = data?.advances || [];
  const absences = data?.absences || [];
  const [staffForm, setStaffForm] = useState({
    first_name: "",
    last_name: "",
    staff_type: "non_teaching",
    role: "",
    department: "",
    base_salary: "",
    bank_code: "",
    bank_name: "",
    bank_account_name: "",
    bank_account_number: "",
    email: "",
    phone: "",
    gender: "",
    employment_type: "full_time",
    hire_date: "",
    staff_password: "",
    confirm_staff_password: "",
  });
  const [editingStaffId, setEditingStaffId] = useState("");
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [selectedRecordType, setSelectedRecordType] = useState("");
  const [showStaffPassword, setShowStaffPassword] = useState(false);
  const [showStaffConfirmPassword, setShowStaffConfirmPassword] = useState(false);

  const formatMoney = (value) => `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString()}`;

  const handleSelectRecord = (type, item) => {
    setSelectedRecordType(type);
    setSelectedRecord(item);
  };

  const clearSelectedRecord = () => {
    setSelectedRecordType("");
    setSelectedRecord(null);
  };

  const resetStaffForm = () => {
    setEditingStaffId("");
    setShowStaffPassword(false);
    setShowStaffConfirmPassword(false);
    setStaffForm({
      first_name: "",
      last_name: "",
      staff_type: "non_teaching",
      role: "",
      department: "",
      base_salary: "",
      bank_code: "",
      bank_name: "",
      bank_account_name: "",
      bank_account_number: "",
      email: "",
      phone: "",
      gender: "",
      employment_type: "full_time",
      hire_date: "",
      staff_password: "",
      confirm_staff_password: "",
    });
  };

  const handleEditStaff = (item) => {
    setEditingStaffId(item.id);
    setShowStaffPassword(false);
    setShowStaffConfirmPassword(false);
    setStaffForm({
      first_name: item.first_name || "",
      last_name: item.last_name || "",
      staff_type: item.staff_type || "non_teaching",
      role: item.role || "",
      department: item.department || "",
      base_salary: item.base_salary || "",
      bank_code: item.bank_code || "",
      bank_name: item.bank_name || "",
      bank_account_name: item.bank_account_name || "",
      bank_account_number: item.bank_account_number || "",
      email: item.email || "",
      phone: item.phone || "",
      gender: item.gender || "",
      employment_type: item.employment_type || "full_time",
      hire_date: item.hire_date || "",
      staff_password: "",
      confirm_staff_password: "",
    });
  };

  const runAction = async (key, action, successMessage) => {
    setBusy(key);
    setFeedback("");
    setFormError("");
    try {
      const result = await action();
      setFeedback(result?.message || successMessage);
      return result;
    } catch (actionError) {
      setFormError(actionError.message || "Action failed.");
      return null;
    } finally {
      setBusy("");
    }
  };

  const handleStaffSubmit = async (event) => {
    event.preventDefault();
    if (staffForm.staff_password || staffForm.confirm_staff_password) {
      if (staffForm.staff_password !== staffForm.confirm_staff_password) {
        setFormError("Staff password and confirm password must match.");
        return;
      }
      if (staffForm.staff_password.length < 8) {
        setFormError("Staff password must be at least 8 characters.");
        return;
      }
    }
    const result = await runAction(
      "staff",
      () => editingStaffId ? onUpdateStaff(editingStaffId, staffForm) : onCreateStaff(staffForm),
      "Staff saved."
    );
    if (result) resetStaffForm();
  };

  const nonTeachingStaff = staff.filter(item => item.staff_type === "non_teaching");
  const nonTeachingStaffIds = new Set(nonTeachingStaff.map((item) => item.id));
  const nonTeachingPayroll = payroll.filter((item) => nonTeachingStaffIds.has(item.staff_id));
  const nonTeachingAttendance = attendance.filter((item) => nonTeachingStaffIds.has(item.staff_id));
  const nonTeachingLeaves = leaves.filter((item) => nonTeachingStaffIds.has(item.staff_id));
  const nonTeachingAdvances = advances.filter((item) => nonTeachingStaffIds.has(item.staff_id));
  const nonTeachingAbsences = absences.filter((item) => nonTeachingStaffIds.has(item.staff_id));
  const selectedRecordTitle = selectedRecordType
    ? `${selectedRecordType.charAt(0).toUpperCase()}${selectedRecordType.slice(1)} details`
    : "";

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Non-Teaching Staff</h2>
        <p>Manage administrative, support, and non-teaching personnel records.</p>
      </div>

      <ScreenState loading={loading && !nonTeachingStaff.length} error={error} onRetry={onRetry} />

      <section className="metric-grid">
        <MetricCard label="Total Staff" value={summary.total_staff ?? 0} trend={`${summary.teaching_staff ?? 0} teaching`} />
        <MetricCard label="Monthly Salary" value={formatMoney(summary.total_monthly_salary)} trend="Base salary total" />
        <MetricCard label="Today Present" value={summary.today_present ?? 0} trend={`${summary.today_absent ?? 0} absent`} />
        <MetricCard label="Salary Balances" value={formatMoney(summary.salary_balances)} trend={`${summary.pending_advances ?? 0} pending advances`} />
      </section>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Staff data exports</h3>
          <small>Download non-teaching staff data or the shared staff attendance QR code.</small>
        </div>
        <div className="panel-form-actions" style={{ justifyContent: "flex-start" }}>
          <button type="button" onClick={() => window.open("/api/hr/staff/download/?type=non_teaching", "_blank")}>Download non-teaching staff CSV</button>
          <button type="button" onClick={onDownloadSharedQr}>Download shared staff QR</button>
        </div>
      </article>

      {(feedback || formError) ? (
        <article className="app-panel">
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          {formError ? <p className="form-feedback error">{formError}</p> : null}
        </article>
      ) : null}

      {editingStaffId && <div className="modal-overlay-bg" onClick={resetStaffForm} />}

      <article
        className={`app-panel ${editingStaffId ? "edit-modal-card" : ""}`}
        role={editingStaffId ? "dialog" : undefined}
        aria-modal={editingStaffId ? "true" : undefined}
        aria-labelledby={editingStaffId ? "edit-non-teaching-staff-title" : undefined}
      >
        <div className="edit-modal-head">
          <div>
            <h3 id={editingStaffId ? "edit-non-teaching-staff-title" : undefined}>{editingStaffId ? "Edit staff profile" : "Add non-teaching staff"}</h3>
            <p>Create or update administrative and support staff records.</p>
          </div>
          {editingStaffId ? <button type="button" className="edit-modal-close" onClick={resetStaffForm} aria-label="Close"><X size={16} /></button> : null}
        </div>
        <form className="panel-form" onSubmit={handleStaffSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">First name<input value={staffForm.first_name} onChange={(e) => setStaffForm((p) => ({ ...p, first_name: e.target.value }))} /></label>
            <label className="panel-field">Last name<input value={staffForm.last_name} onChange={(e) => setStaffForm((p) => ({ ...p, last_name: e.target.value }))} /></label>
            <label className="panel-field">Role<input value={staffForm.role} onChange={(e) => setStaffForm((p) => ({ ...p, role: e.target.value }))} placeholder="e.g., Administrative Assistant" /></label>
            <label className="panel-field">Department<input value={staffForm.department} onChange={(e) => setStaffForm((p) => ({ ...p, department: e.target.value }))} placeholder="e.g., Administration" /></label>
            <label className="panel-field">Monthly salary<input type="number" value={staffForm.base_salary} onChange={(e) => setStaffForm((p) => ({ ...p, base_salary: e.target.value }))} /></label>
            <label className="panel-field">Bank name<input value={staffForm.bank_name} onChange={(e) => setStaffForm((p) => ({ ...p, bank_name: e.target.value }))} /></label>
            <label className="panel-field">Account name<input value={staffForm.bank_account_name} onChange={(e) => setStaffForm((p) => ({ ...p, bank_account_name: e.target.value }))} /></label>
            <label className="panel-field">Account number<input value={staffForm.bank_account_number} onChange={(e) => setStaffForm((p) => ({ ...p, bank_account_number: e.target.value.replace(/\D/g, "") }))} /></label>
            <label className="panel-field">Email<input value={staffForm.email} onChange={(e) => setStaffForm((p) => ({ ...p, email: e.target.value }))} /></label>
            <label className="panel-field">Phone<PhoneCountryInput countries={countries} value={staffForm.phone} onChange={(val) => setStaffForm((p) => ({ ...p, phone: val }))} defaultCountryCode={defaultCountryCode} /></label>
            <label className="panel-field">Gender<select value={staffForm.gender} onChange={(e) => setStaffForm((p) => ({ ...p, gender: e.target.value }))}><option value="">Select gender</option><option value="M">Male</option><option value="F">Female</option><option value="O">Other</option><option value="N">Prefer not to say</option></select></label>
            <label className="panel-field">Hire date<input type="date" value={staffForm.hire_date} onChange={(e) => setStaffForm((p) => ({ ...p, hire_date: e.target.value }))} /></label>
            <label className="panel-field">
              Login password
              <div className="password-toggle-field">
                <input type={showStaffPassword ? "text" : "password"} value={staffForm.staff_password} onChange={(e) => setStaffForm((p) => ({ ...p, staff_password: e.target.value }))} placeholder={editingStaffId ? "Leave blank to keep current" : "Optional staff login"} />
                <button type="button" onClick={() => setShowStaffPassword((current) => !current)}>
                  {showStaffPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
            <label className="panel-field">
              Confirm password
              <div className="password-toggle-field">
                <input type={showStaffConfirmPassword ? "text" : "password"} value={staffForm.confirm_staff_password} onChange={(e) => setStaffForm((p) => ({ ...p, confirm_staff_password: e.target.value }))} placeholder={editingStaffId ? "Repeat new password" : "Repeat password"} />
                <button type="button" onClick={() => setShowStaffConfirmPassword((current) => !current)}>
                  {showStaffConfirmPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
          </div>
          <div className="panel-form-actions">
            {editingStaffId ? <button type="button" className="table-action" onClick={resetStaffForm}>Cancel</button> : null}
            <button type="submit" disabled={busy === "staff"}>{busy === "staff" ? "Saving..." : editingStaffId ? "Save staff" : "Add staff"}</button>
          </div>
        </form>
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Non-teaching staff register</h3>
          <small>Click a staff name or View to open the profile.</small>
        </div>
        {nonTeachingStaff.length ? (
          <table className="data-table">
            <thead><tr><th>Staff</th><th>Gender</th><th>Role</th><th>Department</th><th>Salary</th><th>Balance</th><th>Attendance</th><th>Actions</th></tr></thead>
            <tbody>
              {nonTeachingStaff.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button type="button" className="record-list-button" onClick={() => handleSelectRecord("profile", item)} title="View staff profile">
                      {item.name}
                    </button>
                    <br /><small>{item.staff_code} - Non-teaching</small>
                  </td>
                  <td>{genderDisplay(item.gender)}</td>
                  <td>{item.role}</td>
                  <td>{item.department || "-"}</td>
                  <td>{formatMoney(item.base_salary)}</td>
                  <td>{formatMoney(item.salary_balance)}</td>
                  <td>{item.attendance_rate}% - {item.absent_count} absent</td>
                  <td>
                    <div className="table-actions-inline">
                      <button type="button" className="table-action" onClick={() => handleSelectRecord("profile", item)}>View</button>
                      <button type="button" className="table-action" onClick={() => handleEditStaff(item)}>Edit</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="panel-empty">No non-teaching staff records yet.</p>}
      </article>

      {selectedRecord && selectedRecordType === "profile" ? (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) clearSelectedRecord(); }}>
          <ReadOnlyPersonProfile
            person={selectedRecord}
            title="Staff profile"
            codeLabel="Staff ID"
            codeValue={selectedRecord.staff_code}
            onClose={clearSelectedRecord}
          />
        </div>
      ) : selectedRecord ? (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) clearSelectedRecord(); }}>
          <article className="app-panel edit-modal-card">
            <div className="edit-modal-head">
              <div><h3>{selectedRecordTitle}</h3></div>
              <button type="button" className="edit-modal-close" onClick={clearSelectedRecord} aria-label="Close"><X size={16} /></button>
            </div>
            <div style={{padding:"0 1.5rem 1.5rem"}}>
              <dl className="record-detail-grid">
                {Object.entries(selectedRecord)
                  .filter(([key]) => key !== "id" && key !== "staff_id")
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{value === null || value === undefined || value === "" ? "-" : String(value)}</dd>
                    </div>
                  ))}
              </dl>
            </div>
          </article>
        </div>
      ) : null}
    </section>
  );
}

function AdminHRActivityScreen({ data, loading, error, onRetry, onReviewLeave, onReviewAdvance }) {
  const activity = data?.activity || [];
  const summary = data?.summary || {};
  const leaves = data?.teacher_leaves || [];
  const advances = data?.teacher_advances || [];
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [activeTab, setActiveTab] = useState("approvals");
  const formatMoney = (value) => `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString()}`;

  const runAction = async (key, action, successMessage) => {
    setBusy(key);
    setFeedback("");
    setFormError("");
    try {
      const result = await action();
      setFeedback(result?.message || successMessage);
      return result;
    } catch (actionError) {
      setFormError(actionError.message || "Action failed.");
      return null;
    } finally {
      setBusy("");
    }
  };

  const pendingCount = leaves.length + advances.length;

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <div>
          <h2>HR Management</h2>
          <p>Approve leave and salary advance requests, and review HR activity.</p>
        </div>
        {data ? (
          <div className="hr-hero-stats">
            <div className="hr-hero-stat">
              <span className="hr-hero-stat-value">{leaves.length}</span>
              <span className="hr-hero-stat-label">Leave{leaves.length !== 1 ? "s" : ""} Pending</span>
            </div>
            <div className="hr-hero-stat">
              <span className="hr-hero-stat-value">{advances.length}</span>
              <span className="hr-hero-stat-label">Advance{advances.length !== 1 ? "s" : ""} Pending</span>
            </div>
            <div className="hr-hero-stat muted">
              <span className="hr-hero-stat-value">{summary.today_activity ?? 0}</span>
              <span className="hr-hero-stat-label">Actions Today</span>
            </div>
          </div>
        ) : null}
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <article className="app-panel hr-panel">
          <div className="hr-tab-bar">
            <button
              type="button"
              className={`hr-tab ${activeTab === "approvals" ? "active" : ""}`}
              onClick={() => setActiveTab("approvals")}
            >
              Pending Approvals
              {pendingCount > 0 ? <span className="hr-tab-badge">{pendingCount}</span> : null}
            </button>
            <button
              type="button"
              className={`hr-tab ${activeTab === "activity" ? "active" : ""}`}
              onClick={() => setActiveTab("activity")}
            >
              Activity Log
              <span className="hr-tab-count">{activity.length}</span>
            </button>
          </div>

          {(feedback || formError) ? (
            <div style={{ padding: "0.75rem 1rem 0", borderBottom: "1px solid var(--panel-border, #e2e8f0)" }}>
              {feedback ? <p className="form-feedback success">{feedback}</p> : null}
              {formError ? <p className="form-feedback error">{formError}</p> : null}
            </div>
          ) : null}

          {activeTab === "approvals" && (
            <div className="hr-tab-body">
              <div className="hr-approval-section">
                <div className="hr-approval-header">
                  <h4>Leave Requests</h4>
                  {leaves.length > 0 ? <span className="hr-count-badge">{leaves.length} pending</span> : null}
                </div>
                {leaves.length ? (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr><th>Staff</th><th>Type</th><th>Duration</th><th>Reason</th><th></th></tr>
                      </thead>
                      <tbody>
                        {leaves.map((item) => (
                          <tr key={item.id}>
                            <td><strong>{item.staff_name}</strong></td>
                            <td>{item.leave_type}</td>
                            <td>
                              {item.start_date} → {item.end_date}
                              <br /><small className="text-muted">{item.days} day{item.days === 1 ? "" : "s"}</small>
                            </td>
                            <td>{item.reason || "—"}</td>
                            <td>
                              <button
                                type="button"
                                className="table-action"
                                disabled={!!busy}
                                onClick={() => runAction(`leave-${item.id}`, () => onReviewLeave(item.id, "approved"), "Leave approved.")}
                              >
                                {busy === `leave-${item.id}` ? "…" : "Approve"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="hr-empty-row">
                    <span className="hr-empty-check">✓</span> No pending leave requests
                  </div>
                )}
              </div>

              <div className="hr-section-divider" />

              <div className="hr-approval-section">
                <div className="hr-approval-header">
                  <h4>Salary Advance Requests</h4>
                  {advances.length > 0 ? <span className="hr-count-badge">{advances.length} pending</span> : null}
                </div>
                {advances.length ? (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr><th>Staff</th><th>Amount</th><th>Requested</th><th>Reason</th><th></th></tr>
                      </thead>
                      <tbody>
                        {advances.map((item) => (
                          <tr key={item.id}>
                            <td><strong>{item.staff_name}</strong></td>
                            <td><strong>{formatMoney(item.amount)}</strong></td>
                            <td>{item.request_date}</td>
                            <td>{item.reason || "—"}</td>
                            <td>
                              <button
                                type="button"
                                className="table-action"
                                disabled={!!busy}
                                onClick={() => runAction(`advance-${item.id}`, () => onReviewAdvance(item.id, "approved"), "Salary advance approved.")}
                              >
                                {busy === `advance-${item.id}` ? "…" : "Approve"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="hr-empty-row">
                    <span className="hr-empty-check">✓</span> No pending salary advance requests
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "activity" && (
            <div className="hr-tab-body">
              {activity.length ? (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr><th>Action</th><th>Staff</th><th>Details</th><th>Actor</th><th>Date</th></tr>
                    </thead>
                    <tbody>
                      {activity.map((item) => (
                        <tr key={item.id}>
                          <td><span className="hr-action-tag">{item.action}</span></td>
                          <td>
                            {item.staff_name || "System"}
                            {item.staff_code ? <><br /><small className="text-muted">{item.staff_code}</small></> : null}
                          </td>
                          <td>{item.details || "—"}</td>
                          <td>{item.actor || "—"}</td>
                          <td><small>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</small></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="panel-empty">No activity records yet.</p>
              )}
            </div>
          )}
        </article>
      ) : null}
    </section>
  );
}

function RecordList({ title, rows = [], render, onSelect }) {
  return (
    <article className="app-panel">
      <div className="panel-head"><h3>{title}</h3><small>{rows.length} shown</small></div>
      {rows.length ? (
        <ul className="panel-list">
          {rows.map((item) => (
            <li key={item.id}>
              {onSelect ? (
                <button type="button" className="record-list-button" onClick={() => onSelect(item)}>
                  {render(item)}
                </button>
              ) : render(item)}
            </li>
          ))}
        </ul>
      ) : <p className="panel-empty">No records yet.</p>}
    </article>
  );
}

function idCardDate(value) {
  if (!value) {
    return "-";
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
  if (normalized === "O") return "Other";
  if (normalized === "N") return "Prefer not to say";
  return value || "-";
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Could not read QR image."));
    reader.readAsDataURL(blob);
  });
}

export function IdCardPreview({ person, school, qrDataUrl }) {
  const brand = resolveSchoolBrand(school);
  const [isFlipped, setIsFlipped] = useState(false);
  if (!person) {
    return (
      <article className="app-panel id-card-empty">
        <h3>ID Card Preview</h3>
        <p className="panel-empty">Select a student or staff member to preview an ID card.</p>
      </article>
    );
  }

  return (
    <div id="schooldom-id-card-document" className="id-card-print-area id-card-flip-stage">
      <div className={`id-card-flip-inner ${isFlipped ? "flipped" : ""}`}>
        <article className="id-card-preview-card id-card-face id-card-front">
          <div className="id-card-ribbon">{person.display_type}</div>
          <header className="id-card-top">
            <div className="school-brand-logo id-card-school-logo">
              {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
            </div>
            <div>
              <strong>{brand.name}</strong>
              {brand.motto ? <small className="id-card-motto">{brand.motto}</small> : null}
              <span>{brand.code || "Official Identity Card"}</span>
            </div>
          </header>

          <section className="id-card-front-body">
            <section className="id-card-person">
              <div className="id-card-photo">
                {person.profile_picture ? <img src={person.profile_picture} alt={`${person.name} profile`} /> : <span>{userInitials({ full_name: person.name })}</span>}
              </div>
              <div>
                <p>{person.name || "Unnamed user"}</p>
                <strong>{person.unique_id || "No ID assigned"}</strong>
                <span>{person.primary_label || "-"}</span>
              </div>
            </section>

            <dl className="id-card-details">
              <div>
                <dt>{person.person_type === "student" ? "Admission" : "Employment"}</dt>
                <dd>{idCardDate(person.admission_or_employment_date)}</dd>
              </div>
              <div>
                <dt>Date of Birth</dt>
                <dd>{idCardDate(person.date_of_birth)}</dd>
              </div>
              <div>
                <dt>Gender</dt>
                <dd>{genderDisplay(person.gender)}</dd>
              </div>
              <div>
                <dt>{person.person_type === "student" ? "Class" : "Role"}</dt>
                <dd>{person.primary_label || "-"}</dd>
              </div>
              <div>
                <dt>{person.person_type === "student" ? "Guardian" : "Department"}</dt>
                <dd>{person.guardian_name || person.department || person.secondary_label || "-"}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{person.phone || person.guardian_phone || "-"}</dd>
              </div>
            </dl>
          </section>

          <footer className="id-card-footer id-card-front-footer">
            <strong><span>Flip card to verify {person.email || person.secondary_label || "SchoolDom profile verification"}
</span></strong>
          </footer>
        </article>

        <article className="id-card-preview-card id-card-face id-card-back">
          <header className="id-card-back-head">
            <div className="school-brand-logo id-card-school-logo">
              {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
            </div>
            <div>
              <strong>{brand.name}</strong>
              {brand.motto ? <small className="id-card-motto">{brand.motto}</small> : null}
              <span>Official ID verification</span>
            </div>
          </header>
          <section className="id-card-back-qr-panel">
            <p>Scan to verify</p>
            <div className="id-card-back-qr">
              {qrDataUrl ? <img src={qrDataUrl} alt={`${person.name} verification QR code`} /> : <span>QR</span>}
            </div>
            <strong>{person.unique_id || "No ID assigned"}</strong>
            <span>{person.name || "Unnamed user"}</span>
          </section>
          <footer className="id-card-back-footer">
            <span>Valid only when the scan page confirms this profile as verified and active.</span>
          </footer>
        </article>
      </div>
      <button type="button" className="id-card-flip-button" onClick={() => setIsFlipped((value) => !value)}>
        {isFlipped ? "Show Front" : "Show QR Back"}
      </button>
    </div>
  );
}

export function IdCardVerificationPage() {
  const [state, setState] = useState({ loading: true, error: "", data: null });
  const [form, setForm] = useState({ email: "", unique_id: "" });
  const [submitting, setSubmitting] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const token = useMemo(() => new URLSearchParams(window.location.search).get("token") || "", []);

  useEffect(() => {
    let active = true;
    if (!token) {
      setState({ loading: false, error: "Verification token is missing.", data: null });
      return () => {
        active = false;
      };
    }

    setState({ loading: true, error: "", data: null });
    fetch(`${API_BASE_URL}/api/app/id-cards/verify/?token=${encodeURIComponent(token)}`)
      .then(async (response) => {
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(payload?.message || "This ID card could not be verified.");
        }
        return payload;
      })
      .then((payload) => {
        if (active) setState({ loading: false, error: "", data: payload });
      })
      .catch((verifyError) => {
        if (active) setState({ loading: false, error: verifyError.message || "This ID card could not be verified.", data: null });
      });

    return () => {
      active = false;
    };
  }, [token]);

  const payload = state.data;
  const person = payload?.person || {};
  const school = resolveSchoolBrand(payload?.school || {});
  const isValid = Boolean(payload?.verified && payload?.valid);
  const challenge = payload?.challenge || {};
  const statusText = state.loading ? "Checking ID" : isValid ? "Verified ID" : payload?.verified ? "Inactive Profile" : "Verification Required";

  const handleVerifySubmit = async (event) => {
    event.preventDefault();
    setVerifyError("");
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/app/id-cards/verify/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          email: form.email.trim(),
          unique_id: form.unique_id.trim(),
        }),
      });
      const verifiedPayload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(verifiedPayload?.message || "This ID card could not be verified.");
      }
      setState({ loading: false, error: "", data: verifiedPayload });
    } catch (submitError) {
      setVerifyError(submitError.message || "This ID card could not be verified.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="id-verify-page">
      <section className="id-verify-shell">
        <article className={`id-verify-card ${isValid ? "verified" : ""}`}>
          <div className="id-verify-status">
            <span>{statusText}</span>
          </div>

          {state.loading ? (
            <div className="id-verify-message">
              <h1>Verifying ID card</h1>
              <p>Please wait while SchoolDom checks this card.</p>
            </div>
          ) : state.error ? (
            <div className="id-verify-message">
              <h1>ID card not verified</h1>
              <p>{state.error}</p>
            </div>
          ) : payload?.challenge_required ? (
            <>
              <header className="id-verify-school">
                <div className="school-brand-logo id-verify-logo">
                  {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{school.initials}</span>}
                </div>
                <div>
                  <h1>{school.name}</h1>
                  <p>{school.code || "Official identity verification"}</p>
                </div>
              </header>

              <form className="panel-form id-verify-message" onSubmit={handleVerifySubmit}>
                <h1>Verify ID card</h1>
                <p>{payload.message || "Enter the email and ID on the card."}</p>
                <label className="panel-field">
                  Email
                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                    autoComplete="email"
                    required
                  />
                </label>
                <label className="panel-field">
                  {challenge.id_label || "ID"}
                  <input
                    value={form.unique_id}
                    onChange={(event) => setForm((current) => ({ ...current, unique_id: event.target.value }))}
                    autoComplete="off"
                    required
                  />
                </label>
                {verifyError ? <p className="form-feedback error">{verifyError}</p> : null}
                <div className="panel-form-actions">
                  <button type="submit" disabled={submitting}>
                    {submitting ? "Verifying..." : "Verify ID"}
                  </button>
                </div>
              </form>
            </>
          ) : (
            <>
              <header className="id-verify-school">
                <div className="school-brand-logo id-verify-logo">
                  {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{school.initials}</span>}
                </div>
                <div>
                  <h1>{school.name}</h1>
                  <p>{school.code || "Official identity verification"}</p>
                </div>
              </header>

              <section className="id-verify-person">
                <div>
                  <p>{person.display_type || "ID Card"}</p>
                  <h2>{person.name || person.unique_id || "No ID assigned"}</h2>
                  <strong>{person.unique_id || "No ID assigned"}</strong>
                  <span>{person.email || "No email on record"}</span>
                </div>
              </section>

              <dl className="id-verify-details">
                <div>
                  <dt>Status</dt>
                  <dd>{payload.message || (isValid ? "ID card verified." : "Profile is inactive.")}</dd>
                </div>
                <div>
                  <dt>Name</dt>
                  <dd>{person.name || "-"}</dd>
                </div>
                <div>
                  <dt>{person.person_type === "student" ? "Student ID" : "Staff ID"}</dt>
                  <dd>{person.unique_id || "No ID assigned"}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{person.email || "-"}</dd>
                </div>
              </dl>
            </>
          )}
        </article>
      </section>
    </main>
  );
}

function buildIdCardHtml(person, school, qrDataUrl) {
  const brand = resolveSchoolBrand(school);
  const photoBlock = person.profile_picture
    ? `<img src="${escapeHtml(person.profile_picture)}" alt="${escapeHtml(person.name)} profile" />`
    : `<span>${escapeHtml(userInitials({ full_name: person.name }))}</span>`;
  const logoBlock = brand.logo
    ? `<img src="${escapeHtml(brand.logo)}" alt="${escapeHtml(brand.name)} logo" />`
    : `<span>${escapeHtml(brand.initials)}</span>`;
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(person.name)} ID Card</title>
  <style>
    *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#eef3f8;font-family:Inter,Arial,sans-serif;color:#102033}.stage{display:grid;gap:16px;justify-items:center;padding:24px}.flip{width:360px;height:560px;perspective:1400px}.inner{position:relative;width:100%;height:100%;transition:transform .55s ease;transform-style:preserve-3d}.inner.flipped{transform:rotateY(180deg)}.card{position:absolute;inset:0;width:360px;min-height:560px;background:#fff;border-radius:22px;overflow:hidden;box-shadow:0 24px 60px rgba(15,23,42,.18);border:1px solid #dbe5f0;backface-visibility:hidden}.back{transform:rotateY(180deg);background:#08111f;color:#fff}.ribbon{background:#0f3d5e;color:#fff;text-align:center;text-transform:uppercase;font-weight:800;letter-spacing:.12em;font-size:12px;padding:10px}.top,.backHead{display:flex;gap:12px;align-items:center;padding:18px 22px;background:linear-gradient(135deg,#f8fbff,#e8f2fb)}.backHead{background:#102033;color:#fff}.logo,.photo{display:grid;place-items:center;overflow:hidden;background:#fff;border:1px solid #d8e3ef}.logo{width:54px;height:54px;border-radius:16px;flex:0 0 auto}.logo img,.photo img,.qr img{width:100%;height:100%;object-fit:cover}.logo span,.photo span{font-weight:900;color:#0f3d5e}.top strong,.backHead strong{display:block;font-size:18px}.motto{display:block;color:#0f3d5e;font-size:11px;font-style:italic;font-weight:800;margin-top:2px}.backHead .motto{color:#a7f3d0}.top span,.backHead span{display:block;color:#64748b;font-size:12px;margin-top:2px}.backHead span{color:#cbd5e1}.person{display:grid;grid-template-columns:94px 1fr;gap:16px;padding:24px 22px 18px}.photo{width:94px;height:112px;border-radius:18px}.person p{margin:4px 0 8px;font-size:24px;line-height:1.05;font-weight:900}.person strong{display:inline-flex;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:6px 10px;font-size:13px}.person span{display:block;color:#475569;margin-top:10px;font-weight:700}.details{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 22px 18px}.details div{border:1px solid #e2e8f0;border-radius:12px;padding:10px;background:#f8fafc}.details dt{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800}.details dd{margin:4px 0 0;font-weight:800;font-size:13px}.frontFooter{margin:0 22px 22px;padding:16px;border-radius:18px;background:#08111f;color:#fff}.frontFooter strong,.frontFooter span{display:block}.frontFooter span{color:#cbd5e1;font-size:12px;margin-top:6px}.backPanel{display:grid;justify-items:center;padding:18px 22px 10px;text-align:center}.backPanel p{margin:0 0 16px;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#a7f3d0}.qr{width:250px;height:250px;border-radius:18px;background:#fff;padding:12px;display:grid;place-items:center;color:#0f3d5e;font-weight:900}.qr img{object-fit:contain}.backPanel strong{display:inline-flex;margin-top:12px;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:7px 12px;font-size:14px}.backPanel span{display:block;margin-top:6px;font-size:22px;line-height:1.05;font-weight:900}.backFooter{padding:0 24px 32px;text-align:center;color:#cbd5e1;font-size:12px;line-height:1.45}.flipBtn{border:0;border-radius:8px;background:#0f3d5e;color:#fff;padding:10px 14px;font-weight:800;cursor:pointer}@media print{body{background:#fff;display:block}.stage{display:grid;grid-template-columns:360px 360px;gap:18px;place-content:center;padding:0}.flip{display:contents}.inner{display:contents;transform:none!important}.card{position:relative;inset:auto;box-shadow:none;page-break-inside:avoid;backface-visibility:visible}.back{transform:none}.flipBtn{display:none}}
  </style>
</head>
<body>
  <div class="stage">
    <div class="flip">
      <div class="inner" id="cardInner">
        <article class="card front">
          <div class="ribbon">${escapeHtml(person.display_type)}</div>
          <header class="top"><div class="logo">${logoBlock}</div><div><strong>${escapeHtml(brand.name)}</strong>${brand.motto ? `<small class="motto">${escapeHtml(brand.motto)}</small>` : ""}<span>${escapeHtml(brand.code || "Official Identity Card")}</span></div></header>
          <section class="person"><div class="photo">${photoBlock}</div><div><p>${escapeHtml(person.name || "Unnamed user")}</p><strong>${escapeHtml(person.unique_id || "No ID assigned")}</strong><span>${escapeHtml(person.primary_label || "-")}</span></div></section>
          <dl class="details">
            <div><dt>${person.person_type === "student" ? "Admission" : "Employment"}</dt><dd>${escapeHtml(idCardDate(person.admission_or_employment_date))}</dd></div>
            <div><dt>Date of Birth</dt><dd>${escapeHtml(idCardDate(person.date_of_birth))}</dd></div>
            <div><dt>Gender</dt><dd>${escapeHtml(genderDisplay(person.gender))}</dd></div>
            <div><dt>${person.person_type === "student" ? "Class" : "Role"}</dt><dd>${escapeHtml(person.primary_label || "-")}</dd></div>
            <div><dt>${person.person_type === "student" ? "Guardian" : "Department"}</dt><dd>${escapeHtml(person.guardian_name || person.department || person.secondary_label || "-")}</dd></div>
            <div><dt>Phone</dt><dd>${escapeHtml(person.phone || person.guardian_phone || "-")}</dd></div>
          </dl>
          <footer class="frontFooter"><strong>Flip card to verify</strong><span>${escapeHtml(person.email || person.secondary_label || "SchoolDom profile verification")}</span></footer>
        </article>
        <article class="card back">
          <header class="backHead"><div class="logo">${logoBlock}</div><div><strong>${escapeHtml(brand.name)}</strong>${brand.motto ? `<small class="motto">${escapeHtml(brand.motto)}</small>` : ""}<span>Official ID verification</span></div></header>
          <section class="backPanel"><p>Scan to verify</p><div class="qr"><img src="${escapeHtml(qrDataUrl || "")}" alt="Verification QR code" /></div><strong>${escapeHtml(person.unique_id || "No ID assigned")}</strong><span>${escapeHtml(person.name || "Unnamed user")}</span></section>
          <footer class="backFooter">Valid only when the scan page confirms this profile as verified and active.</footer>
        </article>
      </div>
    </div>
    <button class="flipBtn" type="button" onclick="document.getElementById('cardInner').classList.toggle('flipped')">Flip ID Card</button>
  </div>
</body>
</html>`;
}

function AdminIdCardsScreen({ data, loading, error, onRetry, session, school }) {
  const people = data?.people || [];
  const summary = data?.summary || {};
  const [selectedId, setSelectedId] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [qrLoading, setQrLoading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  const cardSchool = data?.school || school;
  const filteredPeople = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return people.filter((person) => {
      const typeMatch = filterType === "all" || person.person_type === filterType;
      const haystack = [person.name, person.unique_id, person.primary_label, person.secondary_label, person.email, person.phone]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return typeMatch && (!query || haystack.includes(query));
    });
  }, [filterType, people, searchTerm]);
  const selectedPerson = people.find((person) => `${person.person_type}:${person.id}` === selectedId) || filteredPeople[0] || null;

  const fetchQrDataUrl = useCallback(
    async (person, isDownload = false) => {
      if (!person) {
        return "";
      }
      const params = new URLSearchParams({ person_type: person.person_type, person_id: person.id });
      if (isDownload) {
        params.set("download", "true");
      }
      const response = await fetch(`${API_BASE_URL}/api/app/id-cards/qr/?${params.toString()}`, {
        headers: session?.access ? { Authorization: `Bearer ${session.access}` } : {},
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.message || "Could not generate QR code.");
      }
      return {
        dataUrl: await blobToDataUrl(await response.blob()),
        tokenUsed: false,
        tokenMessage: response.headers.get("X-Token-Message") || "ID card generated.",
      };
    },
    [session]
  );

  useEffect(() => {
    if (!selectedId && filteredPeople[0]) {
      setSelectedId(`${filteredPeople[0].person_type}:${filteredPeople[0].id}`);
    }
  }, [filteredPeople, selectedId]);

  useEffect(() => {
    let active = true;
    setQrDataUrl("");
    setActionError("");
    setActionSuccess("");
    if (!selectedPerson) {
      return () => {
        active = false;
      };
    }
    setQrLoading(true);
    fetchQrDataUrl(selectedPerson)
      .then((result) => {
        if (active) setQrDataUrl(result.dataUrl);
      })
      .catch((qrError) => {
        if (active) setActionError(qrError.message || "Could not load QR code.");
      })
      .finally(() => {
        if (active) setQrLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchQrDataUrl, selectedPerson]);

  useEffect(() => {
    if (!actionSuccess) return undefined;
    const timeoutId = window.setTimeout(() => setActionSuccess(""), 4500);
    return () => window.clearTimeout(timeoutId);
  }, [actionSuccess]);

  const handlePrint = async () => {
    if (!selectedPerson) return;
    setActionError("");
    setActionSuccess("");
    try {
      const result = await fetchQrDataUrl(selectedPerson, true);
      setQrDataUrl(result.dataUrl);
      await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
      setActionSuccess(result.tokenMessage || "ID card generated.");
      window.print();
    } catch (printError) {
      setActionError(printError.message || "Could not generate ID card for printing.");
    }
  };

  return (
    <section className="screen-grid id-card-workspace">
      <div className="screen-hero id-card-hero">
        <h2>ID Card Generator</h2>
        <p>Generate secure student and staff ID cards with profile details and scannable verification QR codes.</p>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <section className="metric-grid">
            <MetricCard label="Total Cards" value={summary.total ?? people.length} trend="Ready to generate" />
            <MetricCard label="Students" value={summary.students ?? 0} trend="Learner cards" />
            <MetricCard label="Teaching Staff" value={summary.teaching_staff ?? 0} trend="Teacher cards" />
            <MetricCard label="Other Staff" value={summary.other_staff ?? 0} trend="Support staff cards" />
          </section>

          <section className="id-card-layout">
            <article className="app-panel id-card-directory">
              <div className="panel-head">
                <h3>People</h3>
                <small>Select a profile to preview or print.</small>
              </div>
              <div className="id-card-tools">
                <label className="panel-field">
                  Type
                  <select value={filterType} onChange={(event) => setFilterType(event.target.value)}>
                    <option value="all">All profiles</option>
                    <option value="student">Students</option>
                    <option value="teacher">Teaching staff</option>
                    <option value="staff">Other staff</option>
                  </select>
                </label>
                <label className="panel-field">
                  Search
                  <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Name, ID, class, or role" />
                </label>
              </div>
              {filteredPeople.length ? (
                <div className="id-card-person-list">
                  {filteredPeople.map((person) => {
                    const key = `${person.person_type}:${person.id}`;
                    return (
                      <button
                        key={key}
                        type="button"
                        className={`id-card-person-button ${selectedPerson && key === `${selectedPerson.person_type}:${selectedPerson.id}` ? "active" : ""}`}
                        onClick={() => setSelectedId(key)}
                      >
                        <span>{person.name}</span>
                        <small>{person.unique_id} - {person.primary_label || person.display_type}</small>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="panel-empty">No profiles match this filter.</p>
              )}
            </article>

            <article className="app-panel id-card-preview-panel">
              <div className="panel-head">
                <h3>Preview</h3>
                <small>{qrLoading ? "Generating secure QR..." : "CR80 3.375in x 2.125in"}</small>
              </div>
              {actionSuccess ? <div className="token-usage-toast" role="status">{actionSuccess}</div> : null}
              {actionError ? <p className="form-feedback error">{actionError}</p> : null}
              <IdCardPreview person={selectedPerson} school={cardSchool} qrDataUrl={qrDataUrl} />
              <div className="panel-form-actions id-card-actions">
                <button type="button" className="table-action" onClick={handlePrint} disabled={!selectedPerson || qrLoading}>
                  Generate / Print Card
                </button>
              </div>
            </article>
          </section>
        </>
      ) : null}
    </section>
  );
}

function documentFileName(prefix, student) {
  const base = String(student?.student_id || student?.admission_number || student?.name || "student")
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return `${prefix}-${base || "student"}.png`;
}

function openPrintableDocument(elementId, title) {
  const element = document.getElementById(elementId);
  if (!element) {
    throw new Error("The document preview is not ready yet.");
  }

  const content = `<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /><title>${escapeHtml(title)}</title><style>${documentStylesForExport()}</style></head><body>${element.outerHTML}<script>window.onload=()=>{window.focus();window.print();};</script></body></html>`;

  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=980,height=1200");
  if (printWindow) {
    printWindow.document.write(content);
    printWindow.document.close();
    return;
  }

  const iframe = document.createElement("iframe");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.overflow = "hidden";
  document.body.appendChild(iframe);

  const iframeDoc = iframe.contentWindow?.document;
  if (!iframeDoc) {
    iframe.remove();
    throw new Error("Unable to open print preview.");
  }

  iframeDoc.open();
  iframeDoc.write(content);
  iframeDoc.close();
  iframe.onload = () => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    setTimeout(() => iframe.remove(), 1000);
  };
}

async function downloadPrintablePng(elementId, filename, title) {
  const element = document.getElementById(elementId);
  if (!element) {
    throw new Error("The document preview is not ready yet.");
  }
  const clone = element.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
  const rect = element.getBoundingClientRect();
  const width = Math.max(850, Math.ceil(rect.width || element.scrollWidth || 850));
  const height = Math.max(1100, Math.ceil(element.scrollHeight || rect.height || 1100));
  const html = `<div xmlns="http://www.w3.org/1999/xhtml" style="width:${width}px;background:#ffffff;">${clone.outerHTML}</div>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><foreignObject width="100%" height="100%"><style>${documentStylesForExport()}</style>${html}</foreignObject></svg>`;
  const svgUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  const image = new Image();
  const pngUrl = await new Promise((resolve, reject) => {
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const scale = 2;
        canvas.width = width * scale;
        canvas.height = height * scale;
        const context = canvas.getContext("2d");
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.scale(scale, scale);
        context.drawImage(image, 0, 0);
        canvas.toBlob((blob) => {
          if (!blob) {
            reject(new Error("Could not render PNG."));
            return;
          }
          resolve(URL.createObjectURL(blob));
        }, "image/png");
      } catch (renderError) {
        reject(renderError);
      }
    };
    image.onerror = () => reject(new Error(`Could not render ${title || "document"} as PNG.`));
    image.src = svgUrl;
  });
  URL.revokeObjectURL(svgUrl);
  const link = document.createElement("a");
  link.href = pngUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(pngUrl);
}

function documentStylesForExport() {
  return `
    *{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#0f172a;font-family:Georgia,'Times New Roman',serif}.official-document{width:min(100%,850px);margin:24px auto;background:#fff;color:#111827;padding:42px;border:1px solid #d7e0ec;box-shadow:0 18px 45px rgba(15,23,42,.12)}.official-doc-header{text-align:center;border-bottom:3px double #0f3d5e;padding-bottom:18px;margin-bottom:24px}.official-doc-logo{width:82px;height:82px;border-radius:18px;border:1px solid #cbd5e1;display:grid;place-items:center;margin:0 auto 10px;overflow:hidden;background:#f8fafc}.official-doc-logo img{width:100%;height:100%;object-fit:contain}.official-doc-logo span{font-family:Arial,sans-serif;font-weight:900;color:#0f3d5e}.official-doc-header h1{font-size:28px;text-transform:uppercase;letter-spacing:.04em;margin:0}.official-doc-header p{margin:5px 0 0;color:#475569;font-family:Arial,sans-serif}.official-doc-motto{font-style:italic;font-weight:800;color:#0f3d5e}.official-doc-title{text-align:center;text-transform:uppercase;letter-spacing:.12em;font-size:22px;margin:20px 0;color:#0f3d5e}.doc-info-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin-bottom:22px}.doc-line{display:flex;gap:10px;border-bottom:1px solid #94a3b8;min-height:30px;align-items:flex-end}.doc-line strong{font-family:Arial,sans-serif;font-size:12px;text-transform:uppercase;white-space:nowrap;color:#334155}.doc-line span{font-weight:700}.document-table{width:100%;border-collapse:collapse;margin:14px 0 24px;font-family:Arial,sans-serif;font-size:13px}.document-table th,.document-table td{border:1px solid #cbd5e1;padding:8px;text-align:left}.document-table th{background:#eef6f3;color:#0f3d5e;text-transform:uppercase;font-size:11px}.term-record{break-inside:avoid;margin-bottom:18px}.term-record h3{margin:0 0 8px;font-family:Arial,sans-serif;color:#0f3d5e}.testimonial-border{border:12px double #198754;padding:28px;background:linear-gradient(0deg,rgba(25,135,84,.035),rgba(25,135,84,.035)),#fff}.testimonial-title{font-size:42px;color:#b42318;font-weight:900;text-align:center;font-family:Georgia,'Times New Roman',serif;margin:12px 0 24px}.testimonial-list{display:grid;gap:10px;counter-reset:item}.testimonial-row{display:grid;grid-template-columns:34px 190px 1fr;gap:10px;align-items:end}.testimonial-row:before{counter-increment:item;content:counter(item) ".";font-weight:800}.testimonial-row strong{font-family:Arial,sans-serif;font-size:12px}.testimonial-row span{border-bottom:1px solid #334155;min-height:24px;font-weight:700;padding:0 6px}.doc-summary-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}.doc-summary-strip div{border:1px solid #cbd5e1;padding:10px;background:#f8fafc}.doc-summary-strip strong,.doc-summary-strip span{display:block}.doc-summary-strip strong{font-family:Arial,sans-serif;font-size:11px;color:#64748b;text-transform:uppercase}.doc-summary-strip span{font-size:18px;font-weight:900}.signature-row{display:grid;grid-template-columns:1fr 120px 1fr;gap:20px;align-items:end;margin-top:42px}.signature-line{border-top:1px solid #111827;text-align:center;padding-top:8px;font-family:Arial,sans-serif;font-weight:800;font-size:12px}.stamp-seal{width:98px;height:98px;border-radius:50%;background:#dc2626;box-shadow:inset 0 0 0 8px rgba(255,255,255,.18);margin:auto}.stamp-box{border:2px dashed #94a3b8;min-height:86px;display:grid;place-items:center;color:#64748b;font-family:Arial,sans-serif;text-transform:uppercase;font-weight:800}.document-note{font-family:Arial,sans-serif;color:#64748b;font-size:12px}.no-print{display:none}.id-card-print-area{width:100%;min-height:620px;background:#fff;display:grid;grid-template-columns:370px 370px;gap:18px;place-content:center;place-items:center;font-family:Inter,Arial,sans-serif}.id-card-flip-inner{display:contents;transform:none!important}.id-card-face{position:relative;inset:auto;backface-visibility:visible}.id-card-back{transform:none}.id-card-preview-card{width:370px;min-height:560px;background:#fff;color:#102033;border:1px solid #d7e0ec;border-radius:22px;overflow:hidden;box-shadow:none}.id-card-back{display:grid;grid-template-rows:auto 1fr auto;background:#08111f;color:#fff}.id-card-ribbon{background:#0f3d5e;color:#fff;text-align:center;text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:900;padding:10px}.id-card-top,.id-card-back-head{display:flex;gap:12px;align-items:center;padding:18px 22px;background:linear-gradient(135deg,#f8fbff,#e8f2fb)}.id-card-back-head{background:#102033;color:#fff}.id-card-school-logo,.id-card-photo{display:grid;place-items:center;overflow:hidden;background:#fff;border:1px solid #d8e3ef}.id-card-school-logo{width:54px;height:54px;border-radius:16px;flex:0 0 auto}.id-card-school-logo img,.id-card-photo img,.id-card-back-qr img{width:100%;height:100%;object-fit:cover}.id-card-school-logo span,.id-card-photo span{font-weight:900;color:#0f3d5e}.id-card-top strong,.id-card-back-head strong{display:block;font-size:18px}.id-card-motto{display:block;color:#0f3d5e;font-size:11px;font-style:italic;font-weight:800;margin-top:2px}.id-card-back-head .id-card-motto{color:#a7f3d0}.id-card-top span,.id-card-back-head span{display:block;color:#64748b;font-size:12px;margin-top:2px}.id-card-back-head span{color:#cbd5e1}.id-card-person{display:grid;grid-template-columns:94px 1fr;gap:16px;padding:24px 22px 18px}.id-card-photo{width:94px;height:112px;border-radius:18px}.id-card-person p{margin:4px 0 8px;font-size:24px;line-height:1.05;font-weight:900}.id-card-person strong{display:inline-flex;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:6px 10px;font-size:13px}.id-card-person span{display:block;color:#475569;margin-top:10px;font-weight:700}.id-card-details{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 22px 18px}.id-card-details div{border:1px solid #e2e8f0;border-radius:12px;padding:10px;background:#f8fafc}.id-card-details dt{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800}.id-card-details dd{margin:4px 0 0;font-weight:800;font-size:13px}.id-card-front-footer{margin:0 22px 22px;padding:16px;border-radius:18px;background:#08111f;color:#fff}.id-card-front-footer strong,.id-card-front-footer span{display:block}.id-card-front-footer span{color:#cbd5e1;font-size:12px;margin-top:6px}.id-card-back-qr-panel{display:grid;justify-items:center;padding:18px 22px 10px;text-align:center}.id-card-back-qr-panel p{margin:0 0 16px;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#a7f3d0}.id-card-back-qr{width:250px;height:250px;border-radius:18px;background:#fff;padding:12px;display:grid;place-items:center;color:#0f3d5e;font-weight:900}.id-card-back-qr img{object-fit:contain}.id-card-back-qr-panel strong{display:inline-flex;margin-top:12px;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:7px 12px;font-size:14px}.id-card-back-qr-panel span{display:block;margin-top:6px;font-size:22px;line-height:1.05;font-weight:900}.id-card-back-footer{padding:0 24px 32px;text-align:center;color:#cbd5e1;font-size:12px;line-height:1.45}.id-card-flip-button{display:none}@media print{body{background:#fff}.official-document{box-shadow:none;margin:0 auto;border:none;min-height:100vh}.testimonial-border{min-height:calc(100vh - 84px)}}@media(max-width:720px){.official-document{padding:24px}.doc-info-grid,.doc-summary-strip,.signature-row{grid-template-columns:1fr}.testimonial-row{grid-template-columns:28px 1fr}.testimonial-row span{grid-column:2}}`;
}

function OfficialDocHeader({ school, title }) {
  const brand = resolveSchoolBrand(school);
  return (
    <header className="official-doc-header">
      <div className="official-doc-logo">
        {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
      </div>
      <h1>{brand.name}</h1>
      {brand.motto ? <p className="official-doc-motto">{brand.motto}</p> : null}
      <p>{school?.address || brand.code || "Official School Record"}</p>
      <h2 className="official-doc-title">{title}</h2>
    </header>
  );
}

function TranscriptPreview({ transcript, school }) {
  const selectedSchool = transcript?.school || school;
  const student = transcript?.student || {};
  const termRecords = transcript?.term_records || [];
  const cumulative = transcript?.cumulative || {};
  return (
    <article id="schooldom-transcript-document" className="official-document transcript-document">
      <OfficialDocHeader school={selectedSchool} title="Official Student Transcript" />
      <section className="doc-info-grid">
        <div className="doc-line"><strong>Student Name</strong><span>{student.name || "-"}</span></div>
        <div className="doc-line"><strong>Student ID</strong><span>{student.student_id || student.admission_number || "-"}</span></div>
        <div className="doc-line"><strong>Current Class</strong><span>{student.class_name || "-"}</span></div>
        <div className="doc-line"><strong>Admission Date</strong><span>{idCardDate(transcript?.admission_date)}</span></div>
        <div className="doc-line"><strong>Gender</strong><span>{genderDisplay(student.gender)}</span></div>
        <div className="doc-line"><strong>Sessions</strong><span>{(transcript?.session_history || []).join(", ") || "-"}</span></div>
      </section>
      <section className="doc-summary-strip">
        <div><strong>Total Score</strong><span>{cumulative.total_score ?? 0}</span></div>
        <div><strong>Max Score</strong><span>{cumulative.total_max ?? 0}</span></div>
        <div><strong>Average</strong><span>{cumulative.average ?? 0}%</span></div>
        <div><strong>Grade</strong><span>{cumulative.grade || "-"}</span></div>
      </section>
      {termRecords.length ? (
        termRecords.map((record, index) => (
          <section key={`${record.session}-${record.term}-${index}`} className="term-record">
            <h3>{record.session} - {record.term} - {record.class_name || "Class Record"}</h3>
            <table className="document-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Score</th>
                  <th>Max</th>
                  <th>%</th>
                  <th>Grade</th>
                  <th>Remark</th>
                </tr>
              </thead>
              <tbody>
                {(record.subjects || []).map((subject, subjectIndex) => (
                  <tr key={`${subject.subject}-${subjectIndex}`}>
                    <td>{subject.subject}</td>
                    <td>{subject.score}</td>
                    <td>{subject.max_score}</td>
                    <td>{subject.percentage ?? "-"}</td>
                    <td>{subject.grade || "-"}</td>
                    <td>{subject.remark || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))
      ) : (
        <p className="document-note">No academic result records are available for this student yet.</p>
      )}
      <div className="signature-row">
        <div className="signature-line">Principal / Administrator Signature</div>
        <div className="stamp-box">Stamp</div>
        <div className="signature-line">Registrar / Records Officer</div>
      </div>
    </article>
  );
}

function TestimonialPreview({ detail, school }) {
  const selectedSchool = detail?.school || school;
  const student = detail?.student || {};
  const testimonial = detail?.testimonial || {};
  const rows = [
    ["Student ID", student.student_id || testimonial.admission_number || student.admission_number],
    ["Student Full Name", testimonial.student_name || student.name],
    ["Date of Birth", idCardDate(testimonial.date_of_birth || student.date_of_birth)],
    ["Gender", genderDisplay(testimonial.gender || student.gender)],
    ["State of Origin", testimonial.state_of_origin || student.state_of_origin],
    ["Local Government Area", testimonial.local_government || student.local_government],
    ["Date of Admission", idCardDate(testimonial.admission_date || student.admission_date)],
    ["Class of Admission", testimonial.class_of_admission],
    ["Date of Leaving", idCardDate(testimonial.date_of_leaving)],
    ["Class of Leaving", testimonial.class_of_leaving],
    ["Reason for Leaving", testimonial.reason_for_leaving],
    ["Educational Attainment", testimonial.educational_attainment],
    ["Subjects Offered", testimonial.subjects_offered],
    ["Co-Curricular Activities", testimonial.co_curricular_activities],
    ["Prizes and Honors Won", testimonial.prizes_and_honors],
    ["Office Held", testimonial.office_held],
    ["Principal / Admin Remarks", testimonial.administrator_remarks],
  ];
  return (
    <article id="schooldom-testimonial-document" className="official-document testimonial-document">
      <div className="testimonial-border">
        <OfficialDocHeader school={selectedSchool} title="" />
        <div className="testimonial-title">Testimonial</div>
        <section className="testimonial-list">
          {rows.map(([label, value]) => (
            <div key={label} className="testimonial-row">
              <strong>{label}</strong>
              <span>{value || "-"}</span>
            </div>
          ))}
        </section>
        <div className="signature-row">
          <div className="signature-line">{idCardDate(testimonial.issue_date)}<br />Date</div>
          <div className="stamp-seal" aria-label="Official stamp area" />
          <div className="signature-line">{testimonial.principal_name || "Principal / Administrator"}<br />Signature and Stamp</div>
        </div>
      </div>
    </article>
  );
}

function transcriptRowsFromDetail(transcript) {
  return (transcript?.term_records || []).flatMap((record) =>
    (record.subjects || []).map((subject) => ({
      ...subject,
      context: `${record.session || "Session"} - ${record.term || "Term"} - ${record.class_name || "Class"}`,
    }))
  );
}

function AdminDocumentsScreen({ data, loading, error, onRetry, school, onLoadTranscript, onLoadTestimonial, onSaveTranscript, onSaveTestimonial }) {
  const students = data?.students || [];
  const summary = data?.summary || {};
  const creditBalance = data?.credit_balance || 0;
  const [mode, setMode] = useState("transcript");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");
  const [tokenNotice, setTokenNotice] = useState("");
  const [transcriptForm, setTranscriptForm] = useState([]);
  const [testimonialForm, setTestimonialForm] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const selectedStudent = students.find((student) => student.id === selectedStudentId) || students[0] || null;
  const eligibleStudents = students.filter((student) => student.is_testimonial_eligible);

  useEffect(() => {
    if (!selectedStudentId && students[0]) {
      setSelectedStudentId(students[0].id);
    }
  }, [selectedStudentId, students]);

  useEffect(() => {
    if (mode === "testimonial" && selectedStudent && !selectedStudent.is_testimonial_eligible) {
      const firstEligible = eligibleStudents[0];
      if (firstEligible) {
        setSelectedStudentId(firstEligible.id);
      }
    }
  }, [eligibleStudents, mode, selectedStudent]);

  useEffect(() => {
    let active = true;
    setDetail(null);
    setActionError("");
    setActionSuccess("");
    setTokenNotice("");
    if (!selectedStudent) {
      return () => {
        active = false;
      };
    }
    if (mode === "testimonial" && !selectedStudent.is_testimonial_eligible) {
      setActionError("Testimonials are strictly available only for JSS3 and SSS3 students.");
      return () => {
        active = false;
      };
    }
    setDetailLoading(true);
    const loader = mode === "testimonial" ? onLoadTestimonial : onLoadTranscript;
    loader(selectedStudent.id)
      .then((payload) => {
        if (!active) return;
        const nextDetail = mode === "testimonial" ? payload : payload?.transcript;
        setDetail(nextDetail);
        if (mode === "testimonial") {
          setTestimonialForm(payload?.testimonial || {});
        } else {
          setTranscriptForm(transcriptRowsFromDetail(nextDetail));
        }
        if (payload?.token_used) {
          setTokenNotice(payload.message || `${mode} generated.`);
        }
      })
      .catch((loadError) => {
        if (active) {
          let errorMsg = loadError.message || "Could not load document.";
          setActionError(errorMsg);
        }
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [mode, onLoadTestimonial, onLoadTranscript, selectedStudent]);

  useEffect(() => {
    if (!tokenNotice) return undefined;
    const timeoutId = window.setTimeout(() => setTokenNotice(""), 4500);
    return () => window.clearTimeout(timeoutId);
  }, [tokenNotice]);

  const handleSave = async (event) => {
    event.preventDefault();
    if (!selectedStudent) return;
    setIsSaving(true);
    setActionError("");
    setActionSuccess("");
    try {
      if (mode === "testimonial") {
        const payload = await onSaveTestimonial(selectedStudent.id, testimonialForm);
        setDetail(payload);
        setTestimonialForm(payload?.testimonial || {});
        setActionSuccess("Testimonial details saved.");
      } else {
        const payload = await onSaveTranscript(selectedStudent.id, { scores: transcriptForm });
        const nextTranscript = payload?.transcript || null;
        setDetail(nextTranscript);
        setTranscriptForm(transcriptRowsFromDetail(nextTranscript));
        setActionSuccess("Transcript details saved.");
      }
    } catch (saveError) {
      setActionError(saveError.message || `Could not save ${mode}.`);
    } finally {
      setIsSaving(false);
    }
  };

  const documentId = mode === "testimonial" ? "schooldom-testimonial-document" : "schooldom-transcript-document";
  const documentTitle = mode === "testimonial" ? "Student Testimonial" : "Student Transcript";
  const filePrefix = mode === "testimonial" ? "testimonial" : "transcript";

  const loadGeneratedDocument = async () => {
    if (!selectedStudent) {
      throw new Error("Select a student before generating a document.");
    }
    const loader = mode === "testimonial" ? onLoadTestimonial : onLoadTranscript;
    const payload = await loader(selectedStudent.id, { generate: true });
    const nextDetail = mode === "testimonial" ? payload : payload?.transcript;
    setDetail(nextDetail);
    if (mode === "testimonial") {
      setTestimonialForm(payload?.testimonial || {});
    } else {
      setTranscriptForm(transcriptRowsFromDetail(nextDetail));
    }
    if (payload?.token_used) {
      setTokenNotice(payload.message || `${mode} generated.`);
    }
    await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
    return nextDetail;
  };

  const handlePrintPdf = async () => {
    setActionError("");
    setActionSuccess("");
    setIsGenerating(true);
    try {
      await loadGeneratedDocument();
      openPrintableDocument(documentId, documentTitle);
    } catch (printError) {
      setActionError(printError.message || `Could not generate ${mode}.`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadPng = async () => {
    setActionError("");
    setActionSuccess("");
    setIsGenerating(true);
    try {
      await loadGeneratedDocument();
      await downloadPrintablePng(documentId, documentFileName(filePrefix, selectedStudent), documentTitle);
    } catch (downloadError) {
      setActionError(downloadError.message || `Could not generate ${mode} PNG.`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section className="screen-grid document-workspace">
      <div className="screen-hero document-hero">
        <h2>Transcripts & Testimonials</h2>
        <p>Generate official student transcripts and terminal-class testimonials with printable school document styling.</p>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />
      {data ? (
        <>
          <section className="metric-grid">
            <MetricCard label="Students" value={summary.total_students ?? students.length} trend="Available records" />
            <MetricCard label="Transcripts" value={summary.transcripts_ready ?? students.length} trend="Live academic history" />
            <MetricCard label="Testimonials" value={summary.testimonial_eligible ?? eligibleStudents.length} trend="JSS3 / SSS3 only" />
            <MetricCard 
              label="Available Tokens" 
              value={creditBalance ?? 0} 
              trend="Document generation is free"
            />
          </section>
          <section className="document-layout">
            <article className="app-panel document-controls">
              <div className="document-tabs">
                <button type="button" className={mode === "transcript" ? "active" : ""} onClick={() => setMode("transcript")}>Transcript</button>
                <button type="button" className={mode === "testimonial" ? "active" : ""} onClick={() => setMode("testimonial")}>Testimonial</button>
              </div>
              <label className="panel-field">
                Student
                <select value={selectedStudent?.id || ""} onChange={(event) => setSelectedStudentId(event.target.value)}>
                  {(mode === "testimonial" ? eligibleStudents : students).map((student) => (
                    <option
                      key={student.id}
                      value={student.id}
                      title={`${student.name} - ${student.class_name || "Class not set"} - ${student.student_id || student.admission_number || ""}`}
                    >
                      {student.name} - {student.student_id || student.admission_number || "No ID"}
                    </option>
                  ))}
                </select>
                {selectedStudent ? (
                  <small className="field-note">
                    {selectedStudent.class_name || "Class not set"} - {selectedStudent.student_id || selectedStudent.admission_number || "No ID"}
                  </small>
                ) : null}
              </label>
              {mode === "testimonial" ? (
                <form className="panel-form testimonial-editor" onSubmit={handleSave}>
                  <div className="panel-form-grid">
                    {[
                      ["class_of_admission", "Class of Admission"],
                      ["date_of_leaving", "Date of Leaving", "date"],
                      ["class_of_leaving", "Class of Leaving"],
                      ["reason_for_leaving", "Reason for Leaving"],
                      ["educational_attainment", "Educational Attainment"],
                      ["subjects_offered", "Subjects Offered", "textarea"],
                      ["co_curricular_activities", "Co-Curricular Activities"],
                      ["prizes_and_honors", "Prizes and Honors Won"],
                      ["office_held", "Office Held"],
                      ["administrator_remarks", "Principal / Administrator Remarks", "textarea"],
                      ["issue_date", "Date", "date"],
                      ["principal_name", "Principal / Administrator Name"],
                    ].map(([field, label, type]) => (
                      <label key={field} className={`panel-field ${type === "textarea" ? "full" : ""}`}>
                        {label}
                        {type === "textarea" ? (
                          <textarea value={testimonialForm[field] || ""} onChange={(event) => setTestimonialForm((prev) => ({ ...prev, [field]: event.target.value }))} rows="3" />
                        ) : (
                          <input type={type || "text"} value={String(testimonialForm[field] || "").slice(0, type === "date" ? 10 : undefined)} onChange={(event) => setTestimonialForm((prev) => ({ ...prev, [field]: event.target.value }))} />
                        )}
                      </label>
                    ))}
                  </div>
                  <div className="panel-form-actions">
                    <button type="submit" disabled={isSaving || detailLoading}>{isSaving ? "Saving..." : "Save Testimonial"}</button>
                  </div>
                </form>
              ) : (
                <form className="panel-form transcript-editor" onSubmit={handleSave}>
                  <div className="document-note-box">
                    <strong>Edit transcript scores</strong>
                    <p>Update existing subject rows. Student bio, class history, sessions, and cumulative values refresh from saved records.</p>
                  </div>
                  {transcriptForm.length ? (
                    <div className="transcript-edit-list">
                      {transcriptForm.map((row, index) => (
                        <div key={row.id || `${row.subject}-${index}`} className="transcript-edit-row">
                          <div>
                            <strong>{row.subject || "Subject"}</strong>
                            <small>{row.context}</small>
                          </div>
                          <label>
                            Score
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={row.score ?? ""}
                              onChange={(event) => setTranscriptForm((prev) => prev.map((item, itemIndex) => itemIndex === index ? { ...item, score: event.target.value } : item))}
                            />
                          </label>
                          <label>
                            Max
                            <input
                              type="number"
                              min="1"
                              step="0.01"
                              value={row.max_score ?? ""}
                              onChange={(event) => setTranscriptForm((prev) => prev.map((item, itemIndex) => itemIndex === index ? { ...item, max_score: event.target.value } : item))}
                            />
                          </label>
                          <label>
                            Grade
                            <input
                              value={row.grade || ""}
                              onChange={(event) => setTranscriptForm((prev) => prev.map((item, itemIndex) => itemIndex === index ? { ...item, grade: event.target.value.toUpperCase() } : item))}
                            />
                          </label>
                          <label className="wide">
                            Remark
                            <input
                              value={row.remark || ""}
                              onChange={(event) => setTranscriptForm((prev) => prev.map((item, itemIndex) => itemIndex === index ? { ...item, remark: event.target.value } : item))}
                            />
                          </label>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="panel-empty">No transcript score rows are available to edit yet.</p>
                  )}
                  <div className="panel-form-actions">
                    <button type="submit" disabled={isSaving || detailLoading || transcriptForm.length === 0}>{isSaving ? "Saving..." : "Save Transcript"}</button>
                  </div>
                </form>
              )}
            </article>
            <article className="app-panel document-preview-panel">
              <div className="panel-head">
                <h3>Preview</h3>
                <small>{detailLoading ? "Loading document..." : mode === "testimonial" ? "JSS3 / SSS3 only" : "Academic history"}</small>
              </div>
              {tokenNotice ? <div className="token-usage-toast" role="status">{tokenNotice}</div> : null}
              {actionError ? <p className="form-feedback error">{actionError}</p> : null}
              {actionSuccess ? <p className="form-feedback success">{actionSuccess}</p> : null}
              <div className="document-preview-scroll">
                {detailLoading ? (
                  <p className="panel-empty">Preparing document...</p>
                ) : mode === "testimonial" ? (
                  <TestimonialPreview detail={detail} school={data?.school || school} />
                ) : (
                  <TranscriptPreview transcript={detail} school={data?.school || school} />
                )}
              </div>
              <div className="panel-form-actions document-actions">
                <button type="button" onClick={handlePrintPdf} disabled={!detail || detailLoading || isGenerating}>
                  {isGenerating ? "Generating..." : `Generate ${mode === "testimonial" ? "Testimonial" : "Transcript"} PDF / Print`}
                </button>
                <button type="button" className="table-action" onClick={handleDownloadPng} disabled={!detail || detailLoading || isGenerating}>
                  Generate PNG
                </button>
              </div>
            </article>
          </section>
        </>
      ) : null}
    </section>
  );
}

const SUPPORT_TICKET_CATEGORIES = [
  { value: "technical_issue", label: "Technical Issue" },
  { value: "account_issue", label: "Account Issue" },
  { value: "billing_issue", label: "Billing Issue" },
  { value: "feature_request", label: "Feature Request" },
  { value: "general_inquiry", label: "General Inquiry" },
];

export function SupportCenterPanel({ school, tickets = [], canEdit, onSubmit }) {
  const [form, setForm] = useState({
    category: "technical_issue",
    subject: "",
    description: "",
    attachment: null,
  });
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [localTickets, setLocalTickets] = useState([]);

  useEffect(() => {
    setLocalTickets(Array.isArray(tickets) ? tickets : []);
  }, [tickets]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canEdit || submitting) return;
    setSubmitting(true);
    setFeedback("");
    setFormError("");
    try {
      const result = await onSubmit?.({
        ...form,
        subject: form.subject.trim(),
        description: form.description.trim(),
      });
      if (result?.ticket) {
        setLocalTickets((current) => [result.ticket, ...current.filter((item) => item.id !== result.ticket.id)].slice(0, 8));
      }
      setForm({ category: "technical_issue", subject: "", description: "", attachment: null });
      setFeedback(result?.message || "Support ticket submitted.");
    } catch (actionError) {
      setFormError(actionError.message || "Could not submit support ticket.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <article className="app-panel settings-support-center">
      <div className="settings-support-head">
        <div>
          <h3>SchoolDom Support Center</h3>
          <p>Submit a ticket to {SUPPORT_EMAIL}; SchoolDom will track updates here and notify your school by email.</p>
        </div>
        <span className="status-pill published">{localTickets.length} tracked</span>
      </div>

      <div className="support-school-details">
        <div><span>School</span><strong>{school.name || "-"}</strong></div>
        <div><span>Code</span><strong>{school.school_code || "-"}</strong></div>
        <div><span>Email</span><strong>{school.email || "-"}</strong></div>
        <div><span>Phone</span><strong>{school.phone || "-"}</strong></div>
      </div>

      <form className="panel-form support-ticket-form" onSubmit={handleSubmit}>
        <div className="panel-form-grid">
          <label className="panel-field">
            Category
            <select
              value={form.category}
              onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
              disabled={!canEdit || submitting}
            >
              {SUPPORT_TICKET_CATEGORIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            Subject
            <input
              value={form.subject}
              onChange={(event) => setForm((current) => ({ ...current, subject: event.target.value }))}
              disabled={!canEdit || submitting}
              placeholder="Brief summary"
            />
          </label>
          <label className="panel-field full">
            Description
            <textarea
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              disabled={!canEdit || submitting}
              placeholder="Tell us what happened, who is affected, and any steps you tried."
            />
          </label>
          <label className="panel-field full">
            Attachment
            <input
              type="file"
              onChange={(event) => setForm((current) => ({ ...current, attachment: event.target.files?.[0] || null }))}
              disabled={!canEdit || submitting}
            />
          </label>
        </div>
        {formError ? <p className="form-feedback error">{formError}</p> : null}
        {feedback ? <p className="form-feedback success">{feedback}</p> : null}
        <div className="panel-form-actions">
          <button type="submit" disabled={!canEdit || submitting}>
            {submitting ? "Submitting..." : "Submit Ticket"}
          </button>
        </div>
      </form>

      <div className="support-ticket-list">
        <h4>Ticket Status Tracking</h4>
        {localTickets.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {localTickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td>{ticket.subject}</td>
                    <td>{ticket.category_label || ticket.category}</td>
                    <td><span className={`support-status ${ticket.status || "open"}`}>{ticket.status_label || ticket.status || "Open"}</span></td>
                    <td>{formatDate(ticket.updated_at || ticket.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="panel-empty">No support tickets submitted yet.</p>
        )}
      </div>
    </article>
  );
}

function AdminLoanApplicationScreen({ data = {}, loading, error, onRetry, onSubmit }) {
  const [form, setForm] = useState({
    amount_requested: "",
    purpose: "",
    repayment_period_months: "",
    additional_notes: "",
    requester_email: "",
    requester_phone: "",
    supporting_document: null,
  });
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const loans = data?.loans || [];

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setFeedback("");
    setFormError("");
    if (!form.amount_requested || Number(form.amount_requested) <= 0) {
      setFormError("Enter a loan amount greater than zero.");
      return;
    }
    if (form.purpose.trim().length < 3) {
      setFormError("Tell us the purpose of the loan.");
      return;
    }
    if (!form.repayment_period_months || Number(form.repayment_period_months) <= 0) {
      setFormError("Enter a repayment period of at least 1 month.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await onSubmit?.({
        ...form,
        purpose: form.purpose.trim(),
        additional_notes: form.additional_notes.trim(),
      });
      setFeedback(result?.message || "Loan application submitted.");
      setForm({
        amount_requested: "",
        purpose: "",
        repayment_period_months: "",
        additional_notes: "",
        requester_email: "",
        requester_phone: "",
        supporting_document: null,
      });
    } catch (actionError) {
      setFormError(actionError.message || "Could not submit loan application.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="screen-grid loan-application-screen">
      <div className="screen-hero">
        <h2>Loan Application</h2>
        <p>Apply for financing from SchoolDom. Applications are reviewed manually and you'll be notified by email.</p>
      </div>

      <ScreenState loading={loading && !loans.length} error={error} onRetry={onRetry} />

      <article className="app-panel">
        <div className="panel-head">
          <h3>Apply for a loan</h3>
          <small>Give us the details of the financing your school needs.</small>
        </div>
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Amount requested
              <input
                type="number"
                min="1"
                step="0.01"
                value={form.amount_requested}
                onChange={(event) => setForm((current) => ({ ...current, amount_requested: event.target.value }))}
                disabled={submitting}
                placeholder="e.g. 500000"
              />
            </label>
            <label className="panel-field">
              Repayment period (months)
              <input
                type="number"
                min="1"
                step="1"
                value={form.repayment_period_months}
                onChange={(event) => setForm((current) => ({ ...current, repayment_period_months: event.target.value }))}
                disabled={submitting}
                placeholder="e.g. 12"
              />
            </label>
            <label className="panel-field full">
              Purpose
              <input
                value={form.purpose}
                onChange={(event) => setForm((current) => ({ ...current, purpose: event.target.value }))}
                disabled={submitting}
                placeholder="What is the loan for?"
              />
            </label>
            <label className="panel-field">
              Contact email
              <input
                type="email"
                value={form.requester_email}
                onChange={(event) => setForm((current) => ({ ...current, requester_email: event.target.value }))}
                disabled={submitting}
                placeholder="Optional - defaults to your account email"
              />
            </label>
            <label className="panel-field">
              Contact phone
              <input
                value={form.requester_phone}
                onChange={(event) => setForm((current) => ({ ...current, requester_phone: event.target.value }))}
                disabled={submitting}
                placeholder="Optional - defaults to school phone"
              />
            </label>
            <label className="panel-field full">
              Additional notes
              <textarea
                value={form.additional_notes}
                onChange={(event) => setForm((current) => ({ ...current, additional_notes: event.target.value }))}
                disabled={submitting}
                placeholder="Anything else we should know about this request."
              />
            </label>
            <label className="panel-field full">
              Supporting document
              <input
                type="file"
                onChange={(event) => setForm((current) => ({ ...current, supporting_document: event.target.files?.[0] || null }))}
                disabled={submitting}
              />
            </label>
          </div>
          {formError ? <p className="form-feedback error">{formError}</p> : null}
          {feedback ? <p className="form-feedback success">{feedback}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Application"}
            </button>
          </div>
        </form>
      </article>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Your loan applications</h3>
          <small>Track the status of loans you've applied for.</small>
        </div>
        {loans.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Amount</th>
                  <th>Purpose</th>
                  <th>Repayment</th>
                  <th>Status</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {loans.map((loan) => (
                  <tr key={loan.id}>
                    <td>{loan.amount_requested}</td>
                    <td>{loan.purpose}</td>
                    <td>{loan.repayment_period_months} months</td>
                    <td><span className={`support-status ${loan.status || "pending"}`}>{loan.status_label || loan.status || "Pending"}</span></td>
                    <td>{formatDate(loan.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="panel-empty">No loan applications submitted yet.</p>
        )}
      </article>
    </section>
  );
}

function AdminSettingsScreen({
  data,
  user,
  loading,
  error,
  onRetry,
  onSave,
  onRequestAccountDeletion,
  onCancelAccountDeletion,
  themePreference,
  onThemeChange,
  countries = [],
}) {
  const school = data?.school || {};
  const director = data?.director || {};
  const canEdit = Boolean(data?.can_edit);
  const [name, setName] = useState("");
  const [motto, setMotto] = useState("");
  const [country, setCountry] = useState("NG");
  const [schoolState, setSchoolState] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [studentRules, setStudentRules] = useState("");
  const [staffRules, setStaffRules] = useState("");
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState("");
  const [cacRegisteredName, setCacRegisteredName] = useState("");
  const [ministryApprovalNumber, setMinistryApprovalNumber] = useState("");
  const [cacCertificateFile, setCacCertificateFile] = useState(null);
  const [cacCertificateUrl, setCacCertificateUrl] = useState("");
  const [entrancePhotoFile, setEntrancePhotoFile] = useState(null);
  const [entrancePhotoPreview, setEntrancePhotoPreview] = useState("");
  const [proofOfAddressFile, setProofOfAddressFile] = useState(null);
  const [proofOfAddressUrl, setProofOfAddressUrl] = useState("");
  const [directorAddress, setDirectorAddress] = useState("");
  const [directorIdType, setDirectorIdType] = useState("");
  const [directorProofOfAddressFile, setDirectorProofOfAddressFile] = useState(null);
  const [directorProofOfAddressUrl, setDirectorProofOfAddressUrl] = useState("");
  const [directorIdDocumentFile, setDirectorIdDocumentFile] = useState(null);
  const [directorIdDocumentUrl, setDirectorIdDocumentUrl] = useState("");
  const [directorPassportFile, setDirectorPassportFile] = useState(null);
  const [directorPassportPreview, setDirectorPassportPreview] = useState("");
  const [adminFirstName, setAdminFirstName] = useState("");
  const [adminLastName, setAdminLastName] = useState("");
  const [academicYearName, setAcademicYearName] = useState("");
  const [academicYearStart, setAcademicYearStart] = useState("");
  const [academicYearEnd, setAcademicYearEnd] = useState("");
  const [termName, setTermName] = useState("");
  const [termStart, setTermStart] = useState("");
  const [termEnd, setTermEnd] = useState("");
  const [activityCalendar, setActivityCalendar] = useState([]);
  const today = useMemo(() => new Date(), []);
  const todayDateValue = useMemo(() => today.toISOString().slice(0, 10), [today]);
  const [calendarMonth, setCalendarMonth] = useState(String(today.getMonth() + 1));
  const [calendarYear, setCalendarYear] = useState(String(today.getFullYear()));
  const [activityDraft, setActivityDraft] = useState({
    title: "",
    activity_date: todayDateValue,
    end_date: "",
    description: "",
    color: "#2563EB",
  });
  const [activityToast, setActivityToast] = useState(null);
  const [pendingActivityRemoval, setPendingActivityRemoval] = useState(null);
  const [deleteAccountPromptOpen, setDeleteAccountPromptOpen] = useState(false);
  const [deleteAccountBusy, setDeleteAccountBusy] = useState(false);
  const [deleteAccountFeedback, setDeleteAccountFeedback] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    setName(school.name || "");
    setMotto((current) => school.motto || school.tagline || current || "");
    setCountry(school.country || "NG");
    setSchoolState(school.state || "");
    setEmail(school.email || "");
    setPhone(school.phone || "");
    setAddress(school.address || "");
    setStudentRules((current) => school.student_rules || school.studentRules || current || "");
    setStaffRules((current) => school.staff_rules || school.staffRules || current || "");
    setLogoPreview(school.logo || "");
    setLogoFile(null);
    setCacRegisteredName(school.cac_registered_name || "");
    setMinistryApprovalNumber(school.ministry_approval_number || "");
    setCacCertificateUrl(school.cac_certificate || "");
    setCacCertificateFile(null);
    setEntrancePhotoPreview(school.entrance_photo || "");
    setEntrancePhotoFile(null);
    setProofOfAddressUrl(school.proof_of_address || "");
    setProofOfAddressFile(null);
    setDirectorAddress(director.address || "");
    setDirectorIdType(director.id_type || "");
    setDirectorProofOfAddressUrl(director.proof_of_address || "");
    setDirectorProofOfAddressFile(null);
    setDirectorIdDocumentUrl(director.id_document || "");
    setDirectorIdDocumentFile(null);
    setDirectorPassportPreview(director.passport_photo || "");
    setDirectorPassportFile(null);
    setAdminFirstName(director.first_name || user?.first_name || "");
    setAdminLastName(director.last_name || user?.last_name || "");
    setAcademicYearName(data?.academic_year?.name || "");
    setAcademicYearStart((data?.academic_year?.start_date || "").slice(0, 10));
    setAcademicYearEnd((data?.academic_year?.end_date || "").slice(0, 10));
    setTermName(data?.term?.name || "");
    setTermStart((data?.term?.start_date || "").slice(0, 10));
    setTermEnd((data?.term?.end_date || "").slice(0, 10));
  }, [
    data?.academic_year?.id, data?.academic_year?.name, data?.academic_year?.start_date, data?.academic_year?.end_date,
    data?.term?.id, data?.term?.name, data?.term?.start_date, data?.term?.end_date,
    school.address, school.email, school.logo, school.motto, school.name, school.phone,
    school.staffRules, school.staff_rules, school.studentRules, school.student_rules, school.tagline,
    school.cac_registered_name, school.cac_certificate, school.entrance_photo, school.proof_of_address, school.ministry_approval_number,
    director.address, director.id_type, director.proof_of_address, director.id_document, director.passport_photo,
  ]);

  useEffect(() => {
    setActivityCalendar(
      (data?.activity_calendar || []).map((item) => ({
        id: item.id || `activity-${Date.now()}-${Math.random()}`,
        month: String(item.month || new Date().getMonth() + 1),
        year: item.year ? String(item.year) : "",
        title: item.title || "",
        activity_date: (item.activity_date || "").slice(0, 10),
        end_date: (item.end_date || "").slice(0, 10),
        description: item.description || "",
        color: item.color || "#2563EB",
      }))
    );
  }, [data?.activity_calendar]);

  useEffect(() => {
    if (!activityToast) {
      return undefined;
    }
    const timer = window.setTimeout(() => setActivityToast(null), 2800);
    return () => window.clearTimeout(timer);
  }, [activityToast]);

  const buildSettingsPayload = useCallback(
    (calendarItems = activityCalendar) => ({
      name: name.trim(),
      motto: motto.trim(),
      tagline: motto.trim(),
      country,
      state: schoolState.trim(),
      email: email.trim(),
      phone: phone.trim(),
      address: address.trim(),
      student_rules: studentRules.trim(),
      staff_rules: staffRules.trim(),
      logo: logoFile,
      cac_registered_name: cacRegisteredName.trim(),
      ministry_approval_number: ministryApprovalNumber.trim(),
      cac_certificate: cacCertificateFile,
      entrance_photo: entrancePhotoFile,
      proof_of_address: proofOfAddressFile,
      admin_first_name: adminFirstName.trim(),
      admin_last_name: adminLastName.trim(),
      director_address: directorAddress.trim(),
      director_id_type: directorIdType,
      director_proof_of_address: directorProofOfAddressFile,
      director_id_document: directorIdDocumentFile,
      profile_picture: directorPassportFile,
      academic_year_name: academicYearName.trim(),
      academic_year_start_date: academicYearStart,
      academic_year_end_date: academicYearEnd,
      term_name: termName.trim(),
      term_start_date: termStart,
      term_end_date: termEnd,
      activity_calendar: JSON.stringify(
        calendarItems
          .filter((item) => item.title.trim())
          .map((item) => ({
            month: Number(item.month || 0),
            year: item.year ? Number(item.year) : null,
            title: item.title.trim(),
            activity_date: item.activity_date || null,
            end_date: item.end_date || null,
            description: item.description.trim(),
            color: item.color || "#2563EB",
          }))
      ),
    }),
    [
      academicYearEnd, academicYearName, academicYearStart, activityCalendar, address, adminFirstName, adminLastName, country, email, logoFile, motto, name, phone, schoolState, staffRules, studentRules, termEnd, termName, termStart,
      cacRegisteredName, ministryApprovalNumber, cacCertificateFile, entrancePhotoFile, proofOfAddressFile,
      directorAddress, directorIdType, directorProofOfAddressFile, directorIdDocumentFile, directorPassportFile,
    ]
  );

  const selectCalendarDate = (dateValue) => {
    if (!dateValue) {
      setActivityDraft((current) => ({ ...current, activity_date: "" }));
      return;
    }
    const nextDate = new Date(`${dateValue}T00:00:00`);
    setCalendarMonth(String(nextDate.getMonth() + 1));
    setCalendarYear(String(nextDate.getFullYear()));
    setActivityDraft((current) => ({ ...current, activity_date: dateValue }));
  };

  const addActivity = async () => {
    const title = activityDraft.title.trim();
    if (!title) {
      setFormError("Add the activity title before adding it to the calendar.");
      return;
    }
    if (activityDraft.activity_date && activityDraft.end_date && activityDraft.end_date < activityDraft.activity_date) {
      setFormError("Activity end date cannot be before the start date.");
      return;
    }
    const selectedDate = activityDraft.activity_date ? new Date(`${activityDraft.activity_date}T00:00:00`) : null;
    const month = selectedDate ? selectedDate.getMonth() + 1 : Number(calendarMonth || today.getMonth() + 1);
    const year = selectedDate ? selectedDate.getFullYear() : Number(calendarYear || today.getFullYear());
    const nextActivity = {
      id: `new-${Date.now()}`,
      month: String(month),
      year: String(year),
      title,
      activity_date: activityDraft.activity_date,
      end_date: activityDraft.end_date,
      description: activityDraft.description,
      color: activityDraft.color || "#2563EB",
    };
    const nextCalendar = [...activityCalendar, nextActivity];
    setIsSaving(true);
    setFeedback("");
    setFormError("");
    setActivityCalendar(nextCalendar);
    try {
      const result = await onSave(buildSettingsPayload(nextCalendar));
      setFeedback(result?.message || "School settings updated.");
      setActivityToast({ title, date: activityDraft.activity_date });
      setActivityDraft((current) => ({
        ...current,
        title: "",
        description: "",
        end_date: "",
      }));
    } catch (actionError) {
      setActivityCalendar(activityCalendar);
      setFormError(actionError.message || "Could not save activity.");
    } finally {
      setIsSaving(false);
    }
  };

  const displayActivityDate = (value) => {
    if (!value) {
      return "-";
    }
    try {
      return new Date(`${value}T00:00:00`).toLocaleDateString([], {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch {
      return String(value);
    }
  };

  const confirmRemoveActivity = async () => {
    if (!pendingActivityRemoval) {
      return;
    }
    const nextCalendar = activityCalendar.filter((item) => item.id !== pendingActivityRemoval.id);
    setIsSaving(true);
    setFeedback("");
    setFormError("");
    setActivityCalendar(nextCalendar);
    try {
      const result = await onSave(buildSettingsPayload(nextCalendar));
      setFeedback(result?.message || "Activity removed.");
      setPendingActivityRemoval(null);
    } catch (actionError) {
      setActivityCalendar(activityCalendar);
      setFormError(actionError.message || "Could not remove activity.");
    } finally {
      setIsSaving(false);
    }
  };

  const calendarDays = useMemo(() => {
    const month = Number(calendarMonth || today.getMonth() + 1);
    const year = Number(calendarYear || today.getFullYear());
    const firstDate = new Date(year, month - 1, 1);
    const daysInMonth = new Date(year, month, 0).getDate();
    const leadingDays = firstDate.getDay();
    const cells = [];
    for (let index = 0; index < leadingDays; index += 1) {
      cells.push(null);
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateValue = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      cells.push({
        day,
        dateValue,
        activities: activityCalendar.filter((item) => {
          const itemMonth = Number(item.month || 0);
          const itemYear = Number(item.year || year);
          if (item.activity_date) {
            return item.activity_date === dateValue;
          }
          return day === 1 && itemMonth === month && itemYear === year;
        }),
      });
    }
    return cells;
  }, [activityCalendar, calendarMonth, calendarYear, today]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canEdit) {
      return;
    }
    setFeedback("");
    setFormError("");
    const yearTouched = academicYearName.trim() || academicYearStart || academicYearEnd;
    if (yearTouched && !(academicYearName.trim() && academicYearStart && academicYearEnd)) {
      setFormError("Provide the academic year name, start date, and end date together to save it.");
      return;
    }
    const termTouched = termName.trim() || termStart || termEnd;
    if (termTouched && !(termName.trim() && termStart && termEnd)) {
      setFormError("Provide the term name, start date, and end date together to save it.");
      return;
    }
    setIsSaving(true);
    try {
      const result = await onSave(buildSettingsPayload());
      setFeedback(result?.message || "School settings updated.");
    } catch (actionError) {
      setFormError(actionError.message || "Could not update settings.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogoChange = (event) => {
    const file = event.target.files?.[0] || null;
    setLogoFile(file);
    setLogoPreview(file ? URL.createObjectURL(file) : school.logo || "");
  };

  const handleEntrancePhotoChange = (event) => {
    const file = event.target.files?.[0] || null;
    setEntrancePhotoFile(file);
    setEntrancePhotoPreview(file ? URL.createObjectURL(file) : school.entrance_photo || "");
  };

  const handleDirectorPassportChange = (event) => {
    const file = event.target.files?.[0] || null;
    setDirectorPassportFile(file);
    setDirectorPassportPreview(file ? URL.createObjectURL(file) : director.passport_photo || "");
  };

  const handleThemeSelect = (nextTheme) => {
    if (nextTheme !== "light" && nextTheme !== "dark") {
      return;
    }
    onThemeChange?.(nextTheme);
  };

  const accountDeletion = data?.account_deletion || {};
  const accountDeletionDate = accountDeletion.scheduled_for ? formatDate(accountDeletion.scheduled_for) : "";

  const requestAccountDeletion = async () => {
    setDeleteAccountBusy(true);
    setDeleteAccountFeedback("");
    setFormError("");
    try {
      const result = await onRequestAccountDeletion?.();
      setDeleteAccountFeedback(result?.message || "Account deletion requested.");
      setDeleteAccountPromptOpen(false);
    } catch (actionError) {
      setFormError(actionError.message || "Could not request account deletion.");
    } finally {
      setDeleteAccountBusy(false);
    }
  };

  const cancelAccountDeletion = async () => {
    setDeleteAccountBusy(true);
    setDeleteAccountFeedback("");
    setFormError("");
    try {
      const result = await onCancelAccountDeletion?.();
      setDeleteAccountFeedback(result?.message || "Account deletion request cancelled.");
    } catch (actionError) {
      setFormError(actionError.message || "Could not cancel account deletion request.");
    } finally {
      setDeleteAccountBusy(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Settings</h2>
        <p>Update school profile and contact details.</p>
        <span className="role-chip">{userRoleLabel(user)}</span>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
        <article className="app-panel">
          <div className="theme-switcher">
            <p className="field-note">Interface Theme</p>
            <div className="segmented-control">
              <button
                type="button"
className={themePreference === "light" ? "active" : ""}
onClick={() => handleThemeSelect("light")}
              >
                Light
              </button>
                                    <button
                        type="button"
                        className={themePreference === "dark" ? "active" : ""}
                onClick={() => handleThemeSelect("dark")}
              >
                Dark
                      </button>
                    </div>
                    </div>

          <form className="panel-form" onSubmit={handleSubmit}>
            <div className="panel-form-grid">
              <div className="settings-logo-field full">
                <div className="settings-logo-preview">
                  {logoPreview ? <img src={logoPreview} alt={`${name || "School"} logo`} /> : <span>{resolveSchoolBrand({ name }).initials}</span>}
                </div>
                <label className="panel-field">
                  School Logo
                  <input type="file" accept="image/*" onChange={handleLogoChange} disabled={!canEdit || isSaving} />
                </label>
              </div>
              <label className="panel-field">
                School Name
                <input value={name} onChange={(event) => setName(event.target.value)} disabled={!canEdit || isSaving} />
              </label>
              <label className="panel-field">
                School Code
                <input value={school.school_code || ""} disabled />
              </label>
              <label className="panel-field full">
                School Motto / Tagline
                <input value={motto} onChange={(event) => setMotto(event.target.value)} placeholder="e.g., Knowledge and Character" disabled={!canEdit || isSaving} />
              </label>
              <label className="panel-field">
                Country
                <select value={country} onChange={(event) => setCountry(event.target.value)} disabled={!canEdit || isSaving || countries.length === 0}>
                  {countries.length === 0 ? (
                    <option value={country}>{country || "Loading..."}</option>
                  ) : (
                    countries.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.flag} {c.name}
                      </option>
                    ))
                  )}
                </select>
              </label>
              <label className="panel-field">
                State / Province
                <input value={schoolState} onChange={(event) => setSchoolState(event.target.value)} placeholder="e.g., Lagos State" disabled={!canEdit || isSaving} />
              </label>
              <label className="panel-field">
                Email
                <input value={email} onChange={(event) => setEmail(event.target.value)} disabled={!canEdit || isSaving} />
              </label>
              <label className="panel-field">
                Phone
                <PhoneCountryInput
                  countries={countries}
                  value={phone}
                  onChange={setPhone}
                  defaultCountryCode={country || "NG"}
                  disabled={!canEdit || isSaving}
                  placeholder="School phone number"
                />
              </label>
                        <label className="panel-field full">
                          Address
                          <textarea value={address} onChange={(event) => setAddress(event.target.value)} disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field full">
                          Student Rules & Regulations
                          <textarea
                            value={studentRules}
                            onChange={(event) => setStudentRules(event.target.value)}
                            placeholder="Write the rules and regulations students must follow."
                            rows="6"
                            disabled={!canEdit || isSaving}
                          />
                        </label>
                        <label className="panel-field full">
                          Staff Rules & Regulations
                          <textarea
                            value={staffRules}
                            onChange={(event) => setStaffRules(event.target.value)}
                            placeholder="Write the rules and regulations staff must follow."
                            rows="6"
                            disabled={!canEdit || isSaving}
                          />
                        </label>
                        <label className="panel-field">
                          Academic Year
                          <input value={academicYearName} onChange={(event) => setAcademicYearName(event.target.value)} placeholder="2026/2027" disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field">
                          Academic Year Start
                          <input type="date" value={academicYearStart} onChange={(event) => setAcademicYearStart(event.target.value)} disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field">
                          Academic Year End
                          <input type="date" value={academicYearEnd} onChange={(event) => setAcademicYearEnd(event.target.value)} disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field">
                          Active Term
                          <input value={termName} onChange={(event) => setTermName(event.target.value)} placeholder="First Term" disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field">
                          Term Start
                          <input type="date" value={termStart} onChange={(event) => setTermStart(event.target.value)} disabled={!canEdit || isSaving} />
                        </label>
                        <label className="panel-field">
                          Term End
                          <input type="date" value={termEnd} onChange={(event) => setTermEnd(event.target.value)} disabled={!canEdit || isSaving} />
                        </label>
                      </div>

                      <div className="settings-compliance-section">
                        <div className="panel-head">
                          <h3>School Compliance Details</h3>
                          <small>Provide your school's registration documents for verification.</small>
                        </div>
                        <div className="panel-form-grid">
                          <label className="panel-field">
                            School Name (as on CAC)
                            <input
                              value={cacRegisteredName}
                              onChange={(event) => setCacRegisteredName(event.target.value)}
                              placeholder="Exact name on your CAC certificate"
                              disabled={!canEdit || isSaving}
                            />
                          </label>
                          <label className="panel-field">
                            Ministry of Education Approval Number (if approved)
                            <input
                              value={ministryApprovalNumber}
                              onChange={(event) => setMinistryApprovalNumber(event.target.value)}
                              placeholder="Optional"
                              disabled={!canEdit || isSaving}
                            />
                          </label>
                          <label className="panel-field">
                            CAC Certificate
                            <input type="file" accept="image/*,.pdf" onChange={(event) => setCacCertificateFile(event.target.files?.[0] || null)} disabled={!canEdit || isSaving} />
                            {cacCertificateFile ? (
                              <span className="field-note">Selected: {cacCertificateFile.name}</span>
                            ) : cacCertificateUrl ? (
                              <a className="field-note" href={cacCertificateUrl} target="_blank" rel="noreferrer">View uploaded certificate</a>
                            ) : null}
                          </label>
                          <label className="panel-field">
                            Proof of Address (utility bill)
                            <input type="file" accept="image/*,.pdf" onChange={(event) => setProofOfAddressFile(event.target.files?.[0] || null)} disabled={!canEdit || isSaving} />
                            {proofOfAddressFile ? (
                              <span className="field-note">Selected: {proofOfAddressFile.name}</span>
                            ) : proofOfAddressUrl ? (
                              <a className="field-note" href={proofOfAddressUrl} target="_blank" rel="noreferrer">View uploaded document</a>
                            ) : null}
                          </label>
                          <div className="settings-logo-field full">
                            <div className="settings-logo-preview">
                              {entrancePhotoPreview ? <img src={entrancePhotoPreview} alt="School entrance" /> : <span>No photo</span>}
                            </div>
                            <label className="panel-field">
                              Picture of School Entrance
                              <input type="file" accept="image/*" onChange={handleEntrancePhotoChange} disabled={!canEdit || isSaving} />
                            </label>
                          </div>
                        </div>
                      </div>

                      <div className="settings-compliance-section">
                        <div className="panel-head">
                          <h3>Director's Personal Information</h3>
                          <small>KYC details for the school's proprietor/director.</small>
                        </div>
                        <div className="panel-form-grid">
                          <label className="panel-field">
                            First Name
                            <input value={adminFirstName} onChange={(event) => setAdminFirstName(event.target.value)} disabled={!canEdit || isSaving} />
                          </label>
                          <label className="panel-field">
                            Last Name
                            <input value={adminLastName} onChange={(event) => setAdminLastName(event.target.value)} disabled={!canEdit || isSaving} />
                          </label>
                          <label className="panel-field">
                            Email
                            <input value={director.email || user?.email || ""} disabled />
                          </label>
                          <label className="panel-field full">
                            Address
                            <textarea value={directorAddress} onChange={(event) => setDirectorAddress(event.target.value)} disabled={!canEdit || isSaving} />
                          </label>
                          <label className="panel-field">
                            ID Card Type
                            <select value={directorIdType} onChange={(event) => setDirectorIdType(event.target.value)} disabled={!canEdit || isSaving}>
                              <option value="">Select ID type</option>
                              <option value="drivers_license">Driver's License</option>
                              <option value="nin">National ID (NIN)</option>
                              <option value="voters_card">Voter's Card</option>
                              <option value="passport">International Passport</option>
                            </select>
                          </label>
                          <label className="panel-field">
                            Upload ID Card
                            <input type="file" accept="image/*,.pdf" onChange={(event) => setDirectorIdDocumentFile(event.target.files?.[0] || null)} disabled={!canEdit || isSaving} />
                            {directorIdDocumentFile ? (
                              <span className="field-note">Selected: {directorIdDocumentFile.name}</span>
                            ) : directorIdDocumentUrl ? (
                              <a className="field-note" href={directorIdDocumentUrl} target="_blank" rel="noreferrer">View uploaded ID</a>
                            ) : null}
                          </label>
                          <label className="panel-field">
                            Proof of Address
                            <input type="file" accept="image/*,.pdf" onChange={(event) => setDirectorProofOfAddressFile(event.target.files?.[0] || null)} disabled={!canEdit || isSaving} />
                            {directorProofOfAddressFile ? (
                              <span className="field-note">Selected: {directorProofOfAddressFile.name}</span>
                            ) : directorProofOfAddressUrl ? (
                              <a className="field-note" href={directorProofOfAddressUrl} target="_blank" rel="noreferrer">View uploaded document</a>
                            ) : null}
                          </label>
                          <div className="settings-logo-field full">
                            <div className="settings-logo-preview">
                              {directorPassportPreview ? <img src={directorPassportPreview} alt="Director passport" /> : <span>No photo</span>}
                            </div>
                            <label className="panel-field">
                              Upload Passport Photograph
                              <input type="file" accept="image/*" onChange={handleDirectorPassportChange} disabled={!canEdit || isSaving} />
                            </label>
                          </div>
                        </div>
                      </div>

                      <div className="settings-activity-calendar">
                        <div className="panel-head">
                          <div>
                            <h3>Activities Calendar</h3>
                            <small>Select a date or month, add the title, then save settings when the calendar looks right.</small>
                          </div>
                        </div>
                        <div className="activity-calendar-workspace">
                          <section className="activity-calendar-board">
                            <div className="activity-calendar-toolbar">
                              <label className="panel-field">
                                Month
                                <select value={calendarMonth} onChange={(event) => setCalendarMonth(event.target.value)} disabled={!canEdit || isSaving}>
                                  {ACTIVITY_MONTHS.map((month, index) => (
                                    <option key={month} value={index + 1}>{month}</option>
                                  ))}
                                </select>
                              </label>
                              <label className="panel-field">
                                Year
                                <input type="number" min="1900" max="2200" value={calendarYear} onChange={(event) => setCalendarYear(event.target.value)} disabled={!canEdit || isSaving} />
                              </label>
                            </div>
                            <div className="activity-calendar-weekdays" aria-hidden="true">
                              {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}
                            </div>
                            <div className="activity-calendar-grid">
                              {calendarDays.map((day, index) => (
                                day ? (
                                  <button
                                    key={day.dateValue}
                                    type="button"
                                    className={`activity-calendar-day ${activityDraft.activity_date === day.dateValue ? "selected" : ""} ${day.activities.length ? "has-events" : ""}`}
                                    onClick={() => selectCalendarDate(day.dateValue)}
                                    disabled={!canEdit || isSaving}
                                  >
                                    <span>{day.day}</span>
                                    {day.activities.slice(0, 2).map((item) => (
                                      <small key={item.id} style={{ borderLeftColor: item.color || "#2563EB" }}>{item.title}</small>
                                    ))}
                                    {day.activities.length > 2 ? <em>+{day.activities.length - 2} more</em> : null}
                                  </button>
                                ) : (
                                  <span key={`blank-${index}`} className="activity-calendar-day blank" />
                                )
                              ))}
                            </div>
                          </section>
                          <section className="activity-calendar-composer">
                            <h4>Create activity</h4>
                            <label className="panel-field">
                              Activity Date
                              <input type="date" value={activityDraft.activity_date} onChange={(event) => selectCalendarDate(event.target.value)} disabled={!canEdit || isSaving} />
                            </label>
                            <label className="panel-field">
                              End Date
                              <input type="date" value={activityDraft.end_date} onChange={(event) => setActivityDraft((current) => ({ ...current, end_date: event.target.value }))} disabled={!canEdit || isSaving} />
                            </label>
                            <label className="panel-field">
                              Activity Title
                              <input value={activityDraft.title} onChange={(event) => setActivityDraft((current) => ({ ...current, title: event.target.value }))} placeholder="Inter-house sports, matriculation, excursion..." disabled={!canEdit || isSaving} />
                            </label>
                            <label className="panel-field">
                              Details
                              <textarea value={activityDraft.description} onChange={(event) => setActivityDraft((current) => ({ ...current, description: event.target.value }))} rows="3" disabled={!canEdit || isSaving} />
                            </label>
                            <label className="panel-field">
                              Color
                              <input type="color" value={activityDraft.color} onChange={(event) => setActivityDraft((current) => ({ ...current, color: event.target.value }))} disabled={!canEdit || isSaving} />
                            </label>
                            <button type="button" className="table-action activity-calendar-add" onClick={addActivity} disabled={!canEdit || isSaving}>
                              Add Activity
                            </button>
                          </section>
                        </div>
                        {activityCalendar.length ? (
                          <div className="activity-calendar-list">
                            {activityCalendar.map((activity) => (
                              <div key={activity.id} className="activity-calendar-row">
                                <div className="activity-row-accent" style={{ background: activity.color || "#2563EB" }} aria-hidden="true" />
                                <div className="activity-row-main">
                                  <h4>{activity.title}</h4>
                                  <p>{activity.description || "No details added."}</p>
                                  <div className="activity-row-dates">
                                    <span>Start: {displayActivityDate(activity.activity_date)}</span>
                                    <span>End: {displayActivityDate(activity.end_date)}</span>
                                  </div>
                                </div>
                                <div className="activity-row-actions">
                                  <button type="button" className="table-action danger" onClick={() => setPendingActivityRemoval(activity)} disabled={!canEdit || isSaving}>
                                    Remove
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="panel-empty">No monthly activities have been added yet.</p>
                        )}
                      </div>
                      {activityToast ? (
                        <div className="activity-add-toast" role="status" aria-live="polite">
                          <div className="activity-add-mark" aria-hidden="true"></div>
                          <div>
                            <strong>Activity added</strong>
                            <span>{activityToast.title}{activityToast.date ? ` - ${activityToast.date}` : ""}</span>
                          </div>
                        </div>
                      ) : null}
                      {pendingActivityRemoval ? (
                        <div className="activity-remove-dialog" role="dialog" aria-modal="true" aria-labelledby="activity-remove-title">
                          <article className="activity-remove-card">
                            <p className="activity-remove-kicker">Remove activity</p>
                            <h3 id="activity-remove-title">Remove {pendingActivityRemoval.title}?</h3>
                            <p>This will remove it from the school activities calendar and save the change immediately.</p>
                            <div className="activity-remove-summary">
                              <strong>{pendingActivityRemoval.title}</strong>
                              <span>
                                {displayActivityDate(pendingActivityRemoval.activity_date)} - {displayActivityDate(pendingActivityRemoval.end_date)}
                              </span>
                            </div>
                            <div className="activity-remove-actions">
                              <button type="button" className="table-action" onClick={() => setPendingActivityRemoval(null)} disabled={isSaving}>
                                Cancel
                              </button>
                              <button type="button" className="table-action danger" onClick={confirmRemoveActivity} disabled={isSaving}>
                                {isSaving ? "Removing..." : "Remove activity"}
                              </button>
                            </div>
                          </article>
                        </div>
                      ) : null}
                    {formError ? <p className="form-feedback error">{formError}</p> : null}
            {feedback ? <p className="form-feedback success">{feedback}</p> : null}
            <div className="panel-form-actions">
              <button type="submit" disabled={!canEdit || isSaving}>
                {isSaving ? "Saving..." : "Save Settings"}
              </button>
                  </div>
                </form>
          </article>
          <article className="app-panel danger-zone-panel">
            <div className="panel-head">
              <h3>Delete Account</h3>
              <small>
                {accountDeletion.requested
                  ? `Deletion is scheduled for ${accountDeletionDate || "within 30 days"}.`
                  : "Request permanent account deletion with a 30-day cancellation window."}
              </small>
            </div>
            <p className="field-note">
              Your account will be permanently deleted within 30 days after the request. You can cancel the request before then.
            </p>
            {deleteAccountFeedback ? <p className="form-feedback success">{deleteAccountFeedback}</p> : null}
            <div className="panel-form-actions">
              {accountDeletion.requested ? (
                <button type="button" className="table-action" onClick={cancelAccountDeletion} disabled={deleteAccountBusy || !onCancelAccountDeletion}>
                  {deleteAccountBusy ? "Cancelling..." : "Cancel delete request"}
                </button>
              ) : (
                <button type="button" className="table-action danger" onClick={() => setDeleteAccountPromptOpen(true)} disabled={deleteAccountBusy || !onRequestAccountDeletion}>
                  Request account deletion
                </button>
              )}
            </div>
          </article>
          {deleteAccountPromptOpen ? (
            <div className="student-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-account-title">
              <article className="student-delete-card">
                <div className="student-delete-icon" aria-hidden="true">!</div>
                <p className="student-delete-kicker">Delete account</p>
                <h3 id="delete-account-title">Request account deletion?</h3>
                <p>
                  This account will be permanently deleted within 30 days. You can still cancel this request before the deletion is completed.
                </p>
                <div className="student-delete-actions">
                  <button type="button" className="table-action" onClick={() => setDeleteAccountPromptOpen(false)} disabled={deleteAccountBusy}>
                    Keep account
                  </button>
                  <button type="button" className="table-action danger student-delete-confirm" onClick={requestAccountDeletion} disabled={deleteAccountBusy}>
                    {deleteAccountBusy ? "Requesting..." : "Request deletion"}
                  </button>
                </div>
              </article>
            </div>
          ) : null}
          </>
              ) : null}
    </section>
  );
}

function AdminParentsScreen({ data, school, loading, error, onRetry, onUpdate, onDelete, onChildMonitorInitiate, onChildMonitorVerify, onChildMonitorDeactivate, session, countries = [], defaultCountryCode = "NG" }) {
  const parents = data?.parents || [];
  const groupLabels = academicGroupLabels(data?.school, school);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedParentId, setSelectedParentId] = useState("");
  const [selectedParentUserId, setSelectedParentUserId] = useState("");
  const [cmPaying, setCmPaying] = useState(null);
  const [cmConfirmParent, setCmConfirmParent] = useState(null);
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    occupation: "",
    company: "",
    preferred_contact: "email",
    is_active: true,
  });
  const [isUpdating, setIsUpdating] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const [pendingDeleteParent, setPendingDeleteParent] = useState(null);
  const [deletingParentId, setDeletingParentId] = useState("");
  const [deleteSuccess, setDeleteSuccess] = useState("");

  // Virtual account assignment state
  const [vaTab, setVaTab] = useState("profile");
  const [vaForm, setVaForm] = useState({ account_number: "", bank_name: "", account_name: "", provider: "paystack", paystack_reference: "", is_active: true, notes: "" });
  const [vaLoading, setVaLoading] = useState(false);
  const [vaSaving, setVaSaving] = useState(false);
  const [vaError, setVaError] = useState("");
  const [vaSuccess, setVaSuccess] = useState("");
  const [vaExisting, setVaExisting] = useState(null);
  const [vaProvisioning, setVaProvisioning] = useState(false);

  // Fee reminder state
  const [sendingReminder, setSendingReminder] = useState("");
  const [reminderFeedback, setReminderFeedback] = useState("");

  // Bulk messaging state
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkChannel, setBulkChannel] = useState("sms");
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkTemplate, setBulkTemplate] = useState(null);
  const [bulkSelectedIds, setBulkSelectedIds] = useState(new Set());
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);

  // Preload Paystack inline SDK so it's ready before the user clicks
  useEffect(() => {
    if (window.PaystackPop || !data?.paystack_public_key) return;
    const existing = document.querySelector('script[src*="paystack.co"]');
    if (existing) return;
    const s = document.createElement("script");
    s.src = "https://js.paystack.co/v1/inline.js";
    document.head.appendChild(s);
  }, [data?.paystack_public_key]);

  const handleChildMonitorEnable = async (parent) => {
    if (!window.PaystackPop) {
      await new Promise((resolve, reject) => {
        const existing = document.querySelector('script[src*="paystack.co"]');
        if (existing) { existing.addEventListener("load", resolve, { once: true }); return; }
        const s = document.createElement("script");
        s.src = "https://js.paystack.co/v1/inline.js";
        s.onload = resolve;
        s.onerror = () => reject(new Error("Could not load payment system. Check your internet connection."));
        document.head.appendChild(s);
      }).catch((err) => { alert(err.message); });
    }
    if (!window.PaystackPop) { alert("Payment system unavailable. Try again."); return; }
    setCmPaying(parent.id);
    try {
      const result = await onChildMonitorInitiate(parent.id);
      if (!result?.success) { alert(result?.message || "Failed to initiate payment."); return; }
      if (result.already_paid && result.monitor_active) {
        // A previous payment went through — backend activated without charging again.
        alert(result.message || "Child Monitor activated from your previous payment.");
        await onChildMonitorVerify(parent.id, result.reference);
        return;
      }
      const verifyPayment = (tx) => {
        const ref = tx?.reference || result.reference;
        onChildMonitorVerify(parent.id, ref).then((verifyResult) => {
          if (!verifyResult?.success) alert(verifyResult?.message || "Payment verification failed. Contact support.");
        });
      };
      const handler = window.PaystackPop.setup({
        key: data.paystack_public_key,
        email: parent.email,
        amount: result.amount * 100,
        ref: result.reference,
        // Paystack inline v1 fires `callback`; keep onSuccess for v2 compatibility.
        callback: verifyPayment,
        onSuccess: verifyPayment,
        onClose: () => {},
        onCancel: () => {},
      });
      handler.openIframe();
    } catch {
      alert("An error occurred. Please try again.");
    } finally {
      setCmPaying(null);
    }
  };

  const confirmChildMonitorDeactivate = async () => {
    const parent = cmConfirmParent;
    setCmConfirmParent(null);
    const result = await onChildMonitorDeactivate(parent.id);
    if (!result?.success) alert(result?.message || "Failed to deactivate.");
  };

  const buildTemplate = (tpl) => {
    const schoolName = data?.school?.name || school?.name || "School";
    const now = new Date();

    // SMS has a 160-char budget, so it gets its own compact, single-line copy
    // instead of the longer email/WhatsApp wording sliced mid-sentence.
    if (bulkChannel === "sms") {
      const shortDate = now.toLocaleDateString("en-NG", { day: "numeric", month: "short" });
      const shortTime = now.toLocaleTimeString("en-NG", { hour: "numeric", minute: "2-digit", hour12: true });
      const smsTpls = {
        fee_reminder: `${schoolName}: School fees for your ward are outstanding. Please pay via the school portal or contact the office. Thank you.`,
        meeting: `${schoolName}: You're invited to a parent-teacher meeting on ${shortDate} at ${shortTime}. Please endeavour to attend.`,
        general: `${schoolName}: Important notice - please check the school portal or contact the office for details.`,
        resumption: `${schoolName}: Reminder - school resumes on ${shortDate}. Kindly ensure your ward is present. Thank you.`,
      };
      return (smsTpls[tpl] || smsTpls.general).slice(0, 160);
    }

    const date = now.toLocaleDateString("en-NG", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
    const time = now.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit", hour12: true });
    const tpls = {
      fee_reminder: `Dear Parent,\n\n${schoolName} reminds you that your ward's school fees are currently outstanding. Kindly ensure payment is made promptly.\n\nFor payment details, please log in to the school portal or contact the school office.\n\nDate: ${date}  Time: ${time}\n\n— ${schoolName} Administration`,
      meeting: `Dear Parent,\n\n${schoolName} invites you to an important parent-teacher meeting.\n\nDate: ${date}\nTime: ${time}\n\nPlease endeavour to attend.\n\n— ${schoolName} Administration`,
      general: `Dear Parent,\n\n${schoolName} has an important announcement for you. Please visit the school office or check the school portal for further details.\n\nDate: ${date}  Time: ${time}\n\n— ${schoolName}`,
      resumption: `Dear Parent,\n\n${schoolName} wishes to remind you that resumption for the new term is scheduled. Kindly ensure your ward is in school on the appropriate date.\n\nDate: ${date}\n\n— ${schoolName} Administration`,
    };
    return tpls[tpl] || tpls.general;
  };

  const handleBulkSelectToggle = (parentUserId) => {
    setBulkSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(parentUserId)) { next.delete(parentUserId); } else { next.add(parentUserId); }
      return next;
    });
  };

  const handleBulkSelectAll = () => {
    setBulkSelectedIds((prev) =>
      prev.size === filteredParents.length
        ? new Set()
        : new Set(filteredParents.map((p) => p.user_id))
    );
  };

  const handleBulkSend = async () => {
    if (bulkSelectedIds.size === 0 || !bulkMessage.trim()) return;
    setBulkSending(true);
    setBulkResult(null);
    try {
      const result = await requestJson(session, "POST", "/api/finance/admin/parents/bulk-message/", {
        parent_ids: Array.from(bulkSelectedIds),
        channel: bulkChannel,
        message: bulkMessage,
        personalize: bulkTemplate === "fee_reminder",
      });
      setBulkResult(result);
    } catch (err) {
      setBulkResult({ success: false, message: err.message || "Could not send." });
    } finally {
      setBulkSending(false);
    }
  };

  const buildEditForm = (parent) => ({
    first_name: parent?.first_name || "",
    last_name: parent?.last_name || "",
    email: parent?.email || "",
    phone: parent?.phone || "",
    occupation: parent?.occupation || "",
    company: parent?.company || "",
    preferred_contact: parent?.preferred_contact || "email",
    is_active: Boolean(parent?.is_active),
  });

  const filteredParents = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return parents;
    }
    return parents.filter((item) => {
      const childrenText = (item.children || []).map((child) => `${child.name} ${child.student_id}`).join(" ");
      const haystack = [item.name, item.email, item.phone, childrenText].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }, [parents, searchTerm]);

  const loadVirtualAccount = async (parentId) => {
    setVaLoading(true);
    setVaError("");
    setVaExisting(null);
    try {
      const result = await requestJson(session, "GET", `/api/finance/admin/virtual-accounts/${parentId}/`);
      if (result?.virtual_account) {
        setVaExisting(result.virtual_account);
        setVaForm({
          account_number: result.virtual_account.account_number || "",
          bank_name: result.virtual_account.bank_name || "",
          account_name: result.virtual_account.account_name || "",
          provider: result.virtual_account.provider || "paystack",
          paystack_reference: result.virtual_account.paystack_reference || "",
          is_active: result.virtual_account.is_active !== false,
          notes: result.virtual_account.notes || "",
        });
      } else {
        setVaForm({ account_number: "", bank_name: "", account_name: "", provider: "paystack", paystack_reference: "", is_active: true, notes: "" });
      }
    } catch (err) {
      setVaError(err.message || "Could not load virtual account.");
    } finally {
      setVaLoading(false);
    }
  };

  const handleSaveVirtualAccount = async (event) => {
    event.preventDefault();
    if (!selectedParentUserId) return;
    setVaSaving(true);
    setVaError("");
    setVaSuccess("");
    try {
      const result = await requestJson(session, "POST", `/api/finance/admin/virtual-accounts/${selectedParentUserId}/`, {
        account_number: vaForm.account_number.trim(),
        bank_name: vaForm.bank_name.trim(),
        account_name: vaForm.account_name.trim(),
        provider: vaForm.provider,
        paystack_reference: vaForm.paystack_reference.trim(),
        is_active: vaForm.is_active,
        notes: vaForm.notes.trim(),
      });
      if (result?.virtual_account) {
        setVaExisting(result.virtual_account);
      }
      setVaSuccess(result?.message || "Virtual account saved.");
    } catch (err) {
      setVaError(err.message || "Could not save virtual account.");
    } finally {
      setVaSaving(false);
    }
  };

  const handleProvisionPaystackAccount = async () => {
    if (!selectedParentUserId) return;
    setVaProvisioning(true);
    setVaError("");
    setVaSuccess("");
    try {
      const result = await requestJson(session, "POST", `/api/finance/admin/virtual-accounts/${selectedParentUserId}/provision/`);
      if (result?.virtual_account) {
        setVaExisting(result.virtual_account);
        setVaForm({
          account_number: result.virtual_account.account_number || "",
          bank_name: result.virtual_account.bank_name || "",
          account_name: result.virtual_account.account_name || "",
          provider: result.virtual_account.provider || "paystack",
          paystack_reference: result.virtual_account.paystack_reference || "",
          is_active: result.virtual_account.is_active !== false,
          notes: result.virtual_account.notes || "",
        });
      }
      setVaSuccess(result?.message || "Virtual account provisioned.");
    } catch (err) {
      setVaError(err.message || "Could not provision virtual account.");
    } finally {
      setVaProvisioning(false);
    }
  };

  const handleSendReminder = async (parentUserId) => {
    setSendingReminder(parentUserId);
    setReminderFeedback("");
    try {
      const result = await requestJson(session, "POST", `/api/finance/admin/virtual-accounts/${parentUserId}/remind/`);
      setReminderFeedback(result?.success ? `Reminder sent.` : result?.message || "Could not send.");
    } catch (err) {
      setReminderFeedback(err.message || "Could not send reminder.");
    } finally {
      setSendingReminder("");
      setTimeout(() => setReminderFeedback(""), 4000);
    }
  };

  const handleStartEdit = (parent) => {
    setSelectedParentId(parent.id);
    setSelectedParentUserId(parent.user_id);
    setEditForm(buildEditForm(parent));
    setEditError("");
    setEditSuccess("");
    setVaTab("profile");
    setVaError("");
    setVaSuccess("");
    loadVirtualAccount(parent.user_id);
  };

  const handleUpdateSubmit = async (event) => {
    event.preventDefault();
    if (!selectedParentId || !onUpdate) {
      return;
    }
    setEditError("");
    setEditSuccess("");
    setIsUpdating(true);
    try {
      const result = await onUpdate(selectedParentId, {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        occupation: editForm.occupation.trim(),
        company: editForm.company.trim(),
        preferred_contact: editForm.preferred_contact,
        is_active: editForm.is_active,
      });
      if (result?.parent) {
        setEditForm(buildEditForm(result.parent));
      }
      setEditSuccess(result?.message || "Parent updated.");
    } catch (actionError) {
      setEditError(actionError.message || "Could not update parent.");
    } finally {
      setIsUpdating(false);
    }
  };

  const confirmDeleteParent = async () => {
    const parent = pendingDeleteParent;
    if (!parent?.id || !onDelete) {
      return;
    }
    setDeletingParentId(parent.id);
    setEditError("");
    try {
      const result = await onDelete(parent.id);
      if (selectedParentId === parent.id) {
        setSelectedParentId("");
      }
      setPendingDeleteParent(null);
      setDeleteSuccess(result?.message || `${parent.name || "Parent"} deleted.`);
    } catch (deleteError) {
      setEditError(deleteError.message || "Could not delete parent.");
    } finally {
      setDeletingParentId("");
    }
  };

  useEffect(() => {
    if (!deleteSuccess) {
      return undefined;
    }
    const timer = window.setTimeout(() => setDeleteSuccess(""), 2600);
    return () => window.clearTimeout(timer);
  }, [deleteSuccess]);

  useEffect(() => {
    if (!selectedParentId) {
      return;
    }
    if (!parents.find((item) => item.id === selectedParentId)) {
      setSelectedParentId("");
      setSelectedParentUserId("");
    }
  }, [parents, selectedParentId]);

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Parent Directory</h2>
        <p>Review, edit, and remove guardian records linked from student profiles.</p>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <div className="metric-grid">
            <MetricCard label="Total Parents" value={data.summary?.total_parents || 0} helper="Parent profiles in this school" />
            <MetricCard label="Linked Parents" value={data.summary?.linked_parents || 0} helper="Attached to student records" />
            <MetricCard label="Without Children" value={data.summary?.without_children || 0} helper="No linked student yet" />
          </div>

          {/* Child Monitor Pricing Card */}
          {data.paystack_public_key ? (
            <article className="app-panel cm-pricing-card">
              <div className="cm-pricing-body">
                <div className="cm-pricing-icon">🔔</div>
                <div className="cm-pricing-info">
                  <h3 className="cm-pricing-title">Child Monitor</h3>
                  <p className="cm-pricing-desc">
                    Enable instant SMS alerts for a parent whenever their child&apos;s attendance is marked — present, absent, or late.
                    Toggle on per parent in the table below.
                  </p>
                </div>
                <div className="cm-pricing-tag">
                  ₦{(data.child_monitor_price || 1000).toLocaleString()}<span>/child</span>
                </div>
              </div>
              <div className="cm-pricing-meta">
                <span className="km-badge km-badge--active">{parents.filter((p) => p.child_monitor_active).length} active</span>
                <span className="cm-pricing-total">{parents.length} total parents</span>
              </div>
            </article>
          ) : null}

          {/* Bulk Messaging Panel */}
          <article className="app-panel" style={{ borderLeft: bulkOpen ? "4px solid #6366f1" : undefined }}>
            <div className="bulk-panel-header">
              <h3>Bulk Message</h3>
              <button
                type="button"
                className={`table-action${bulkOpen ? " active" : ""}`}
                style={bulkOpen ? { background: "#6366f1", color: "#fff", borderColor: "#6366f1" } : undefined}
                onClick={() => { setBulkOpen((p) => !p); setBulkResult(null); if (bulkOpen) setBulkSelectedIds(new Set()); }}
              >
                {bulkOpen ? "Close Bulk Message" : "Open Bulk Message"}
              </button>
            </div>

            {bulkOpen ? (
              <div className="bulk-panel-body">
                {/* Channel picker */}
                <div className="bulk-channel-row">
                  {[["sms", "SMS"], ["whatsapp", "WhatsApp"], ["email", "Email"]].map(([val, label]) => (
                    <button
                      key={val}
                      type="button"
                      className={`bulk-channel-btn${bulkChannel === val ? " active" : ""}`}
                      onClick={() => {
                        setBulkChannel(val);
                        if (val === "sms") setBulkMessage((prev) => prev.slice(0, 160));
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {/* Template picker */}
                <div className="bulk-template-row">
                  <span className="bulk-template-label">Templates:</span>
                  {[["fee_reminder", "Fee Reminder"], ["meeting", "Meeting Notice"], ["general", "General Notice"], ["resumption", "Resumption Reminder"]].map(([tpl, lbl]) => (
                    <button
                      key={tpl}
                      type="button"
                      className="bulk-template-btn"
                      onClick={() => {
                        const text = buildTemplate(tpl);
                        setBulkMessage(bulkChannel === "sms" ? text.slice(0, 160) : text);
                        setBulkTemplate(tpl);
                      }}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>

                {/* Message textarea */}
                <label className="bulk-message-label">
                  Message<span className="bulk-message-hint">(school name, date &amp; time are pre-filled in templates)</span>
                  <textarea
                    className="bulk-message-field"
                    rows={6}
                    value={bulkMessage}
                    onChange={(e) => {
                      setBulkMessage(bulkChannel === "sms" ? e.target.value.slice(0, 160) : e.target.value);
                      setBulkTemplate(null);
                    }}
                    maxLength={bulkChannel === "sms" ? 160 : undefined}
                    placeholder="Type your message or pick a template above…"
                  />
                  {bulkChannel === "sms" && (
                    <span className={`bulk-sms-counter${bulkMessage.length >= 160 ? " bulk-sms-counter--limit" : ""}`}>
                      {bulkMessage.length}/160 characters (SMS limit)
                    </span>
                  )}
                  {bulkTemplate === "fee_reminder" && (
                    <span className="bulk-message-hint">
                      Each parent will get their own children's names, outstanding balance, and payment account instead of this preview text.
                    </span>
                  )}
                </label>

                {/* Select controls + send */}
                <div className="bulk-controls-row">
                  <label className="bulk-select-label">
                    <input
                      type="checkbox"
                      checked={filteredParents.length > 0 && bulkSelectedIds.size === filteredParents.length}
                      onChange={handleBulkSelectAll}
                    />
                    Select all ({filteredParents.length})
                  </label>
                  <span className="bulk-selected-count">{bulkSelectedIds.size} selected</span>
                  <button
                    type="button"
                    className="table-action"
                    style={{ background: "#6366f1", color: "#fff", borderColor: "#6366f1", opacity: bulkSending || bulkSelectedIds.size === 0 || !bulkMessage.trim() ? 0.45 : 1 }}
                    disabled={bulkSending || bulkSelectedIds.size === 0 || !bulkMessage.trim()}
                    onClick={handleBulkSend}
                  >
                    {bulkSending ? "Sending…" : `Send ${bulkChannel.toUpperCase()} to ${bulkSelectedIds.size}`}
                  </button>
                  {bulkSelectedIds.size > 0 && (
                    <button type="button" className="table-action" onClick={() => setBulkSelectedIds(new Set())}>
                      Clear selection
                    </button>
                  )}
                </div>

                {/* Result feedback */}
                {bulkResult && (
                  <div className={`bulk-result ${bulkResult.success ? "success" : "error"}`}>
                    {bulkResult.success
                      ? `Sent to ${bulkResult.sent} parent${bulkResult.sent !== 1 ? "s" : ""}${bulkResult.failed > 0 ? `, ${bulkResult.failed} failed` : ""}${bulkResult.skipped > 0 ? `, ${bulkResult.skipped} skipped (no outstanding balance)` : ""}.`
                      : bulkResult.message || "Send failed."}
                    {bulkResult.errors?.length > 0 && (
                      <ul>{bulkResult.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="field-note" style={{ margin: "0.4rem 0 0" }}>
                Send SMS, WhatsApp, or Email to selected parents at once with school-branded templates.
              </p>
            )}
          </article>

          <article className="app-panel">
            <h3>Directory</h3>
            <div className="directory-tools">
              <label className="panel-field full search-field">
                Search by parent, phone, email, or student
                <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Example: 0803 or Amina" />
              </label>
            </div>
            {filteredParents.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    {bulkOpen ? (
                      <th style={{ width: "2.5rem", textAlign: "center" }}>
                        <input
                          type="checkbox"
                          title="Select all visible"
                          checked={filteredParents.length > 0 && bulkSelectedIds.size === filteredParents.length}
                          onChange={handleBulkSelectAll}
                        />
                      </th>
                    ) : null}
                    <th>Parent</th>
                    <th>Phone</th>
                    <th>Email</th>
                    <th>Ward(s)</th>
                    <th>Virtual Account</th>
                    <th>Child Monitor</th>
                    <th>Contact</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredParents.map((parent) => (
                    <tr key={parent.id} className={bulkSelectedIds.has(parent.user_id) ? "bulk-row-selected" : undefined}>
                      {bulkOpen ? (
                        <td style={{ textAlign: "center" }}>
                          <input
                            type="checkbox"
                            checked={bulkSelectedIds.has(parent.user_id)}
                            onChange={() => handleBulkSelectToggle(parent.user_id)}
                          />
                        </td>
                      ) : null}
                      <td>{parent.name || "Parent"}<br /><small>{parent.is_active ? "Active" : "Inactive"}</small></td>
                      <td>{parent.phone || "-"}</td>
                      <td>{parent.email || "-"}</td>
                      <td>
                        {(parent.children || []).length ? (
                          (parent.children || []).map((child) => (
                            <small key={child.id} style={{ display: "block" }}>{child.name} — {child.student_id} — {child.class_name || groupLabels.unassigned}</small>
                          ))
                        ) : (
                          <small>No ward linked</small>
                        )}
                      </td>
                      <td>
                        {parent.virtual_account ? (
                          <>
                            <strong style={{ fontSize: "0.85rem", letterSpacing: "0.05em" }}>{parent.virtual_account.account_number}</strong>
                            <br />
                            <small style={{ color: "#64748b" }}>{parent.virtual_account.bank_name}</small>
                          </>
                        ) : (
                          <small style={{ color: "#94a3b8" }}>Not assigned</small>
                        )}
                      </td>
                      <td>
                        <div className="km-toggle-cell">
                          {parent.child_monitor_active ? (
                            <>
                              <span className="km-badge km-badge--active">Active</span>
                              {parent.child_monitor_expires_at ? (
                                <small style={{ color: "#94a3b8" }}>
                                  Renews {new Date(parent.child_monitor_expires_at).toLocaleDateString()}
                                </small>
                              ) : null}
                              <button
                                type="button"
                                className="btn btn-sm btn-outline-danger"
                                onClick={() => setCmConfirmParent(parent)}
                              >Off</button>
                            </>
                          ) : (
                            <button
                              type="button"
                              className={`btn btn-sm btn-primary km-enable-btn${cmPaying === parent.id ? " loading" : ""}`}
                              onClick={() => handleChildMonitorEnable(parent)}
                              disabled={cmPaying === parent.id || !parent.phone || !data.paystack_public_key}
                              title={!parent.phone ? "Parent has no phone number on file" : ""}
                            >
                              {cmPaying === parent.id ? "Processing…" : `Enable — ₦${((parent.children_count || 1) * (data.child_monitor_price || 1000)).toLocaleString()}`}
                            </button>
                          )}
                        </div>
                      </td>
                      <td>{parent.preferred_contact || "email"}</td>
                      <td>
                        <div className="table-actions-inline">
                          <button type="button" className="table-action" onClick={() => handleStartEdit(parent)}>Edit</button>
                          <button
                            type="button"
                            className="table-action"
                            title="Send WhatsApp/SMS fee reminder"
                            onClick={() => handleSendReminder(parent.user_id)}
                            disabled={sendingReminder === parent.user_id || !parent.phone}
                          >
                            {sendingReminder === parent.user_id ? "Sending…" : "Remind"}
                          </button>
                          <button type="button" className="table-action danger" onClick={() => setPendingDeleteParent(parent)} disabled={deletingParentId === parent.id}>
                            {deletingParentId === parent.id ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="panel-empty">{searchTerm ? "No parents match your filter." : "No parents found yet. Creating a student with a guardian phone will add one here."}</p>
            )}
          </article>

          {reminderFeedback ? (
            <div className="student-delete-success" role="status" aria-live="polite">
              <div className="student-delete-success-mark" aria-hidden="true"></div>
              <div>
                <strong>Fee Reminder</strong>
                <span>{reminderFeedback}</span>
              </div>
            </div>
          ) : null}

          {deleteSuccess ? (
            <div className="student-delete-success" role="status" aria-live="polite">
              <div className="student-delete-success-mark" aria-hidden="true"></div>
              <div>
                <strong>Parent deleted</strong>
                <span>{deleteSuccess}</span>
              </div>
            </div>
          ) : null}

          {pendingDeleteParent ? (
            <div className="student-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="parent-delete-title">
              <article className="student-delete-card">
                <div className="student-delete-icon" aria-hidden="true">!</div>
                <p className="student-delete-kicker">Delete parent</p>
                <h3 id="parent-delete-title">Delete {pendingDeleteParent.name || "this parent"}?</h3>
                <p>This removes the parent login/profile from the directory. Student records will remain in place.</p>
                <div className="student-delete-summary">
                  <strong>{pendingDeleteParent.name || "Parent record"}</strong>
                  <span>{pendingDeleteParent.phone || pendingDeleteParent.email || "Contact profile"}</span>
                </div>
                <div className="student-delete-actions">
                  <button type="button" className="table-action" onClick={() => setPendingDeleteParent(null)} disabled={deletingParentId === pendingDeleteParent.id}>Cancel</button>
                  <button type="button" className="table-action danger student-delete-confirm" onClick={confirmDeleteParent} disabled={deletingParentId === pendingDeleteParent.id}>
                    {deletingParentId === pendingDeleteParent.id ? "Deleting..." : "Delete parent"}
                  </button>
                </div>
              </article>
            </div>
          ) : null}

          {cmConfirmParent ? (
            <div className="student-delete-dialog" role="dialog" aria-modal="true">
              <article className="student-delete-card">
                <div className="student-delete-icon" aria-hidden="true">🔔</div>
                <p className="student-delete-kicker">Child Monitor</p>
                <h3>Deactivate for {cmConfirmParent.name}?</h3>
                <p>SMS attendance alerts will stop immediately. You&apos;ll need to pay ₦{((cmConfirmParent.children_count || 1) * (data.child_monitor_price || 1000)).toLocaleString()} to re-enable.</p>
                <div className="student-delete-actions">
                  <button type="button" className="table-action" onClick={() => setCmConfirmParent(null)}>Cancel</button>
                  <button type="button" className="table-action danger student-delete-confirm" onClick={confirmChildMonitorDeactivate}>Deactivate</button>
                </div>
              </article>
            </div>
          ) : null}

          {selectedParentId ? (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-parent-title" onClick={(e) => { if (e.target === e.currentTarget && !isUpdating && !vaSaving) setSelectedParentId(""); }}>
            <article className="app-panel edit-modal-card">
              <div className="edit-modal-head">
                <div>
                  <h3 id="edit-parent-title">Edit Parent</h3>
                  <p>Update contact, profile and virtual account</p>
                </div>
                <button type="button" className="edit-modal-close" onClick={() => setSelectedParentId("")} disabled={isUpdating || vaSaving} aria-label="Close"><X size={16} /></button>
              </div>

              {/* Tab switcher */}
              <div className="pill-stack" style={{ marginBottom: "1rem" }}>
                <button
                  type="button"
                  className={`pill${vaTab === "profile" ? " active" : ""}`}
                  style={{ cursor: "pointer", fontWeight: vaTab === "profile" ? "700" : "400" }}
                  onClick={() => setVaTab("profile")}
                >
                  Profile
                </button>
                <button
                  type="button"
                  className={`pill${vaTab === "virtual-account" ? " active" : ""}`}
                  style={{ cursor: "pointer", fontWeight: vaTab === "virtual-account" ? "700" : "400" }}
                  onClick={() => setVaTab("virtual-account")}
                >
                  Virtual Account {vaExisting ? "✓" : ""}
                </button>
              </div>

              {/* Profile tab */}
              {vaTab === "profile" ? (
                <form className="panel-form" onSubmit={handleUpdateSubmit}>
                  <div className="panel-form-grid">
                    <label className="panel-field">First Name<input value={editForm.first_name} onChange={(event) => setEditForm((prev) => ({ ...prev, first_name: event.target.value }))} required /></label>
                    <label className="panel-field">Last Name<input value={editForm.last_name} onChange={(event) => setEditForm((prev) => ({ ...prev, last_name: event.target.value }))} /></label>
                    <label className="panel-field">Email<input type="email" value={editForm.email} onChange={(event) => setEditForm((prev) => ({ ...prev, email: event.target.value }))} required /></label>
                    <label className="panel-field">Phone<PhoneCountryInput countries={countries} value={editForm.phone} onChange={(val) => setEditForm((prev) => ({ ...prev, phone: val }))} defaultCountryCode={defaultCountryCode} /></label>
                    <label className="panel-field">Occupation<input value={editForm.occupation} onChange={(event) => setEditForm((prev) => ({ ...prev, occupation: event.target.value }))} /></label>
                    <label className="panel-field">Company<input value={editForm.company} onChange={(event) => setEditForm((prev) => ({ ...prev, company: event.target.value }))} /></label>
                    <label className="panel-field">
                      Preferred Contact
                      <select value={editForm.preferred_contact} onChange={(event) => setEditForm((prev) => ({ ...prev, preferred_contact: event.target.value }))}>
                        <option value="email">Email</option>
                        <option value="sms">SMS</option>
                        <option value="push">Push Notification</option>
                        <option value="whatsapp">WhatsApp</option>
                      </select>
                    </label>
                    <label className="panel-field checkbox-field">
                      <input type="checkbox" checked={editForm.is_active} onChange={(event) => setEditForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                      Active account
                    </label>
                  </div>
                  {editError ? <p className="form-feedback error">{editError}</p> : null}
                  {editSuccess ? <p className="form-feedback success">{editSuccess}</p> : null}
                  <div className="panel-form-actions">
                    <button type="submit" disabled={isUpdating}>{isUpdating ? "Saving..." : "Update Parent"}</button>
                    <button type="button" className="table-action" onClick={() => setSelectedParentId("")} disabled={isUpdating}>Cancel</button>
                  </div>
                </form>
              ) : null}

              {/* Virtual Account tab */}
              {vaTab === "virtual-account" ? (
                vaLoading ? (
                  <p className="panel-empty">Loading virtual account...</p>
                ) : (
                  <form className="panel-form" onSubmit={handleSaveVirtualAccount}>
                    <p className="field-note" style={{ marginBottom: "0.75rem" }}>
                      Auto-generate a dedicated account number for this parent, or assign one manually below.
                      The parent transfers school fees to this account and the system automatically matches and credits their children's fees.
                    </p>
                    <div className="panel-form-actions" style={{ marginBottom: "1rem" }}>
                      <button
                        type="button"
                        onClick={handleProvisionPaystackAccount}
                        disabled={vaProvisioning || vaSaving}
                      >
                        {vaProvisioning ? "Provisioning..." : "Provision Account"}
                      </button>
                    </div>
                    {vaExisting ? (
                      <div style={{ padding: "0.75rem", background: "#f0fdf4", borderRadius: "6px", marginBottom: "1rem", border: "1px solid #bbf7d0" }}>
                        <strong style={{ color: "#166534" }}>Active virtual account assigned</strong>
                        <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#15803d" }}>
                          {vaExisting.account_number} — {vaExisting.bank_name}
                        </p>
                      </div>
                    ) : (
                      <div style={{ padding: "0.75rem", background: "#fffbeb", borderRadius: "6px", marginBottom: "1rem", border: "1px solid #fde68a" }}>
                        <strong style={{ color: "#92400e" }}>No virtual account assigned yet</strong>
                      </div>
                    )}
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        Account Number <span style={{ color: "#ef4444" }}>*</span>
                        <input
                          value={vaForm.account_number}
                          onChange={(e) => setVaForm((p) => ({ ...p, account_number: e.target.value }))}
                          placeholder="e.g. 0123456789"
                          required
                        />
                      </label>
                      <label className="panel-field">
                        Bank Name <span style={{ color: "#ef4444" }}>*</span>
                        <input
                          value={vaForm.bank_name}
                          onChange={(e) => setVaForm((p) => ({ ...p, bank_name: e.target.value }))}
                          placeholder="e.g. Wema Bank"
                          required
                        />
                      </label>
                      <label className="panel-field">
                        Account Name <span style={{ color: "#ef4444" }}>*</span>
                        <input
                          value={vaForm.account_name}
                          onChange={(e) => setVaForm((p) => ({ ...p, account_name: e.target.value }))}
                          placeholder="e.g. John Doe / SchoolDom"
                          required
                        />
                      </label>
                      <label className="panel-field">
                        Provider
                        <select value={vaForm.provider} onChange={(e) => setVaForm((p) => ({ ...p, provider: e.target.value }))}>
                          <option value="paystack">Automated</option>
                          <option value="kuda">Kuda</option>
                          <option value="flutterwave">Flutterwave</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      <label className="panel-field">
                        Payment Reference (optional)
                        <input
                          value={vaForm.paystack_reference}
                          onChange={(e) => setVaForm((p) => ({ ...p, paystack_reference: e.target.value }))}
                          placeholder="DVA customer code from provider"
                        />
                      </label>
                      <label className="panel-field checkbox-field">
                        <input
                          type="checkbox"
                          checked={vaForm.is_active}
                          onChange={(e) => setVaForm((p) => ({ ...p, is_active: e.target.checked }))}
                        />
                        Active (parent can see and use this account)
                      </label>
                      <label className="panel-field full">
                        Notes (optional)
                        <input
                          value={vaForm.notes}
                          onChange={(e) => setVaForm((p) => ({ ...p, notes: e.target.value }))}
                          placeholder="Internal notes about this virtual account"
                        />
                      </label>
                    </div>
                    {vaError ? <p className="form-feedback error">{vaError}</p> : null}
                    {vaSuccess ? <p className="form-feedback success">{vaSuccess}</p> : null}
                    <div className="panel-form-actions">
                      <button type="submit" disabled={vaSaving}>{vaSaving ? "Saving..." : vaExisting ? "Update Virtual Account" : "Assign Virtual Account"}</button>
                      <button type="button" className="table-action" onClick={() => setVaTab("profile")} disabled={vaSaving}>Back to Profile</button>
                    </div>
                  </form>
                )
              ) : null}
            </article>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function AdminSmsWalletScreen({ data, loading, error, onRetry, onPurchase, onVerifyPurchase }) {
  const pricing = data?.unit_pricing || { block_size: 100, block_price: "1000.00", minimum_units: 100, currency: "NGN" };
  const blockSize = pricing.block_size || 100;
  const blockPrice = Number(pricing.block_price || 1000);
  const [units, setUnits] = useState(blockSize);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    if (window.PaystackPop || !data?.paystack_public_key) return;
    const existing = document.querySelector('script[src*="paystack.co"]');
    if (existing) return;
    const s = document.createElement("script");
    s.src = "https://js.paystack.co/v1/inline.js";
    document.head.appendChild(s);
  }, [data?.paystack_public_key]);

  const adjustUnits = (delta) => {
    setUnits((prev) => Math.max(blockSize, prev + delta));
  };

  const handleUnitsInput = (value) => {
    const parsed = Math.max(blockSize, Math.round((Number(value) || blockSize) / blockSize) * blockSize);
    setUnits(parsed);
  };

  const priceForUnits = (units / blockSize) * blockPrice;

  const handleBuyCredits = async () => {
    if (!window.PaystackPop) {
      await new Promise((resolve, reject) => {
        const existing = document.querySelector('script[src*="paystack.co"]');
        if (existing) { existing.addEventListener("load", resolve, { once: true }); return; }
        const s = document.createElement("script");
        s.src = "https://js.paystack.co/v1/inline.js";
        s.onload = resolve;
        s.onerror = () => reject(new Error("Could not load payment system. Check your internet connection."));
        document.head.appendChild(s);
      }).catch((err) => { alert(err.message); });
    }
    if (!window.PaystackPop) { alert("Payment system unavailable. Try again."); return; }
    setPaying(true);
    try {
      const result = await onPurchase(units);
      if (!result?.success) { alert(result?.message || "Failed to initiate purchase."); return; }
      const verifyPayment = (tx) => {
        const ref = tx?.reference || result.reference;
        onVerifyPurchase(ref).then((verifyResult) => {
          if (!verifyResult?.success) alert(verifyResult?.message || "Payment verification failed. Contact support.");
        });
      };
      const handler = window.PaystackPop.setup({
        key: data.paystack_public_key,
        email: "billing@schooldom.academy",
        amount: Math.round(Number(result.amount) * 100),
        ref: result.reference,
        // Paystack inline v1 fires `callback`; keep onSuccess for v2 compatibility.
        callback: verifyPayment,
        onSuccess: verifyPayment,
        onClose: () => {},
        onCancel: () => {},
      });
      handler.openIframe();
    } catch {
      alert("An error occurred. Please try again.");
    } finally {
      setPaying(false);
    }
  };

  const wallet = data?.wallet || {};
  const transactions = data?.recent_transactions || [];
  const lowBalance = wallet.balance < (wallet.low_balance_threshold || 50);

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>SMS Wallet</h2>
        <p>Buy SMS credits to cover attendance alerts, fee reminders, and bulk messages sent to guardians.</p>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <div className="metric-grid">
            <MetricCard label="SMS Credits" value={wallet.balance ?? 0} helper={wallet.is_locked ? "Wallet locked" : "Available to send"} />
            <MetricCard label="Recent Purchases" value={transactions.filter((t) => t.tx_type === "purchase").length} helper="Last 20 transactions" />
          </div>

          {lowBalance ? (
            <div className="bulk-result error" role="alert">
              SMS credits are running low. Buy more below to avoid interrupted alerts.
            </div>
          ) : null}

          <article className="app-panel cm-pricing-card">
            <h3>Buy SMS Credits</h3>
            {data.paystack_public_key ? (
              <>
                <p className="cm-pricing-desc">
                  {blockSize.toLocaleString()} credits = ₦{blockPrice.toLocaleString()}. Sold in blocks of {blockSize} - minimum {pricing.minimum_units.toLocaleString()} credits.
                </p>
                <div className="cm-pricing-body" style={{ alignItems: "center" }}>
                  <button type="button" className="table-action sms-wallet-btn" onClick={() => adjustUnits(-blockSize)} disabled={units <= blockSize}>
                    − {blockSize}
                  </button>
                  <input
                    type="number"
                    step={blockSize}
                    min={blockSize}
                    value={units}
                    onChange={(e) => handleUnitsInput(e.target.value)}
                    className="sms-wallet-units-input"
                    aria-label="SMS credits to buy"
                  />
                  <button type="button" className="table-action sms-wallet-btn" onClick={() => adjustUnits(blockSize)}>
                    + {blockSize}
                  </button>
                  <div className="cm-pricing-tag">
                    ₦{priceForUnits.toLocaleString()}
                  </div>
                </div>
                <div className="cm-pricing-meta">
                  <button type="button" className="table-action sms-wallet-btn sms-wallet-btn--primary" disabled={paying} onClick={handleBuyCredits}>
                    {paying ? "Processing…" : `Buy ${units.toLocaleString()} credits`}
                  </button>
                </div>
              </>
            ) : (
              <p className="panel-empty compact">Payments are not configured for this school yet.</p>
            )}
          </article>

          <article className="app-panel">
            <h3>Recent Transactions</h3>
            {transactions.length > 0 ? (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Reference</th>
                      <th>Type</th>
                      <th>Credits</th>
                      <th>Balance After</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => (
                      <tr key={tx.id}>
                        <td>{tx.reference}</td>
                        <td style={{ textTransform: "capitalize" }}>{tx.tx_type}</td>
                        <td>{tx.credits > 0 ? `+${tx.credits}` : tx.credits}</td>
                        <td>{tx.balance_after ?? "—"}</td>
                        <td>{tx.created_at ? new Date(tx.created_at).toLocaleString() : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="panel-empty compact">No SMS wallet activity yet.</p>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
}

function AdminStudentsScreen({ data, school, loading, error, onRetry, onCreate, onUpdate, onDelete, onActivityTitleSave, onActivityTitleDeactivate, countries = [], defaultCountryCode = "NG" }) {
  const students = data?.students || [];
  const classes = data?.options?.classes || [];
  const groupLabels = academicGroupLabels(data?.school, school);
  // Student activity titles (leadership/extracurricular roles) are a K-12-only feature.
  const nonK12 = (school?.school_type || school?.schoolType || data?.school?.school_type || data?.school?.schoolType || "k12") === "non_k12";
  const activityTitles = data?.options?.student_activity_titles || [];
  const activeActivityTitles = activityTitles.filter((item) => item.is_active);
  const [form, setForm] = useState({
    student_email: "",
    first_name: "",
    last_name: "",
    gender: "",
    state_of_origin: "",
    local_government: "",
    guardian_name: "",
    guardian_phone: "",
    guardian_email: "",
    guardian_relation: "Guardian",
    second_guardian_name: "",
    second_guardian_phone: "",
    second_guardian_email: "",
    second_guardian_relation: "",
    class_id: "",
    admission_date: "",
    student_password: "",
    confirm_student_password: "",
    profile_picture: null,
    date_of_birth: "",
    disability: "no",
    medical_records: "",
    blood_group: "",
    student_type: "",
    extra_curricular_activity_title_id: "",
    home_address: "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    gender: "",
    state_of_origin: "",
    local_government: "",
    guardian_name: "",
    guardian_phone: "",
    guardian_email: "",
    guardian_relation: "Guardian",
    second_guardian_name: "",
    second_guardian_phone: "",
    second_guardian_email: "",
    second_guardian_relation: "",
    class_id: "",
    admission_date: "",
    date_of_birth: "",
    disability: "no",
    medical_records: "",
    blood_group: "",
    student_type: "",
    extra_curricular_activity_title_id: "",
    home_address: "",
    is_active: true,
    student_password: "",
    confirm_student_password: "",
  });
  const [isUpdating, setIsUpdating] = useState(false);
  const [editError, setEditError] = useState("");
    const [editSuccess, setEditSuccess] = useState("");
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [showCreateConfirmPassword, setShowCreateConfirmPassword] = useState(false);
  const [showEditPassword, setShowEditPassword] = useState(false);
  const [showEditConfirmPassword, setShowEditConfirmPassword] = useState(false);
  const [deletingStudentId, setDeletingStudentId] = useState("");
  const [pendingDeleteStudent, setPendingDeleteStudent] = useState(null);
  const [deleteSuccess, setDeleteSuccess] = useState(null);
  const [activityTitleForm, setActivityTitleForm] = useState({ name: "", star_rating: "1" });
  const [editingActivityTitleId, setEditingActivityTitleId] = useState("");
  const [activityTitleBusyId, setActivityTitleBusyId] = useState("");
  const [activityTitleError, setActivityTitleError] = useState("");
  const [activityTitleSuccess, setActivityTitleSuccess] = useState("");
  const createProfilePictureRef = useRef(null);

  const toDateInputValue = (value) => {
    const raw = String(value || "");
    if (!raw) {
      return "";
    }
    return raw.slice(0, 10);
  };

  const buildEditForm = (student) => ({
    first_name: student?.first_name || "",
    last_name: student?.last_name || "",
    email: student?.email || "",
    phone: student?.phone || "",
    gender: student?.gender || "",
    state_of_origin: student?.state_of_origin || "",
    local_government: student?.local_government || "",
    guardian_name: student?.guardian_name || "",
    guardian_phone: student?.guardian_phone || "",
    guardian_email: student?.guardian_email || "",
    guardian_relation: student?.guardian_relation || "Guardian",
    second_guardian_name: student?.second_guardian_name || "",
    second_guardian_phone: student?.second_guardian_phone || "",
    second_guardian_email: student?.second_guardian_email || "",
    second_guardian_relation: student?.second_guardian_relation || "",
    class_id: student?.class_id ? String(student.class_id) : "",
    admission_date: toDateInputValue(student?.admission_date),
    date_of_birth: toDateInputValue(student?.date_of_birth),
    disability: student?.disability || "no",
    medical_records: student?.medical_records || "",
    blood_group: student?.blood_group || "",
    student_type: student?.student_type || "",
    extra_curricular_activity_title_id: student?.extra_curricular_activity_title_id || "",
    home_address: student?.home_address || "",
    is_active: Boolean(student?.is_active),
    student_password: "",
    confirm_student_password: "",
  });

  const filteredStudents = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return students;
    }
    return students.filter((item) => {
      const haystack = [item.name, item.email, item.student_id, item.class_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [searchTerm, students]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");
    setIsSaving(true);
    try {
      const payload = { ...form };
      if (!payload.class_id) {
        delete payload.class_id;
      }
      if (!payload.admission_date) {
        delete payload.admission_date;
      }
      if (!payload.profile_picture) {
        delete payload.profile_picture;
      }
      const result = await onCreate(payload);
      setFormSuccess(result?.message || "Student saved.");
      setForm({
        student_email: "",
        first_name: "",
        last_name: "",
        gender: "",
        state_of_origin: "",
        local_government: "",
        guardian_name: "",
        guardian_phone: "",
        guardian_email: "",
        guardian_relation: "Guardian",
        second_guardian_name: "",
        second_guardian_phone: "",
        second_guardian_email: "",
        second_guardian_relation: "",
        class_id: "",
        admission_date: "",
        student_password: "",
        confirm_student_password: "",
        profile_picture: null,
        date_of_birth: "",
        disability: "no",
        medical_records: "",
        blood_group: "",
        student_type: "",
        extra_curricular_activity_title_id: "",
        home_address: "",
      });
      setShowCreatePassword(false);
      setShowCreateConfirmPassword(false);
      if (createProfilePictureRef.current) {
        createProfilePictureRef.current.value = "";
      }
    } catch (actionError) {
      setFormError(actionError.message || "Could not save student.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleStartEdit = (student) => {
    setSelectedStudentId(student.id);
    setEditForm(buildEditForm(student));
    setShowEditPassword(false);
    setShowEditConfirmPassword(false);
    setEditError("");
    setEditSuccess("");
  };

  const handleUpdateSubmit = async (event) => {
    event.preventDefault();
    if (!selectedStudentId) {
      return;
    }
    setEditError("");
    setEditSuccess("");
    if (editForm.student_password || editForm.confirm_student_password) {
      if (editForm.student_password !== editForm.confirm_student_password) {
        setEditError("Password and confirm password must match.");
        return;
      }
    }
    setIsUpdating(true);
    try {
      const payload = {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        gender: editForm.gender,
        state_of_origin: editForm.state_of_origin.trim(),
        local_government: editForm.local_government.trim(),
        guardian_name: editForm.guardian_name.trim(),
        guardian_phone: editForm.guardian_phone.trim(),
        guardian_email: editForm.guardian_email.trim(),
        guardian_relation: editForm.guardian_relation.trim(),
        second_guardian_name: editForm.second_guardian_name.trim(),
        second_guardian_phone: editForm.second_guardian_phone.trim(),
        second_guardian_email: editForm.second_guardian_email.trim(),
        second_guardian_relation: editForm.second_guardian_relation.trim(),
        class_id: editForm.class_id || "",
        date_of_birth: editForm.date_of_birth,
        disability: editForm.disability,
        medical_records: editForm.medical_records.trim(),
        blood_group: editForm.blood_group,
        student_type: editForm.student_type.trim(),
        extra_curricular_activity_title_id: editForm.extra_curricular_activity_title_id,
        home_address: editForm.home_address.trim(),
        is_active: editForm.is_active,
      };
      if (editForm.admission_date) {
        payload.admission_date = editForm.admission_date;
      }
      if (editForm.student_password || editForm.confirm_student_password) {
        payload.student_password = editForm.student_password;
        payload.confirm_student_password = editForm.confirm_student_password;
      }
      const result = await onUpdate(selectedStudentId, payload);
      if (result?.student) {
        setEditForm(buildEditForm(result.student));
      }
      setEditSuccess(result?.message || "Student updated.");
    } catch (actionError) {
      setEditError(actionError.message || "Could not update student.");
    } finally {
      setIsUpdating(false);
    }
  };

  const requestDeleteStudent = (student) => {
    if (!student?.id || !onDelete) {
      return;
    }
    setFormError("");
    setEditError("");
    setPendingDeleteStudent(student);
  };

  const handleActivityTitleSubmit = async (event) => {
    event.preventDefault();
    const name = activityTitleForm.name.trim();
    if (!name || !onActivityTitleSave) {
      setActivityTitleError("Enter a title name.");
      return;
    }
    setActivityTitleError("");
    setActivityTitleSuccess("");
    setActivityTitleBusyId(editingActivityTitleId || "new");
    try {
      const payload = {
        name,
        star_rating: activityTitleForm.star_rating,
        is_active: true,
      };
      const result = await onActivityTitleSave(editingActivityTitleId, payload);
      setActivityTitleSuccess(result?.message || "Title saved.");
      setActivityTitleForm({ name: "", star_rating: "1" });
      setEditingActivityTitleId("");
    } catch (actionError) {
      setActivityTitleError(actionError.message || "Could not save title.");
    } finally {
      setActivityTitleBusyId("");
    }
  };

  const handleEditActivityTitle = (title) => {
    setEditingActivityTitleId(title.id);
    setActivityTitleForm({ name: title.name || "", star_rating: String(title.star_rating ?? "1") });
    setActivityTitleError("");
    setActivityTitleSuccess("");
  };

  const handleToggleActivityTitle = async (title) => {
    if (!title?.id || !onActivityTitleSave) {
      return;
    }
    setActivityTitleBusyId(title.id);
    setActivityTitleError("");
    setActivityTitleSuccess("");
    try {
      const result = await onActivityTitleSave(title.id, { is_active: !title.is_active });
      setActivityTitleSuccess(result?.message || "Title updated.");
    } catch (actionError) {
      setActivityTitleError(actionError.message || "Could not update title.");
    } finally {
      setActivityTitleBusyId("");
    }
  };

  const handleDeactivateActivityTitle = async (title) => {
    if (!title?.id || !onActivityTitleDeactivate) {
      return;
    }
    setActivityTitleBusyId(title.id);
    setActivityTitleError("");
    setActivityTitleSuccess("");
    try {
      const result = await onActivityTitleDeactivate(title.id);
      setActivityTitleSuccess(result?.message || "Title deactivated.");
    } catch (actionError) {
      setActivityTitleError(actionError.message || "Could not deactivate title.");
    } finally {
      setActivityTitleBusyId("");
    }
  };

  const confirmDeleteStudent = async () => {
    const student = pendingDeleteStudent;
    if (!student?.id || !onDelete) {
      return;
    }
    const label = student.name || student.email || "this student";
    setDeletingStudentId(student.id);
    setEditError("");
    setFormError("");
    try {
      const result = await onDelete(student.id);
      if (selectedStudentId === student.id) {
        setSelectedStudentId("");
      }
      setPendingDeleteStudent(null);
      setDeleteSuccess({
        name: label,
        message: result?.message || `${label} has been deleted.`,
      });
    } catch (deleteError) {
      setFormError(deleteError.message || "Could not delete student.");
    } finally {
      setDeletingStudentId("");
    }
  };

  useEffect(() => {
    if (!deleteSuccess) {
      return undefined;
    }
    const timer = window.setTimeout(() => setDeleteSuccess(null), 2600);
    return () => window.clearTimeout(timer);
  }, [deleteSuccess]);

  useEffect(() => {
    if (!selectedStudentId) {
      return;
    }
    const current = students.find((item) => item.id === selectedStudentId);
    if (!current) {
      setSelectedStudentId("");
      setEditError("");
      setEditSuccess("");
    }
  }, [selectedStudentId, students]);

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Students</h2>
        <p>Create and review student records.</p>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
      <article className="app-panel">
        <h3>Admissions</h3>
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Email
              <input value={form.student_email} onChange={(event) => setForm((prev) => ({ ...prev, student_email: event.target.value }))} required />
            </label>
            <label className="panel-field">
              First Name
              <input value={form.first_name} onChange={(event) => setForm((prev) => ({ ...prev, first_name: event.target.value }))} required />
            </label>
            <label className="panel-field">
              Last Name
                  <input value={form.last_name} onChange={(event) => setForm((prev) => ({ ...prev, last_name: event.target.value }))} required />
                </label>
                <label className="panel-field">
                  Gender
                  <select value={form.gender} onChange={(event) => setForm((prev) => ({ ...prev, gender: event.target.value }))}>
                    <option value="">Select gender</option>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="O">Other</option>
                    <option value="N">Prefer not to say</option>
                  </select>
                </label>
                <label className="panel-field">
                  State of Origin
                  <textarea className="compact-textarea" value={form.state_of_origin} onChange={(event) => setForm((prev) => ({ ...prev, state_of_origin: event.target.value }))} rows="1" />
                </label>
                <label className="panel-field">
                  Local Government
                  <textarea className="compact-textarea" value={form.local_government} onChange={(event) => setForm((prev) => ({ ...prev, local_government: event.target.value }))} rows="1" />
                </label>
                <label className="panel-field">
                  Guardian Name
                  <input value={form.guardian_name} onChange={(event) => setForm((prev) => ({ ...prev, guardian_name: event.target.value }))} required />
                </label>
                <label className="panel-field">
                  Guardian Phone
                  <PhoneCountryInput
                    countries={countries}
                    value={form.guardian_phone}
                    onChange={(val) => setForm((prev) => ({ ...prev, guardian_phone: val }))}
                    defaultCountryCode={defaultCountryCode}
                  />
                </label>
                <label className="panel-field">
                  Guardian Email
                  <input type="email" value={form.guardian_email} onChange={(event) => setForm((prev) => ({ ...prev, guardian_email: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Guardian Relationship
                  <input value={form.guardian_relation} onChange={(event) => setForm((prev) => ({ ...prev, guardian_relation: event.target.value }))} placeholder="Father, Mother, Uncle" />
                </label>
                <label className="panel-field">
                  Second Guardian Name
                  <input value={form.second_guardian_name} onChange={(event) => setForm((prev) => ({ ...prev, second_guardian_name: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Second Guardian Phone
                  <PhoneCountryInput
                    countries={countries}
                    value={form.second_guardian_phone}
                    onChange={(val) => setForm((prev) => ({ ...prev, second_guardian_phone: val }))}
                    defaultCountryCode={defaultCountryCode}
                  />
                </label>
                <label className="panel-field">
                  Second Guardian Email
                  <input type="email" value={form.second_guardian_email} onChange={(event) => setForm((prev) => ({ ...prev, second_guardian_email: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Second Guardian Relationship
                  <input value={form.second_guardian_relation} onChange={(event) => setForm((prev) => ({ ...prev, second_guardian_relation: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Profile Picture
                  <input
                    ref={createProfilePictureRef}
                    type="file"
                    accept="image/*"
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, profile_picture: event.target.files?.[0] || null }))
                    }
                  />
            </label>
            <label className="panel-field">
              {groupLabels.singular}
              <select value={form.class_id} onChange={(event) => setForm((prev) => ({ ...prev, class_id: event.target.value }))}>
                    <option value="">{groupLabels.unassigned}</option>
                    {classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
            </label>
            <label className="panel-field">
              Admission Date
                  <input type="date" value={form.admission_date} onChange={(event) => setForm((prev) => ({ ...prev, admission_date: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Date of Birth
                  <input type="date" value={form.date_of_birth} onChange={(event) => setForm((prev) => ({ ...prev, date_of_birth: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Disability
                  <select value={form.disability} onChange={(event) => setForm((prev) => ({ ...prev, disability: event.target.value }))}>
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </label>
                <label className="panel-field">
                  Blood Group
                  <select value={form.blood_group} onChange={(event) => setForm((prev) => ({ ...prev, blood_group: event.target.value }))}>
                    <option value="">Select Blood Group</option>
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                  </select>
                </label>
                <label className="panel-field">
                  Student Type
                  <input value={form.student_type} onChange={(event) => setForm((prev) => ({ ...prev, student_type: event.target.value }))} placeholder="e.g., Regular, Scholarship, Transfer" />
                </label>
                {nonK12 ? null : (
                  <label className="panel-field">
                    Activity Title
                    <select value={form.extra_curricular_activity_title_id} onChange={(event) => setForm((prev) => ({ ...prev, extra_curricular_activity_title_id: event.target.value }))}>
                      <option value="">No title</option>
                      {activeActivityTitles.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} - {item.star_label || `${item.star_rating || 0} stars`}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="panel-field full">
                  Medical Records
                  <textarea value={form.medical_records} onChange={(event) => setForm((prev) => ({ ...prev, medical_records: event.target.value }))} placeholder="Any medical conditions, allergies, or special medical needs" rows="3" />
                </label>
                <label className="panel-field full">
                  Home Address
                  <textarea value={form.home_address} onChange={(event) => setForm((prev) => ({ ...prev, home_address: event.target.value }))} placeholder="Street address, city, state, postal code" rows="3" />
                </label>
                <label className="panel-field">
              Password
                  <div className="password-toggle-field">
                    <input type={showCreatePassword ? "text" : "password"} value={form.student_password} onChange={(event) => setForm((prev) => ({ ...prev, student_password: event.target.value }))} required />
                    <button type="button" onClick={() => setShowCreatePassword((current) => !current)}>
                      {showCreatePassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </label>
                <label className="panel-field">
                  Confirm Password
                  <div className="password-toggle-field">
                    <input type={showCreateConfirmPassword ? "text" : "password"} value={form.confirm_student_password} onChange={(event) => setForm((prev) => ({ ...prev, confirm_student_password: event.target.value }))} required />
                    <button type="button" onClick={() => setShowCreateConfirmPassword((current) => !current)}>
                      {showCreateConfirmPassword ? "Hide" : "Show"}
                    </button>
                  </div>
            </label>
          </div>
{formError ? <p className="form-feedback error">{formError}</p> : null}
              {formSuccess ? <p className="form-feedback success">{formSuccess}</p> : null}
          <div className="panel-form-actions">
                        <button type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Create Student"}
</button>
          </div>
        </form>
      </article>

      {nonK12 ? null : (
      <article className="app-panel">
        <h3>Student Activity Titles</h3>
        <form className="panel-form" onSubmit={handleActivityTitleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Title Name
              <input
                value={activityTitleForm.name}
                onChange={(event) => setActivityTitleForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Prefect, Class Monitor"
              />
            </label>
            <label className="panel-field">
              Stars
              <input
                type="number"
                min="0.5"
                max="5"
                step="0.5"
                value={activityTitleForm.star_rating}
                onChange={(event) => setActivityTitleForm((prev) => ({ ...prev, star_rating: event.target.value }))}
                placeholder="1"
              />
            </label>
          </div>
          {activityTitleError ? <p className="form-feedback error">{activityTitleError}</p> : null}
          {activityTitleSuccess ? <p className="form-feedback success">{activityTitleSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={Boolean(activityTitleBusyId)}>
              {activityTitleBusyId === "new" || activityTitleBusyId === editingActivityTitleId ? "Saving..." : editingActivityTitleId ? "Rename Title" : "Add Title"}
            </button>
            {editingActivityTitleId ? (
              <button type="button" className="table-action" onClick={() => {
                setEditingActivityTitleId("");
                setActivityTitleForm({ name: "", star_rating: "1" });
              }}>
                Cancel
              </button>
            ) : null}
          </div>
        </form>
        {activityTitles.length > 0 ? (
          <div className="teacher-class-chip-list">
            {activityTitles.map((title) => (
              <button
                key={title.id}
                type="button"
                className={title.is_active ? "" : "muted"}
                onClick={() => handleEditActivityTitle(title)}
                title={`${title.is_active ? "Active" : "Inactive"} - ${title.student_count || 0} student(s)`}
              >
                {title.name} - {title.star_label || `${title.star_rating || 0} stars`}
              </button>
            ))}
          </div>
        ) : null}
        {editingActivityTitleId ? (
          <div className="panel-form-actions">
            {activityTitles.find((item) => item.id === editingActivityTitleId)?.is_active ? (
              <button type="button" className="table-action" onClick={() => handleDeactivateActivityTitle(activityTitles.find((item) => item.id === editingActivityTitleId))} disabled={activityTitleBusyId === editingActivityTitleId}>
                Deactivate
              </button>
            ) : (
              <button type="button" className="table-action" onClick={() => handleToggleActivityTitle(activityTitles.find((item) => item.id === editingActivityTitleId))} disabled={activityTitleBusyId === editingActivityTitleId}>
                Activate
              </button>
            )}
          </div>
        ) : null}
      </article>
      )}

      <article className="app-panel">
        <h3>Student Directory</h3>
        <div className="directory-tools">
                <button
                  type="button"
                className={`table-action filter-toggle ${showFilters ? "active" : ""}`}
                onClick={() => setShowFilters((previous) => !previous)}
              >
                <FilterIcon className="inline-icon" />
                Filter
              </button>
              {showFilters ? (
                <label className="panel-field full search-field">
                  Search by student ID, name, {groupLabels.singular.toLowerCase()}, or email
                  <input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Example: STU1029"
                  />
                </label>
              ) : null}
            </div>

            {filteredStudents.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Student ID</th>
                <th>{groupLabels.singular}</th>
                    {nonK12 ? null : <th>Activity Title</th>}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.email}</td>
                      <td>{item.student_id}</td>
                      <td>{item.class_name}</td>
                      {nonK12 ? null : (
                        <td>
                          {item.extra_curricular_activity_title
                            ? `${item.extra_curricular_activity_title} - ${item.extra_curricular_activity_star_label || `${item.extra_curricular_activity_stars || 0} stars`}`
                            : "None"}
                        </td>
                      )}
                      <td>
                        <div className="table-actions-inline">
                          <button type="button" className="table-action" onClick={() => handleStartEdit(item)}>
                            Edit
                          </button>
                          <button
                            type="button"
                            className="table-action danger"
                            onClick={() => requestDeleteStudent(item)}
                            disabled={deletingStudentId === item.id}
                          >
                            {deletingStudentId === item.id ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="panel-empty">{searchTerm ? "No students match your filter." : "No students found."}</p>
            )}
          </article>

          {pendingDeleteStudent ? (
            <div className="student-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="student-delete-title">
              <article className="student-delete-card">
                <div className="student-delete-icon" aria-hidden="true">!</div>
                <p className="student-delete-kicker">Delete student</p>
                <h3 id="student-delete-title">
                  Delete {pendingDeleteStudent.name || pendingDeleteStudent.email || "this student"}?
                </h3>
                <p>
                  This will remove the student's account and profile. They will no longer be able to sign in or appear in
                  your student directory.
                </p>
                <div className="student-delete-summary">
                  <strong>{pendingDeleteStudent.name || "Student record"}</strong>
                  <span>{pendingDeleteStudent.student_id || pendingDeleteStudent.email || "Account and profile"}</span>
                </div>
                <div className="student-delete-actions">
                  <button
                    type="button"
                    className="table-action"
                    onClick={() => setPendingDeleteStudent(null)}
                    disabled={deletingStudentId === pendingDeleteStudent.id}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="table-action danger student-delete-confirm"
                    onClick={confirmDeleteStudent}
                    disabled={deletingStudentId === pendingDeleteStudent.id}
                  >
                    {deletingStudentId === pendingDeleteStudent.id ? "Deleting..." : "Delete student"}
                  </button>
                </div>
              </article>
            </div>
          ) : null}

          {deleteSuccess ? (
            <div className="student-delete-success" role="status" aria-live="polite">
              <div className="student-delete-success-mark" aria-hidden="true"></div>
              <div>
                <strong>Student deleted</strong>
                <span>{deleteSuccess.message}</span>
              </div>
            </div>
          ) : null}

          {selectedStudentId ? (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-student-title" onClick={(e) => { if (e.target === e.currentTarget && !isUpdating) setSelectedStudentId(""); }}>
              <article className="app-panel edit-modal-card">
                <div className="edit-modal-head">
                  <div>
                    <h3 id="edit-student-title">Edit Student</h3>
                    <p>Update profile, contact and academic information</p>
                  </div>
                  <button type="button" className="edit-modal-close" onClick={() => setSelectedStudentId("")} disabled={isUpdating} aria-label="Close">
                    <X size={16} />
                  </button>
                </div>

                <form className="modal-form-wrap" onSubmit={handleUpdateSubmit}>
                  {/* Personal Information */}
                  <div className="form-section">
                    <p className="form-section-label"><User size={13} /> Personal Information</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        First Name
                        <input value={editForm.first_name} onChange={(e) => setEditForm((p) => ({ ...p, first_name: e.target.value }))} required />
                      </label>
                      <label className="panel-field">
                        Last Name
                        <input value={editForm.last_name} onChange={(e) => setEditForm((p) => ({ ...p, last_name: e.target.value }))} required />
                      </label>
                      <label className="panel-field">
                        Email
                        <input type="email" value={editForm.email} onChange={(e) => setEditForm((p) => ({ ...p, email: e.target.value }))} required />
                      </label>
                      <label className="panel-field">
                        Phone
                        <input value={editForm.phone} onChange={(e) => setEditForm((p) => ({ ...p, phone: e.target.value }))} />
                      </label>
                      <label className="panel-field">
                        Gender
                        <select value={editForm.gender} onChange={(e) => setEditForm((p) => ({ ...p, gender: e.target.value }))}>
                          <option value="">Select gender</option>
                          <option value="M">Male</option>
                          <option value="F">Female</option>
                          <option value="O">Other</option>
                          <option value="N">Prefer not to say</option>
                        </select>
                      </label>
                      <label className="panel-field">
                        Date of Birth
                        <input type="date" value={editForm.date_of_birth} onChange={(e) => setEditForm((p) => ({ ...p, date_of_birth: e.target.value }))} />
                      </label>
                    </div>
                  </div>

                  {/* Location */}
                  <div className="form-section">
                    <p className="form-section-label"><MapPin size={13} /> Location &amp; Background</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        State of Origin
                        <input value={editForm.state_of_origin} onChange={(e) => setEditForm((p) => ({ ...p, state_of_origin: e.target.value }))} />
                      </label>
                      <label className="panel-field">
                        Local Government
                        <input value={editForm.local_government} onChange={(e) => setEditForm((p) => ({ ...p, local_government: e.target.value }))} />
                      </label>
                      <label className="panel-field full">
                        Home Address
                        <textarea value={editForm.home_address} onChange={(e) => setEditForm((p) => ({ ...p, home_address: e.target.value }))} placeholder="Street address, city, state, postal code" rows="2" />
                      </label>
                    </div>
                  </div>

                  {/* Guardian 1 */}
                  <div className="form-section">
                    <p className="form-section-label"><Users size={13} /> Primary Guardian</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        Guardian Name
                        <input value={editForm.guardian_name} onChange={(e) => setEditForm((p) => ({ ...p, guardian_name: e.target.value }))} required />
                      </label>
                      <label className="panel-field">
                        Relationship
                        <input value={editForm.guardian_relation} onChange={(e) => setEditForm((p) => ({ ...p, guardian_relation: e.target.value }))} placeholder="e.g., Father, Mother" />
                      </label>
                      <label className="panel-field">
                        Guardian Phone
                        <PhoneCountryInput
                          countries={countries}
                          value={editForm.guardian_phone}
                          onChange={(val) => setEditForm((p) => ({ ...p, guardian_phone: val }))}
                          defaultCountryCode={defaultCountryCode}
                        />
                      </label>
                      <label className="panel-field">
                        Guardian Email
                        <input type="email" value={editForm.guardian_email} onChange={(e) => setEditForm((p) => ({ ...p, guardian_email: e.target.value }))} />
                      </label>
                    </div>
                  </div>

                  {/* Guardian 2 */}
                  <div className="form-section">
                    <p className="form-section-label"><Users size={13} /> Secondary Guardian</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        Name
                        <input value={editForm.second_guardian_name} onChange={(e) => setEditForm((p) => ({ ...p, second_guardian_name: e.target.value }))} />
                      </label>
                      <label className="panel-field">
                        Relationship
                        <input value={editForm.second_guardian_relation} onChange={(e) => setEditForm((p) => ({ ...p, second_guardian_relation: e.target.value }))} placeholder="e.g., Uncle, Aunt" />
                      </label>
                      <label className="panel-field">
                        Phone
                        <PhoneCountryInput
                          countries={countries}
                          value={editForm.second_guardian_phone}
                          onChange={(val) => setEditForm((p) => ({ ...p, second_guardian_phone: val }))}
                          defaultCountryCode={defaultCountryCode}
                        />
                      </label>
                      <label className="panel-field">
                        Email
                        <input type="email" value={editForm.second_guardian_email} onChange={(e) => setEditForm((p) => ({ ...p, second_guardian_email: e.target.value }))} />
                      </label>
                    </div>
                  </div>

                  {/* Academic */}
                  <div className="form-section">
                    <p className="form-section-label"><GraduationCap size={13} /> Academic &amp; Activity</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        {groupLabels.singular}
                        <select value={editForm.class_id} onChange={(e) => setEditForm((p) => ({ ...p, class_id: e.target.value }))}>
                          <option value="">{groupLabels.unassigned}</option>
                          {classes.map((item) => (
                            <option key={item.id} value={item.id}>{item.label}</option>
                          ))}
                        </select>
                      </label>
                      <label className="panel-field">
                        Admission Date
                        <input type="date" value={editForm.admission_date} onChange={(e) => setEditForm((p) => ({ ...p, admission_date: e.target.value }))} />
                      </label>
                      <label className="panel-field">
                        Student Type
                        <input value={editForm.student_type} onChange={(e) => setEditForm((p) => ({ ...p, student_type: e.target.value }))} placeholder="e.g., Regular, Scholarship, Transfer" />
                      </label>
                      {nonK12 ? null : (
                        <label className="panel-field">
                          Activity Title
                          <select value={editForm.extra_curricular_activity_title_id} onChange={(e) => setEditForm((p) => ({ ...p, extra_curricular_activity_title_id: e.target.value }))}>
                            <option value="">No title</option>
                            {activeActivityTitles.map((item) => (
                              <option key={item.id} value={item.id}>{item.name} — {item.star_label || `${item.star_rating || 0} stars`}</option>
                            ))}
                            {editForm.extra_curricular_activity_title_id && !activeActivityTitles.some((item) => item.id === editForm.extra_curricular_activity_title_id) ? (
                              <option value={editForm.extra_curricular_activity_title_id}>Inactive title</option>
                            ) : null}
                          </select>
                        </label>
                      )}
                    </div>
                  </div>

                  {/* Health */}
                  <div className="form-section">
                    <p className="form-section-label"><Heart size={13} /> Health Information</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        Blood Group
                        <select value={editForm.blood_group} onChange={(e) => setEditForm((p) => ({ ...p, blood_group: e.target.value }))}>
                          <option value="">Select Blood Group</option>
                          <option value="O+">O+</option>
                          <option value="O-">O-</option>
                          <option value="A+">A+</option>
                          <option value="A-">A-</option>
                          <option value="B+">B+</option>
                          <option value="B-">B-</option>
                          <option value="AB+">AB+</option>
                          <option value="AB-">AB-</option>
                        </select>
                      </label>
                      <label className="panel-field">
                        Disability
                        <select value={editForm.disability} onChange={(e) => setEditForm((p) => ({ ...p, disability: e.target.value }))}>
                          <option value="no">No</option>
                          <option value="yes">Yes</option>
                        </select>
                      </label>
                      <label className="panel-field full">
                        Medical Records
                        <textarea value={editForm.medical_records} onChange={(e) => setEditForm((p) => ({ ...p, medical_records: e.target.value }))} placeholder="Any medical conditions, allergies, or special medical needs" rows="2" />
                      </label>
                    </div>
                  </div>

                  {/* Security */}
                  <div className="form-section">
                    <p className="form-section-label"><Lock size={13} /> Account &amp; Security</p>
                    <div className="panel-form-grid">
                      <label className="panel-field">
                        New Password <span style={{color:"#94a3b8",fontWeight:400}}>(optional)</span>
                        <div className="password-toggle-field">
                          <input
                            type={showEditPassword ? "text" : "password"}
                            placeholder="Leave blank to keep current"
                            value={editForm.student_password}
                            onChange={(e) => setEditForm((p) => ({ ...p, student_password: e.target.value }))}
                          />
                          <button type="button" onClick={() => setShowEditPassword((c) => !c)}>
                            {showEditPassword ? "Hide" : "Show"}
                          </button>
                        </div>
                      </label>
                      <label className="panel-field">
                        Confirm New Password
                        <div className="password-toggle-field">
                          <input
                            type={showEditConfirmPassword ? "text" : "password"}
                            placeholder="Repeat new password"
                            value={editForm.confirm_student_password}
                            onChange={(e) => setEditForm((p) => ({ ...p, confirm_student_password: e.target.value }))}
                          />
                          <button type="button" onClick={() => setShowEditConfirmPassword((c) => !c)}>
                            {showEditConfirmPassword ? "Hide" : "Show"}
                          </button>
                        </div>
                      </label>
                      <label className="panel-field checkbox-field">
                        <input
                          type="checkbox"
                          checked={editForm.is_active}
                          onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.checked }))}
                        />
                        Active account
                      </label>
                    </div>
                  </div>

                  {editError ? <p className="form-feedback error" style={{margin:"0.5rem 1.5rem 0"}}>{editError}</p> : null}
                  {editSuccess ? <p className="form-feedback success" style={{margin:"0.5rem 1.5rem 0"}}>{editSuccess}</p> : null}

                  <div className="panel-form-actions" style={{margin:"0.75rem 1.5rem 0",paddingTop:"1rem",borderTop:"1px solid #f1f5f9"}}>
                    <button type="submit" disabled={isUpdating}>
                      {isUpdating ? "Saving..." : "Update Student"}
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setSelectedStudentId("")} disabled={isUpdating}>
                      Cancel
                    </button>
                  </div>
                </form>
              </article>
            </div>
          ) : null}
        </>
      ) : null}

    </section>
  );
}

function AdminTeachersScreen({ data, school, loading, error, onRetry, onCreate, onUpdate, onDelete, countries = [], defaultCountryCode = "NG" }) {
  const teachers = data?.teachers || [];
  const employmentTypes = data?.options?.employment_types || [];
  const subjectOptions = data?.options?.subjects || [];
  const classOptions = data?.options?.classes || [];
  const groupLabels = academicGroupLabels(data?.school, school);
  const [form, setForm] = useState({
    teacher_email: "",
    first_name: "",
    last_name: "",
    gender: "",
    phone: "",
    teacher_password: "",
    confirm_teacher_password: "",
    specialization: "",
    qualification: "",
    years_of_experience: "0",
    monthly_salary: "",
    hire_date: "",
    employment_type: "full_time",
    subjects_text: "",
    subjects: [],
    classes: [],
  });
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [profileTeacher, setProfileTeacher] = useState(null);
  const [selectedTeacherId, setSelectedTeacherId] = useState("");
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    gender: "",
    employee_id: "",
    specialization: "",
    qualification: "",
    years_of_experience: "0",
    monthly_salary: "",
    hire_date: "",
    employment_type: "full_time",
    is_active: true,
    subjects_text: "",
    subjects: [],
    classes: [],
    teacher_password: "",
    confirm_teacher_password: "",
  });
  const [isUpdating, setIsUpdating] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const [isDeleting, setIsDeleting] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showEditPassword, setShowEditPassword] = useState(false);
  const [showEditConfirmPassword, setShowEditConfirmPassword] = useState(false);
  const [confirm, confirmDialog] = useConfirm();

  const toDateInputValue = (value) => {
    const raw = String(value || "");
    if (!raw) {
      return "";
    }
    return raw.slice(0, 10);
  };
  const formatTeacherMoney = (value) => `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString()}`;

  const buildEditForm = (teacher) => ({
    first_name: teacher?.first_name || "",
    last_name: teacher?.last_name || "",
    email: teacher?.email || "",
    phone: teacher?.phone || "",
    gender: teacher?.gender || "",
    employee_id: teacher?.employee_id || "",
    specialization: teacher?.specialization || "",
    qualification: teacher?.qualification || "",
    years_of_experience: String(teacher?.years_of_experience ?? 0),
    monthly_salary: teacher?.monthly_salary ?? "",
    hire_date: toDateInputValue(teacher?.hire_date),
    employment_type: teacher?.employment_type || "full_time",
    is_active: Boolean(teacher?.is_active),
    subjects_text: teacher?.subjects_text || "",
    subjects: (teacher?.subjects || []).map((item) => String(item.id)),
    classes: (teacher?.assigned_classes || []).map((item) => String(item.id)),
    teacher_password: "",
    confirm_teacher_password: "",
  });

  const filteredTeachers = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return teachers;
    }
    return teachers.filter((item) => {
      const subjectNames = (item.subjects || []).map((subject) => subject.name);
      const haystack = [item.name, item.email, item.employee_id, item.specialization, item.subjects_text, ...subjectNames]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [searchTerm, teachers]);

  const handleDelete = async (teacherId) => {
    if (!onDelete) {
      return;
    }
    const ok = await confirm({ title: "Delete Teacher", message: "Are you sure you want to delete this teacher? This action cannot be undone.", confirmLabel: "Delete", danger: true });
    if (!ok) {
      return;
    }
    setIsDeleting(teacherId);
    try {
      await onDelete(teacherId);
      setProfileTeacher((current) => (current?.id === teacherId ? null : current));
      if (selectedTeacherId === teacherId) {
        setSelectedTeacherId("");
      }
    } catch (deleteError) {
      setFormError(deleteError.message || "Could not delete teacher.");
    } finally {
      setIsDeleting("");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    event.stopPropagation();
    setFormError("");
    setFormSuccess("");
    
    // Validate required fields
    if (!form.teacher_email?.trim()) {
      setFormError("Email is required.");
      return;
    }
    const emailVal = form.teacher_email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(emailVal)) {
      setFormError("Enter a valid email address (e.g. teacher@gmail.com).");
      return;
    }
    if (/\.local$|@schooldom\.|@example\.|@test\.|@fake\./i.test(emailVal)) {
      setFormError("Use a real email address. Placeholder or internal domains are not allowed.");
      return;
    }
    if (!form.first_name?.trim()) {
      setFormError("First name is required.");
      return;
    }
    if (!form.last_name?.trim()) {
      setFormError("Last name is required.");
      return;
    }
    
    const password = (form.teacher_password || "").trim();
    const confirm = (form.confirm_teacher_password || "").trim();
    if (!password) {
      setFormError("Password is required for teacher accounts.");
      return;
    }
    if (!confirm) {
      setFormError("Confirm the teacher password.");
      return;
    }
    if (password !== confirm) {
      setFormError("Passwords do not match.");
      return;
    }
    if (
      password.length < 8 ||
      !/[A-Z]/.test(password) ||
      !/[a-z]/.test(password) ||
      !/[0-9]/.test(password)
    ) {
      setFormError("Password must be at least 8 characters and include uppercase, lowercase, and a number.");
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        ...form,
        teacher_email: form.teacher_email.trim().toLowerCase(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim(),
        gender: form.gender,
        teacher_password: password,
        confirm_teacher_password: confirm,
        years_of_experience: Number(form.years_of_experience || 0),
        monthly_salary: Number(form.monthly_salary || 0),
        subjects_text: form.subjects_text,
        subject_ids: form.subjects,
        class_ids: form.classes,
      };
      if (!payload.employee_id) {
        delete payload.employee_id;
      }
      if (!payload.specialization) {
        delete payload.specialization;
      }
      if (!payload.qualification) {
        delete payload.qualification;
      }
      if (!payload.phone) {
        delete payload.phone;
      }
      if (!payload.hire_date) {
        delete payload.hire_date;
      }
      const result = await onCreate(payload);
      setFormSuccess(result?.message || "Teacher created successfully.");
      setForm({
        teacher_email: "",
        first_name: "",
        last_name: "",
        gender: "",
        phone: "",
        teacher_password: "",
        confirm_teacher_password: "",
        employee_id: "",
        specialization: "",
        qualification: "",
        years_of_experience: "0",
        monthly_salary: "",
        hire_date: "",
        employment_type: "full_time",
        subjects_text: "",
        subjects: [],
        classes: [],
      });
      setShowPassword(false);
      setShowConfirmPassword(false);
    } catch (actionError) {
      setFormError(actionError.message || "Could not create teacher.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleStartEdit = (teacher) => {
    setSelectedTeacherId(teacher.id);
    setEditForm(buildEditForm(teacher));
    setEditError("");
    setEditSuccess("");
  };

  const handleUpdateSubmit = async (event) => {
    event.preventDefault();
    if (!selectedTeacherId) {
      return;
    }
    setIsUpdating(true);
    setEditError("");
    setEditSuccess("");
    const password = (editForm.teacher_password || "").trim();
    const confirm = (editForm.confirm_teacher_password || "").trim();
    if (password || confirm) {
      if (!password || !confirm) {
        setEditError("Enter and confirm the new password.");
        setIsUpdating(false);
        return;
      }
      if (password !== confirm) {
        setEditError("Passwords do not match.");
        setIsUpdating(false);
        return;
      }
      if (
        password.length < 8 ||
        !/[A-Z]/.test(password) ||
        !/[a-z]/.test(password) ||
        !/[0-9]/.test(password)
      ) {
        setEditError("Password must be at least 8 characters and include uppercase, lowercase, and a number.");
        setIsUpdating(false);
        return;
      }
    }
    try {
      const payload = {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        gender: editForm.gender,
        employee_id: editForm.employee_id.trim(),
        specialization: editForm.specialization.trim(),
        qualification: editForm.qualification.trim(),
        years_of_experience: Number(editForm.years_of_experience || 0),
        monthly_salary: Number(editForm.monthly_salary || 0),
        employment_type: editForm.employment_type,
        is_active: editForm.is_active,
        subjects_text: editForm.subjects_text,
        subject_ids: editForm.subjects,
        class_ids: editForm.classes,
      };
      if (password) {
        payload.teacher_password = password;
        payload.confirm_teacher_password = confirm;
      }
      if (editForm.hire_date) {
        payload.hire_date = editForm.hire_date;
      }
      const result = await onUpdate(selectedTeacherId, payload);
      if (result?.teacher) {
        setEditForm(buildEditForm(result.teacher));
      }
      setShowEditPassword(false);
      setShowEditConfirmPassword(false);
      setEditSuccess(result?.message || "Teacher updated.");
    } catch (actionError) {
      setEditError(actionError.message || "Could not update teacher.");
    } finally {
      setIsUpdating(false);
    }
  };

  useEffect(() => {
    if (!selectedTeacherId) {
      return;
    }
    const current = teachers.find((item) => item.id === selectedTeacherId);
    if (!current) {
      setSelectedTeacherId("");
      setEditError("");
      setEditSuccess("");
      return;
    }
    setEditForm(buildEditForm(current));
  }, [selectedTeacherId, teachers]);

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Teachers</h2>
        <p>Create and review teacher profiles.</p>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
      <article className="app-panel">
        <h3>Create Teacher</h3>
        <form className="panel-form" onSubmit={handleSubmit} noValidate>
          <div className="panel-form-grid">
            <label className="panel-field">
              Email <span style={{ color: "#ef4444", fontSize: "0.78rem", fontWeight: 600 }}>— must be a real email</span>
              <input
                type="email"
                value={form.teacher_email}
                onChange={(event) => setForm((prev) => ({ ...prev, teacher_email: event.target.value }))}
                placeholder="e.g. teacher@gmail.com"
                autoComplete="off"
              />
            </label>
            <label className="panel-field">
              First Name
              <input value={form.first_name} onChange={(event) => setForm((prev) => ({ ...prev, first_name: event.target.value }))} required />
            </label>
            <label className="panel-field">
              Last Name
              <input value={form.last_name} onChange={(event) => setForm((prev) => ({ ...prev, last_name: event.target.value }))} />
            </label>
            <label className="panel-field">
              Gender
              <select value={form.gender} onChange={(event) => setForm((prev) => ({ ...prev, gender: event.target.value }))}>
                <option value="">Select gender</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="O">Other</option>
                <option value="N">Prefer not to say</option>
              </select>
            </label>
            <label className="panel-field">
              Phone
              <PhoneCountryInput
                countries={countries}
                value={form.phone}
                onChange={(val) => setForm((prev) => ({ ...prev, phone: val }))}
                defaultCountryCode={defaultCountryCode}
              />
            </label>
            <label className="panel-field">
              Password
              <div className="password-wrap">
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.teacher_password}
                  onChange={(event) => setForm((prev) => ({ ...prev, teacher_password: event.target.value }))}
                  placeholder="Set login password"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
            <label className="panel-field">
              Confirm password
              <div className="password-wrap">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  value={form.confirm_teacher_password}
                  onChange={(event) => setForm((prev) => ({ ...prev, confirm_teacher_password: event.target.value }))}
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  aria-label={showConfirmPassword ? "Hide confirmation" : "Show confirmation"}
                >
                  {showConfirmPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
            <label className="panel-field">
              Employment
              <select value={form.employment_type} onChange={(event) => setForm((prev) => ({ ...prev, employment_type: event.target.value }))}>
                {employmentTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="panel-field full">
              <p className="field-note">
                Password must be at least 8 characters and include uppercase, lowercase, and a number.
              </p>
            </div>
                <label className="panel-field full">
                  Subjects (assign)
                  <MultiSelectBox
                    options={subjectOptions}
                    selected={form.subjects}
                    onChange={(values) => setForm((prev) => ({ ...prev, subjects: values }))}
                    labelForOption={(subject) => `${subject.name} (${subject.code})`}
                    emptyText="Go to classes to add a new subject."
                  />
                  <small className="field-note">Tick all subjects this teacher handles.</small>
                </label>
                <label className="panel-field full">
                  {groupLabels.plural} (optional)
                  <MultiSelectBox
                    options={classOptions}
                    selected={form.classes}
                    onChange={(values) => setForm((prev) => ({ ...prev, classes: values }))}
                    labelForOption={(item) => item.label || `${item.name}${item.section ? ` - ${item.section}` : ""}`}
                    emptyText={`No ${groupLabels.shortPlural.toLowerCase()} available.`}
                  />
                  <small className="field-note">Optional. Tick every {groupLabels.singular.toLowerCase()} assigned to this teacher.</small>
                </label>
                <label className="panel-field">
                  Experience (years)
                  <input type="number" min="0" value={form.years_of_experience} onChange={(event) => setForm((prev) => ({ ...prev, years_of_experience: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Monthly salary
                  <input type="number" min="0" step="0.01" value={form.monthly_salary} onChange={(event) => setForm((prev) => ({ ...prev, monthly_salary: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Hire Date
                  <input type="date" value={form.hire_date} onChange={(event) => setForm((prev) => ({ ...prev, hire_date: event.target.value }))} />
                </label>
                <label className="panel-field full">
                  Specialization (optional)
                  <textarea
                    rows={3}
                    value={form.specialization}
                    onChange={(event) => setForm((prev) => ({ ...prev, specialization: event.target.value }))}
                    placeholder="e.g. Mathematics and Further Mathematics"
                  />
                </label>
          </div>
{formError ? <p className="form-feedback error">{formError}</p> : null}
              {formSuccess ? <p className="form-feedback success">{formSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Create Teacher"}
</button>
          </div>
        </form>
      </article>

      <article className="app-panel">
        <h3>Teacher Directory</h3>
        <div className="directory-tools">
              <button
                type="button"
                className={`table-action filter-toggle ${showFilters ? "active" : ""}`}
                onClick={() => setShowFilters((previous) => !previous)}
              >
                <FilterIcon className="inline-icon" />
                Filter
              </button>
              {showFilters ? (
                <label className="panel-field full search-field">
                  Search by teacher ID, name, specialization, or email
                  <input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Example: TCH0021"
                  />
                </label>
              ) : null}
            </div>

            {filteredTeachers.length > 0 ? (
              <table className="data-table">
                <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Gender</th>
                <th>Employee ID</th>
                <th>Specialization</th>
                <th>Monthly Salary</th>
                <th>Subjects</th>
                <th>{groupLabels.plural}</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredTeachers.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button type="button" className="record-list-button" onClick={() => setProfileTeacher(item)}>
                      {item.name}
                    </button>
                  </td>
                  <td>{item.email}</td>
                  <td>{genderDisplay(item.gender)}</td>
                  <td>{item.employee_id}</td>
                  <td>{item.specialization}</td>
                  <td>{formatTeacherMoney(item.monthly_salary)}</td>
                  <td>
                    {(item.subjects || []).map((s) => s.name).join(", ") ||
                      item.subjects_text ||
                      "-"}
                  </td>
                  <td>
                    {(item.assigned_classes || []).map((classItem) => classItem.label || classItem.name).join(", ") || "-"}
                  </td>
                  <td>
                    <button type="button" className="table-action" onClick={() => handleStartEdit(item)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="table-action danger"
                      onClick={() => handleDelete(item.id)}
                      disabled={isDeleting === item.id}
                    >
                      {isDeleting === item.id ? "Deleting..." : "Delete"}
                    </button>
                  </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="panel-empty">{searchTerm ? "No teachers match your filter." : "No teachers found."}</p>
            )}
      </article>

          {profileTeacher ? (
            <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setProfileTeacher(null); }}>
              <ReadOnlyPersonProfile
                person={profileTeacher}
                title="Teacher profile"
                codeLabel="Employee ID"
                codeValue={profileTeacher.employee_id}
                onClose={() => setProfileTeacher(null)}
              />
            </div>
          ) : null}

          {selectedTeacherId ? (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-teacher-title" onClick={(e) => { if (e.target === e.currentTarget && !isUpdating) setSelectedTeacherId(""); }}>
            <article className="app-panel edit-modal-card">
              <div className="edit-modal-head">
                <div>
                  <h3 id="edit-teacher-title">Edit Teacher</h3>
                  <p>Update profile, subjects, classes and account settings</p>
                </div>
                <button type="button" className="edit-modal-close" onClick={() => setSelectedTeacherId("")} disabled={isUpdating} aria-label="Close"><X size={16} /></button>
              </div>
              <form className="panel-form" onSubmit={handleUpdateSubmit}>
                <div className="panel-form-grid">
                  <label className="panel-field">
                    First Name
                    <input value={editForm.first_name} onChange={(event) => setEditForm((prev) => ({ ...prev, first_name: event.target.value }))} required />
                  </label>
                  <label className="panel-field">
                    Last Name
                    <input value={editForm.last_name} onChange={(event) => setEditForm((prev) => ({ ...prev, last_name: event.target.value }))} required />
                  </label>
                  <label className="panel-field">
                    Email
                    <input value={editForm.email} onChange={(event) => setEditForm((prev) => ({ ...prev, email: event.target.value }))} required />
                  </label>
                  <label className="panel-field">
                    Phone
                    <PhoneCountryInput
                      countries={countries}
                      value={editForm.phone}
                      onChange={(val) => setEditForm((prev) => ({ ...prev, phone: val }))}
                      defaultCountryCode={defaultCountryCode}
                    />
                  </label>
                  <label className="panel-field">
                    Gender
                    <select value={editForm.gender} onChange={(event) => setEditForm((prev) => ({ ...prev, gender: event.target.value }))}>
                      <option value="">Select gender</option>
                      <option value="M">Male</option>
                      <option value="F">Female</option>
                      <option value="O">Other</option>
                      <option value="N">Prefer not to say</option>
                    </select>
                  </label>
                  <label className="panel-field">
                    Employee ID
                    <input value={editForm.employee_id} onChange={(event) => setEditForm((prev) => ({ ...prev, employee_id: event.target.value }))} required />
                  </label>
                  <label className="panel-field">
                    New password
                    <div className="password-wrap">
                      <input
                        type={showEditPassword ? "text" : "password"}
                        value={editForm.teacher_password}
                        onChange={(event) => setEditForm((prev) => ({ ...prev, teacher_password: event.target.value }))}
                        placeholder="Leave blank to keep current"
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowEditPassword((prev) => !prev)}
                        aria-label={showEditPassword ? "Hide password" : "Show password"}
                      >
                        {showEditPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                  </label>
                  <label className="panel-field">
                    Confirm new password
                    <div className="password-wrap">
                      <input
                        type={showEditConfirmPassword ? "text" : "password"}
                        value={editForm.confirm_teacher_password}
                        onChange={(event) => setEditForm((prev) => ({ ...prev, confirm_teacher_password: event.target.value }))}
                        placeholder="Repeat new password"
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowEditConfirmPassword((prev) => !prev)}
                        aria-label={showEditConfirmPassword ? "Hide confirmation" : "Show confirmation"}
                      >
                        {showEditConfirmPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                  </label>
                  <div className="panel-field full">
                    <p className="field-note">
                      Leave password fields blank unless you want to reset this teacher's login password.
                    </p>
                  </div>
                  <label className="panel-field">
                    Employment
                    <select value={editForm.employment_type} onChange={(event) => setEditForm((prev) => ({ ...prev, employment_type: event.target.value }))}>
                      {employmentTypes.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="panel-field full">
                    Subjects (assign)
                    <MultiSelectBox
                      options={subjectOptions}
                      selected={editForm.subjects}
                      onChange={(values) => setEditForm((prev) => ({ ...prev, subjects: values }))}
                      labelForOption={(subject) => `${subject.name} (${subject.code})`}
                      emptyText="Go to classes to add a new subject."
                    />
                    <small className="field-note">Tick all subjects this teacher handles.</small>
                  </label>
                  <label className="panel-field full">
                    Subjects (free text)
                    <textarea
                      value={editForm.subjects_text}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, subjects_text: event.target.value }))}
                      placeholder="Enter subjects e.g. English, Mathematics, Physics"
                    />
                    <small className="field-note">Comma or line separated; shown on teacher profile.</small>
                  </label>
                  <label className="panel-field full">
                    {groupLabels.plural} (optional)
                    <MultiSelectBox
                      options={classOptions}
                      selected={editForm.classes}
                      onChange={(values) => setEditForm((prev) => ({ ...prev, classes: values }))}
                      labelForOption={(item) => item.label || `${item.name}${item.section ? ` - ${item.section}` : ""}`}
                      emptyText={`No ${groupLabels.shortPlural.toLowerCase()} available.`}
                    />
                    <small className="field-note">Optional. Leave empty if the teacher is not tied to a {groupLabels.singular.toLowerCase()}.</small>
                  </label>
                  <label className="panel-field">
                    Experience (years)
                    <input type="number" min="0" value={editForm.years_of_experience} onChange={(event) => setEditForm((prev) => ({ ...prev, years_of_experience: event.target.value }))} />
                  </label>
                  <label className="panel-field">
                    Monthly salary
                    <input type="number" min="0" step="0.01" value={editForm.monthly_salary} onChange={(event) => setEditForm((prev) => ({ ...prev, monthly_salary: event.target.value }))} />
                  </label>
                  <label className="panel-field">
                    Hire Date
                    <input type="date" value={editForm.hire_date} onChange={(event) => setEditForm((prev) => ({ ...prev, hire_date: event.target.value }))} />
                  </label>
                  <label className="panel-field full">
                    Specialization
                    <textarea
                      rows={3}
                      value={editForm.specialization}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, specialization: event.target.value }))}
                      placeholder="e.g. Mathematics and Further Mathematics"
                    />
                  </label>
                  <label className="panel-field full">
                    Qualification
                    <input value={editForm.qualification} onChange={(event) => setEditForm((prev) => ({ ...prev, qualification: event.target.value }))} />
                  </label>
                  <label className="panel-field checkbox-field">
                    <input
                      type="checkbox"
                      checked={editForm.is_active}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, is_active: event.target.checked }))}
                    />
                    Active account
                  </label>
                </div>
                {editError ? <p className="form-feedback error">{editError}</p> : null}
                {editSuccess ? <p className="form-feedback success">{editSuccess}</p> : null}
                <div className="panel-form-actions">
                  <button type="submit" disabled={isUpdating}>
                    {isUpdating ? "Saving..." : "Update Teacher"}
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => setSelectedTeacherId("")} disabled={isUpdating}>
                    Cancel
                  </button>
                </div>
              </form>
            </article>
            </div>
          ) : null}
        </>
      ) : null}
      {confirmDialog}
    </section>
  );
}

function AdminEnrollmentsScreen({ data, loading, error, onRetry, onCreate }) {
  const enrollments = data?.enrollments || [];
  const students = data?.options?.students || [];
  const classes = data?.options?.classes || [];
  const exams = data?.options?.exams || [];
  const [form, setForm] = useState({
    student_id: "",
    class_id: "",
    exam_ids: [],
    welcome_subject: "Enrollment update",
    welcome_message: "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  const toggleExam = (examId) => {
    setForm((prev) => {
      const exists = prev.exam_ids.includes(examId);
      return {
        ...prev,
        exam_ids: exists ? prev.exam_ids.filter((id) => id !== examId) : [...prev.exam_ids, examId],
      };
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.student_id) {
      setFormError("Select a student.");
      return;
    }
    setIsSaving(true);
    try {
      const payload = { ...form };
      if (!payload.class_id) {
        delete payload.class_id;
      }
      const result = await onCreate(payload);
      setFormSuccess(result?.message || "Enrollment created.");
      setForm((prev) => ({
        ...prev,
        class_id: "",
        exam_ids: [],
        welcome_message: "",
      }));
    } catch (actionError) {
      setFormError(actionError.message || "Could not create enrollment.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Enrollments</h2>
        <p>Assign students to classes and exams.</p>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
      <article className="app-panel">
        <h3>Create Enrollment</h3>
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Student
              <select value={form.student_id} onChange={(event) => setForm((prev) => ({ ...prev, student_id: event.target.value }))} required>
                <option value="">Select student</option>
                {students.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.email})
                  </option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Class
              <select value={form.class_id} onChange={(event) => setForm((prev) => ({ ...prev, class_id: event.target.value }))}>
                <option value="">Unassigned</option>
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
<label className="panel-field full">
                  Welcome Subject
                  <input value={form.welcome_subject} onChange={(event) => setForm((prev) => ({ ...prev, welcome_subject: event.target.value }))} />
                </label>
                <label className="panel-field full">
                  Welcome Message
                  <textarea value={form.welcome_message} onChange={(event) => setForm((prev) => ({ ...prev, welcome_message: event.target.value }))} />
                </label>
          </div>
<div>
          <p className="field-note">Link Exams</p>
          <div className="segmented-control" style={{ flexWrap: "wrap" }}>
            {exams.map((exam) => (
              <button
                key={exam.id}
                type="button"
                className={form.exam_ids.includes(exam.id) ? "active" : ""}
                onClick={() => toggleExam(exam.id)}
              >
                {exam.title}
              </button>
            ))}
          </div>
</div>
              {formError ? <p className="form-feedback error">{formError}</p> : null}
              {formSuccess ? <p className="form-feedback success">{formSuccess}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Create Enrollment"}
</button>
          </div>
        </form>
      </article>

      <article className="app-panel">
        <h3>Enrollment Records</h3>
            {enrollments.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Class</th>
                    <th>Exam Count</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {enrollments.map((item) => (
                    <tr key={item.id}>
                      <td>{item.student_name}</td>
                      <td>{item.class_name}</td>
                      <td>{item.exam_count}</td>
                      <td>{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="panel-empty">No enrollment records found.</p>
            )}
      </article>
</>
      ) : null}
    </section>
  );
}

function AdminMessagesScreen({ user, data, loading, error, onRetry, onSendMessage, onMarkRead, onDelete }) {
  const summary = data?.summary || {};
  const announcements = data?.announcements || [];
  const recipients = data?.recipients || [];
  const recipientOptions = recipients
    .filter((item) => item?.email)
    .map((item) => ({
      value: item.email,
      label: `${item.name || item.email} - ${roleLabel(item.role)}`,
      name: item.name || item.email,
      role: roleLabel(item.role),
    }));

  const handleChatSend = async (recipientValue, subject, messageBody, _selectedRecipient, attachments = []) => {
    return onSendMessage?.({
      recipient_email: String(recipientValue || "").trim().toLowerCase(),
      subject: subject || "",
      body: messageBody,
      attachments,
    }, { refresh: true });
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Messages</h2>
        <p>Chat with students, teachers, and staff from one shared inbox.</p>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <div className="metric-grid">
            <MetricCard label="Unread Inbox" value={summary.unread_inbox ?? 0} trend="Direct messages" />
            <MetricCard label="Active Announcements" value={summary.active_announcements ?? announcements.length} trend="Published now" />
          </div>

          <MessageInboxPanel
            title="Admin Chat"
            messages={data?.inbox || data?.messages || []}
            recipientOptions={recipientOptions}
            onComposeSubmit={handleChatSend}
            onMarkRead={onMarkRead}
            onDelete={onDelete}
            onRefresh={onRetry}
          />

          <p className="panel-empty compact">Broadcast announcements are shown in the notifications popup.</p>
        </>
      ) : null}
    </section>
  );

}

function AdminDatabaseImportScreen({ data = {}, loading, error, onRetry, onUpload, onClear }) {
  const summary = data?.summary || {};
  const history = data?.history || [];
  const importTypes = data?.options?.import_types || [
    { value: "full_school", label: "Full school database" },
    { value: "students", label: "Student records" },
    { value: "teachers", label: "Teacher profiles" },
    { value: "classes_subjects", label: "Classes and subjects" },
    { value: "cbt_results", label: "CBT results" },
    { value: "attendance", label: "Attendance records" },
    { value: "payments", label: "Payment history" },
    { value: "documents", label: "Uploaded documents" },
    { value: "academic_records", label: "Academic records" },
  ];
  const linkKeys = data?.options?.link_keys || [
    { value: "admission_number", label: "Admission number" },
    { value: "student_id", label: "Student ID" },
    { value: "employee_id", label: "Employee ID" },
    { value: "email", label: "Email address" },
    { value: "filename", label: "Filename convention" },
  ];
  const [form, setForm] = useState({ import_type: "full_school", link_key: "admission_number", notes: "" });
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [confirm, confirmDialog] = useConfirm();

  const submitImport = async (event) => {
    event.preventDefault();
    if (!files.length) {
      setUploadError("Choose database export files, images, documents, or a folder.");
      return;
    }
    setBusy(true);
    setFeedback("");
    setUploadError("");
    try {
      const result = await onUpload?.({ ...form, file: files });
      setFeedback(result?.message || "Import uploaded for validation.");
      setFiles([]);
      setForm((current) => ({ ...current, notes: "" }));
    } catch (actionError) {
      setUploadError(actionError.message || "Could not upload import.");
    } finally {
      setBusy(false);
    }
  };

  const clearHistory = async () => {
    if (!onClear) return;
    const ok = await confirm({ title: "Clear Import History", message: "Clear all import history? This cannot be undone.", confirmLabel: "Clear all", danger: true });
    if (!ok) return;
    setClearing(true);
    setFeedback("");
    setUploadError("");
    try {
      const result = await onClear();
      setFeedback(result?.message || "Import history cleared.");
    } catch (err) {
      setUploadError(err.message || "Could not clear history.");
    } finally {
      setClearing(false);
    }
  };

  const acceptDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const dropped = Array.from(event.dataTransfer.files || []);
    if (dropped.length) {
      setFiles(dropped);
      setUploadError("");
    }
  };
  const selectedFileSize = files.reduce((total, item) => total + Number(item.size || 0), 0);

  return (
    <section className="screen-grid database-import-screen">
      <div className="screen-hero database-import-hero">
        <h2>School Database Import System</h2>
        <p>Securely migrate school data, academic records, media, and historical activity into SchoolDom.</p>
      </div>

      <ScreenState loading={loading && !history.length} error={error} onRetry={onRetry} />

      <div className="metric-grid">
        <MetricCard label="Imports" value={summary.total_imports ?? history.length} trend="Migration jobs" />
        <MetricCard label="Validated" value={summary.validated ?? 0} trend="Ready for review" />
        <MetricCard label="Needs Review" value={summary.needs_review ?? 0} trend="Mapping or format checks" />
        <MetricCard label="Latest" value={summary.latest_import_at ? formatDate(summary.latest_import_at) : "-"} trend="Most recent upload" />
      </div>

      <div className="database-import-layout">
        <article className="app-panel database-import-uploader">
          <div className="panel-head">
            <h3>Upload migration file</h3>
            <small>CSV, Excel, JSON, SQL backup, ZIP, images, and documents are accepted for admin review.</small>
          </div>
          <form className="panel-form" onSubmit={submitImport}>
            <div
              className={`migration-dropzone ${dragging ? "dragging" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={acceptDrop}
            >
              <div className="database-import-file-actions">
                <label className="table-action file-action">
                  Choose files
                  <input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} />
                </label>
                <label className="table-action file-action">
                  Choose folder
                  <input
                    type="file"
                    multiple
                    webkitdirectory=""
                    directory=""
                    onChange={(event) => setFiles(Array.from(event.target.files || []))}
                  />
                </label>
                {files.length > 0 && (
                  <button type="button" className="table-action" onClick={() => { setFiles([]); setUploadError(""); setFeedback(""); }}>
                    Clear
                  </button>
                )}
              </div>
              <strong>{files.length ? `${files.length} file${files.length === 1 ? "" : "s"} selected` : "Drop files or a folder here"}</strong>
              <span>
                {files.length
                  ? `${Math.ceil(selectedFileSize / 1024).toLocaleString()} KB selected`
                  : "or click to browse files/folders from your device"}
              </span>
              {files.length ? <small>{files.slice(0, 4).map((item) => item.webkitRelativePath || item.name).join(", ")}{files.length > 4 ? `, +${files.length - 4} more` : ""}</small> : null}
            </div>

            <div className="panel-form-grid">
              <label className="panel-field">
                Import category
                <select value={form.import_type} onChange={(event) => setForm((current) => ({ ...current, import_type: event.target.value }))}>
                  {importTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label className="panel-field">
                Link images/documents by
                <select value={form.link_key} onChange={(event) => setForm((current) => ({ ...current, link_key: event.target.value }))}>
                  {linkKeys.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label className="panel-field full">
                Migration notes
                <textarea value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Mention column names, image naming patterns, or special mapping instructions." />
              </label>
            </div>
            {uploadError ? <p className="form-feedback error">{uploadError}</p> : null}
            {feedback ? <p className="form-feedback success">{feedback}</p> : null}
            <div className="panel-form-actions">
              <button type="submit" disabled={busy}>{busy ? "Validating..." : "Upload and validate"}</button>
            </div>
          </form>
        </article>

        <article className="app-panel migration-safety-panel">
          <h3>Secure migration workflow</h3>
          <div className="migration-status-list">
            <div><strong>Admin only</strong><span>Teacher, student, staff, and parent accounts are blocked.</span></div>
            <div><strong>Safe SQL handling</strong><span>SQL backups are inspected and stored, never executed from upload.</span></div>
            <div><strong>Media linking</strong><span>Passports, logos, certificates, and documents can be matched by ID, email, or filename.</span></div>
            <div><strong>Review before apply</strong><span>Every import has validation status, summary, and errors.</span></div>
          </div>
        </article>
      </div>

      <article className="app-panel">
        <div className="panel-head">
          <h3>Recent import history</h3>
          <small>Validation summaries from recent migration uploads.</small>
          {history.length > 0 && (
            <button type="button" className="table-action" onClick={clearHistory} disabled={clearing} style={{ marginLeft: "auto" }}>
              {clearing ? "Clearing…" : "Clear history"}
            </button>
          )}
        </div>
        {history.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Detected</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {history.map((job) => (
                  <tr key={job.id}>
                    <td>{job.original_filename}<br /><small>{Number(job.file_size || 0).toLocaleString()} bytes</small></td>
                    <td>{job.import_type_label || job.import_type}</td>
                    <td><span className={`student-status-pill status-${job.status === "validated" ? "present" : "unmarked"}`}>{job.status}</span></td>
                    <td>
                      {(job.summary?.format || "file").toUpperCase()}
                      {job.summary?.file_count ? <small>{job.summary.file_count} files in ZIP</small> : null}
                      {job.summary?.student_image_import ? <small>{job.summary.student_image_import.created_or_updated || 0} student records created/updated</small> : null}
                      {job.errors?.length ? <small>{job.errors[0]}</small> : null}
                    </td>
                    <td>{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="panel-empty">No database imports have been uploaded yet.</p>
        )}
      </article>
      {confirmDialog}
    </section>
  );
}

export {
  AdminDashboardScreen,
  AdminPerformanceHeatmapScreen,
  AdminFinanceScreen,
  AdminExamResultsScreen,
  AdminTimetablesScreen,
  AdminResultsScreen,
  AdminTableScreen,
  AdminClassesScreen,
  AdminHRPayrollScreen,
  AdminNonTeachingStaffScreen,
  AdminHRActivityScreen,
  AdminIdCardsScreen,
  AdminDocumentsScreen,
  AdminSettingsScreen,
  AdminParentsScreen,
  AdminStudentsScreen,
  AdminTeachersScreen,
  AdminEnrollmentsScreen,
  AdminMessagesScreen,
  AdminDatabaseImportScreen,
  AdminLoanApplicationScreen,
  AdminSmsWalletScreen,
};

// ─── Child Monitor (standalone, kept for reference) ──────────────────────────

function usePaystackPopup() {
  const [loaded, setLoaded] = useState(!!window.PaystackPop);
  useEffect(() => {
    if (window.PaystackPop) { setLoaded(true); return; }
    const script = document.createElement("script");
    script.src = "https://js.paystack.co/v1/inline.js";
    script.onload = () => setLoaded(true);
    document.head.appendChild(script);
    return () => {};
  }, []);
  return loaded;
}

function AdminKidsMonitorScreen({ data, loading, error, onRetry, onInitiate, onVerify, onDeactivate, session }) {
  const [confirm, confirmDialog] = useConfirm();
  const [paying, setPaying] = useState(null);
  const paystackReady = usePaystackPopup();

  const parents = data?.parents || [];
  const publicKey = data?.paystack_public_key || "";
  const price = data?.price || 1000;

  if (loading && !data) return <section className="screen-grid"><div className="panel"><p className="panel-empty">Loading Kids Monitor…</p></div></section>;
  if (error) return (
    <section className="screen-grid">
      <div className="panel">
        <p className="panel-empty">{error}</p>
        <button type="button" className="btn" onClick={onRetry}>Retry</button>
      </div>
    </section>
  );

  const handleToggleOn = async (parent) => {
    if (!paystackReady) {
      alert("Payment system not ready yet. Please wait a moment and try again.");
      return;
    }
    setPaying(parent.id);
    try {
      const result = await onInitiate(parent.id);
      if (!result?.success) {
        alert(result?.message || "Failed to initiate payment.");
        return;
      }
      if (result.already_paid && result.monitor_active) {
        alert(result.message || "Child Monitor activated from your previous payment.");
        await onVerify(parent.id, result.reference);
        return;
      }
      const verifyPayment = (tx) => {
        const ref = tx?.reference || result.reference;
        onVerify(parent.id, ref).then((verifyResult) => {
          if (!verifyResult?.success) {
            alert(verifyResult?.message || "Payment verification failed. Contact support.");
          }
        });
      };
      const handler = window.PaystackPop.setup({
        key: publicKey,
        email: parent.email,
        amount: price * 100,
        ref: result.reference,
        metadata: { parent_id: parent.id, type: "kids_monitor" },
        // Paystack inline v1 fires `callback`; keep onSuccess for v2 compatibility.
        callback: verifyPayment,
        onSuccess: verifyPayment,
        onClose: () => {},
        onCancel: () => {},
      });
      handler.openIframe();
    } catch {
      alert("An error occurred. Please try again.");
    } finally {
      setPaying(null);
    }
  };

  const handleToggleOff = async (parent) => {
    const ok = await confirm({
      title: "Deactivate Kids Monitor",
      message: `Stop SMS attendance alerts for ${parent.name}? You'll need to pay again to re-enable.`,
      confirmLabel: "Deactivate",
      danger: true,
    });
    if (!ok) return;
    const result = await onDeactivate(parent.id);
    if (!result?.success) alert(result?.message || "Failed to deactivate.");
  };

  return (
    <section className="screen-grid">
      {confirmDialog}
      <div className="panel km-header-panel">
        <div className="km-header">
          <div>
            <h2 className="panel-title">Kids Monitor</h2>
            <p className="panel-subtitle">
              Enable SMS attendance alerts for parents — ₦{price.toLocaleString()} per parent.
              When a child&apos;s attendance is marked (present, absent or late), the parent receives an instant SMS.
            </p>
          </div>
          <div className="km-stats">
            <div className="km-stat-card">
              <span className="km-stat-num">{parents.filter((p) => p.monitor_active).length}</span>
              <span className="km-stat-label">Active</span>
            </div>
            <div className="km-stat-card">
              <span className="km-stat-num">{parents.length}</span>
              <span className="km-stat-label">Total Parents</span>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        {!parents.length ? (
          <p className="panel-empty">No parents in the directory yet. Add parents first.</p>
        ) : (
          <div className="table-responsive">
            <table className="data-table km-table">
              <thead>
                <tr>
                  <th>Parent</th>
                  <th>Phone</th>
                  <th>Ward(s)</th>
                  <th>Kids Monitor</th>
                </tr>
              </thead>
              <tbody>
                {parents.map((parent) => (
                  <tr key={parent.id}>
                    <td>
                      <strong>{parent.name}</strong>
                      <small>{parent.email}</small>
                    </td>
                    <td>{parent.phone || <span className="text-muted">—</span>}</td>
                    <td>
                      {parent.wards.length ? (
                        <div className="km-wards">
                          {parent.wards.map((w, i) => (
                            <span key={i} className="km-ward-chip">
                              {w.name} <em>{w.class_name}</em>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted">No wards linked</span>
                      )}
                    </td>
                    <td>
                      <div className="km-toggle-cell">
                        {parent.monitor_active ? (
                          <>
                            <span className="km-badge km-badge--active">Active</span>
                            <button
                              type="button"
                              className="btn btn-sm btn-outline-danger"
                              onClick={() => handleToggleOff(parent)}
                            >
                              Deactivate
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            className={`btn btn-sm btn-primary km-enable-btn${paying === parent.id ? " loading" : ""}`}
                            onClick={() => handleToggleOn(parent)}
                            disabled={paying === parent.id || !parent.phone}
                            title={!parent.phone ? "Parent has no phone number on file" : ""}
                          >
                            {paying === parent.id ? "Processing…" : `Enable — ₦${price.toLocaleString()}`}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}



