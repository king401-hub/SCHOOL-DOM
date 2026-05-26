import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const api = window.schoolDomCbt;
const NAIRA_SYMBOL = "\u20A6";

const fallbackApi = {
  bootstrap: async () => ({
    appName: "SchoolDom CBT Client",
    cloudUrl: "http://127.0.0.1:8000",
    snapshot: { exams: [], students: [], sessions: [], queueCount: 0, settings: {} },
  }),
};

function secondsLeft(endsAt) {
  return Math.max(0, Math.floor((new Date(endsAt).getTime() - Date.now()) / 1000));
}

function formatTime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function normalizeQuestions(exam) {
  const payload = exam?.payload || exam || {};
  const questions = payload.questions || payload.question_rows || payload.items || [];
  return questions.map((question, index) => ({
    id: String(question.id || question.question_id || index + 1),
    number: index + 1,
    text: question.text || question.question || question.prompt || `Question ${index + 1}`,
    type: question.type || question.question_type || "multiple_choice",
    options: question.options || question.choices || [],
    marks: question.marks || question.score || 1,
  }));
}

export default function App() {
  const bridge = api || fallbackApi;
  const [booting, setBooting] = useState(true);
  const [mode, setMode] = useState("student");
  const [cloudUrl, setCloudUrl] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [fallbackPin, setFallbackPin] = useState("");
  const [snapshot, setSnapshot] = useState({ exams: [], students: [], sessions: [], queueCount: 0, settings: {} });
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");
  const [studentContext, setStudentContext] = useState(null);
  const [examPayload, setExamPayload] = useState(null);
  const [phase, setPhase] = useState("login");

  const refreshSnapshot = useCallback(async () => {
    if (!api) return;
    const nextSnapshot = await api.admin.getSnapshot();
    setSnapshot(nextSnapshot);
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const boot = await bridge.bootstrap();
        if (!active) return;
        setCloudUrl(boot.cloudUrl || "");
        setSnapshot(boot.snapshot || {});
      } catch (bootError) {
        setError(bootError.message || "Could not start SchoolDom CBT Client.");
      } finally {
        setTimeout(() => active && setBooting(false), 650);
      }
    })();
    return () => {
      active = false;
    };
  }, [bridge]);

  useEffect(() => {
    const interval = setInterval(() => {
      refreshSnapshot().catch(() => null);
    }, 5000);
    return () => clearInterval(interval);
  }, [refreshSnapshot]);

  async function syncFromCloud() {
    setError("");
    setSyncMessage("Syncing published exams, students, subjects, timings, and PINs...");
    try {
      const result = await api.admin.syncFromCloud({ cloudUrl, accessToken, fallbackPin });
      setSnapshot(result);
      setSyncMessage("Cloud sync complete. Exams are available offline.");
    } catch (syncError) {
      setError(syncError.message || "Cloud sync failed.");
      setSyncMessage("");
    }
  }

  async function pushResults() {
    setError("");
    setSyncMessage("Pushing pending CBT results to SchoolDom cloud...");
    try {
      const result = await api.admin.pushResults({ cloudUrl, accessToken });
      setSnapshot(result.snapshot);
      setSyncMessage(`Synced ${result.synced} result(s). ${result.failures?.length ? `${result.failures.length} still pending.` : "Queue clear."}`);
    } catch (pushError) {
      setError(pushError.message || "Result sync failed.");
      setSyncMessage("");
    }
  }

  async function importExamPackage() {
    setError("");
    setSyncMessage("Opening offline CBT package...");
    try {
      const result = await api.admin.importExamPackage();
      if (result.canceled) {
        setSyncMessage("");
        return;
      }
      setSnapshot(result.snapshot);
      setSyncMessage(`Imported ${result.imported.exams} exam(s) and ${result.imported.students} student(s).`);
    } catch (importError) {
      setError(importError.message || "Could not import CBT package.");
      setSyncMessage("");
    }
  }

  async function exportResultsPackage() {
    setError("");
    setSyncMessage("Preparing result package...");
    try {
      const result = await api.admin.exportResultsPackage();
      if (result.canceled) {
        setSyncMessage("");
        return;
      }
      setSyncMessage(`Exported ${result.summary?.pending_results || 0} pending result(s).`);
    } catch (exportError) {
      setError(exportError.message || "Could not export result package.");
      setSyncMessage("");
    }
  }

  async function handleStudentLogin(payload) {
    setError("");
    const result = await api.student.login(payload);
    if (!result.success) {
      setError(result.message || "Login failed.");
      return;
    }
    setStudentContext(result);
    const examResult = await api.student.getExam(result.exam.id);
    if (!examResult.success) {
      setError(examResult.message || "Could not open exam.");
      return;
    }
    setExamPayload(examResult.exam);
    setPhase("instructions");
  }

  if (booting) return <SplashScreen />;

  return (
    <main className="app-shell">
      <aside className="side-rail">
        <div className="brand-lockup">
          <span>SD</span>
          <div>
            <strong>SchoolDom</strong>
            <small>CBT Client</small>
          </div>
        </div>
        <nav>
          <button className={mode === "student" ? "active" : ""} onClick={() => setMode("student")}>Student Exam</button>
          <button className={mode === "admin" ? "active" : ""} onClick={() => setMode("admin")}>Admin Sync</button>
          <button className={mode === "status" ? "active" : ""} onClick={() => setMode("status")}>Sync Status</button>
        </nav>
        <SyncBadge queueCount={snapshot?.queueCount || 0} />
      </aside>

      <section className="main-stage">
        {error ? <div className="error-banner">{error}<button onClick={() => setError("")}>Dismiss</button></div> : null}
        {mode === "admin" ? (
          <AdminDashboard
            accessToken={accessToken}
            cloudUrl={cloudUrl}
            snapshot={snapshot}
            syncMessage={syncMessage}
            onAccessToken={setAccessToken}
            onCloudUrl={setCloudUrl}
            fallbackPin={fallbackPin}
            onPushResults={pushResults}
            onImportPackage={importExamPackage}
            onExportResults={exportResultsPackage}
            onFallbackPin={setFallbackPin}
            onRefresh={refreshSnapshot}
            onSync={syncFromCloud}
          />
        ) : mode === "status" ? (
          <SyncStatus snapshot={snapshot} onCleanup={async () => {
            await api.admin.cleanupCache();
            await refreshSnapshot();
          }} />
        ) : (
          <StudentWorkspace
            phase={phase}
            setPhase={setPhase}
            context={studentContext}
            examPayload={examPayload}
            onLogin={handleStudentLogin}
            onExit={() => {
              setStudentContext(null);
              setExamPayload(null);
              setPhase("login");
              api?.window?.exitFullscreen?.();
            }}
          />
        )}
      </section>
    </main>
  );
}

function SplashScreen() {
  return (
    <div className="splash-screen">
      <div className="splash-mark">SD</div>
      <h1>SchoolDom CBT Client</h1>
      <p>Starting secure offline examination workspace...</p>
    </div>
  );
}

function SyncBadge({ queueCount }) {
  const online = typeof navigator !== "undefined" ? navigator.onLine : false;
  const label = queueCount ? "Pending Sync" : online ? "Online" : "Offline";
  return (
    <div className={`sync-badge ${queueCount ? "pending" : online ? "online" : "offline"}`}>
      <strong>{label}</strong>
      <small>Offline desktop mode</small>
    </div>
  );
}

function AdminDashboard(props) {
  const { accessToken, cloudUrl, fallbackPin, snapshot, syncMessage, onAccessToken, onCloudUrl, onExportResults, onFallbackPin, onImportPackage, onPushResults, onRefresh, onSync } = props;
  const [lanName, setLanName] = useState(snapshot.settings?.lanName || "School CBT Room");
  const [lanInstructions, setLanInstructions] = useState(snapshot.settings?.lanInstructions || "Admin will set Wi-Fi, hotspot, or lab network access manually.");
  const submitted = snapshot.sessions?.filter((item) => item.status === "submitted").length || 0;
  const inProgress = snapshot.sessions?.filter((item) => item.status === "in_progress").length || 0;
  useEffect(() => {
    setLanName(snapshot.settings?.lanName || "School CBT Room");
    setLanInstructions(snapshot.settings?.lanInstructions || "Admin will set Wi-Fi, hotspot, or lab network access manually.");
  }, [snapshot.settings?.lanInstructions, snapshot.settings?.lanName]);
  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <p>Admin desktop</p>
          <h1>Prepare fully offline CBT sessions</h1>
        </div>
        <button onClick={onRefresh}>Refresh Local Data</button>
      </header>

      <div className="metric-grid">
        <Metric label="Published Exams" value={snapshot.exams?.length || 0} />
        <Metric label="Synced Students" value={snapshot.students?.length || 0} />
        <Metric label="In Progress" value={inProgress} />
        <Metric label="Submitted" value={submitted} />
      </div>

      <section className="panel sync-panel">
        <div className="panel-head">
          <h2>Exam Package</h2>
          <span>{snapshot.settings?.lastSyncAt ? `Last sync ${new Date(snapshot.settings.lastSyncAt).toLocaleString()}` : "Not synced yet"}</span>
        </div>
        <div className="form-grid">
          <label>
            SchoolDom Cloud URL
            <input value={cloudUrl} onChange={(event) => onCloudUrl(event.target.value)} placeholder="https://school.example.com" />
          </label>
          <label>
            JWT Access Token
            <input value={accessToken} onChange={(event) => onAccessToken(event.target.value)} placeholder="Paste admin JWT token" type="password" />
          </label>
          <label>
            Offline Exam PIN
            <input value={fallbackPin} onChange={(event) => onFallbackPin(event.target.value)} placeholder="Optional fallback PIN for this synced package" type="password" />
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={onImportPackage}>Import Exam Package</button>
          <button onClick={onExportResults}>Export Results Package</button>
          <button className="primary-button" onClick={onSync}>Sync Published Exams</button>
          <button onClick={onPushResults}>Sync Pending Results</button>
        </div>
        {syncMessage ? <p className="success-text">{syncMessage}</p> : null}
      </section>

      <div className="two-column">
        <section className="panel">
          <div className="panel-head">
            <h2>Manual LAN Setup</h2>
            <span>Admin controlled</span>
          </div>
          <label>
            Session / Network Name
            <input value={lanName} onChange={(event) => setLanName(event.target.value)} placeholder="Example: JSS2 CBT Lab" />
          </label>
          <label>
            Admin LAN Notes
            <textarea value={lanInstructions} onChange={(event) => setLanInstructions(event.target.value)} rows="4" />
          </label>
          <button onClick={async () => {
            await api.admin.saveOfflineSettings({ lanName, lanInstructions, cloudUrl });
            await onRefresh();
          }}>Save Offline Settings</button>
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Live Student Monitoring</h2>
            <span>{snapshot.sessions?.length || 0} sessions</span>
          </div>
          <div className="compact-table">
            {(snapshot.sessions || []).slice(0, 8).map((session) => (
              <div key={session.id}>
                <span>{session.student_id}</span>
                <strong>{session.status}</strong>
                <small>{session.sync_status}</small>
              </div>
            ))}
            {!snapshot.sessions?.length ? <p>No active student sessions yet.</p> : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function StudentWorkspace({ phase, setPhase, context, examPayload, onLogin, onExit }) {
  if (phase === "login") return <StudentLogin onLogin={onLogin} />;
  if (phase === "instructions") return <Instructions context={context} onStart={() => setPhase("exam")} />;
  if (phase === "summary") return <Summary context={context} onExit={onExit} />;
  return <ExamInterface context={context} examPayload={examPayload} onSubmitted={() => setPhase("summary")} />;
}

function StudentLogin({ onLogin }) {
  const [studentId, setStudentId] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="login-screen">
      <section className="login-card">
        <p>Secure student login</p>
        <h1>Start CBT Exam</h1>
        <label>Student ID<input value={studentId} onChange={(event) => setStudentId(event.target.value)} autoFocus /></label>
        <label>Exam PIN<input value={pin} onChange={(event) => setPin(event.target.value)} type="password" /></label>
        <button className="primary-button" disabled={busy} onClick={async () => {
          setBusy(true);
          try {
            await onLogin({ studentId, pin });
          } finally {
            setBusy(false);
          }
        }}>{busy ? "Checking..." : "Continue"}</button>
      </section>
    </div>
  );
}

function Instructions({ context, onStart }) {
  return (
    <div className="screen narrow">
      <section className="panel instructions">
        <p>{context.student.full_name} - {context.student.student_id}</p>
        <h1>{context.exam.title}</h1>
        <h2>Exam Instructions</h2>
        <div className="instruction-box">{context.exam.instructions || "Answer all questions. Do not leave fullscreen mode during the examination."}</div>
        <ul>
          <li>Answers are auto-saved every second to this computer.</li>
          <li>The exam can resume after crash or power failure.</li>
          <li>Focus loss, window switching, and unauthorized actions are logged.</li>
          <li>The paper submits automatically when the timer ends.</li>
        </ul>
        <button className="primary-button" onClick={async () => {
          await api?.window?.enterFullscreen?.();
          onStart();
        }}>Enter Fullscreen and Start</button>
      </section>
    </div>
  );
}

function ExamInterface({ context, examPayload, onSubmitted }) {
  const questions = useMemo(() => normalizeQuestions(examPayload), [examPayload]);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState(context.session.answers || {});
  const [remaining, setRemaining] = useState(secondsLeft(context.session.ends_at));
  const answersRef = useRef(answers);
  answersRef.current = answers;

  const submit = useCallback(async (cause = "student_submit") => {
    await api.student.saveAnswers({ sessionId: context.session.id, answers: answersRef.current });
    await api.student.submit({ sessionId: context.session.id, cause });
    await api.window.exitFullscreen();
    onSubmitted();
  }, [context.session.id, onSubmitted]);

  useEffect(() => {
    const tick = setInterval(() => {
      const next = secondsLeft(context.session.ends_at);
      setRemaining(next);
      if (next <= 0) {
        clearInterval(tick);
        submit("timer_elapsed");
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [context.session.ends_at, submit]);

  useEffect(() => {
    const saver = setInterval(() => {
      api.student.saveAnswers({ sessionId: context.session.id, answers: answersRef.current }).catch(() => null);
    }, 1000);
    return () => clearInterval(saver);
  }, [context.session.id]);

  useEffect(() => {
    const onBlur = () => api.student.focusLoss({ sessionId: context.session.id, reason: "window_blur" }).catch(() => null);
    const block = (event) => {
      if ((event.ctrlKey || event.metaKey) && ["r", "l", "n", "t", "w"].includes(event.key.toLowerCase())) {
        event.preventDefault();
        api.student.focusLoss({ sessionId: context.session.id, reason: `blocked_shortcut_${event.key}` }).catch(() => null);
      }
    };
    window.addEventListener("blur", onBlur);
    window.addEventListener("keydown", block);
    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("keydown", block);
    };
  }, [context.session.id]);

  const question = questions[current] || {};
  const answered = Object.values(answers).filter((value) => String(value || "").trim()).length;

  return (
    <div className="exam-layout">
      <header className="exam-topbar">
        <div><strong>{context.exam.title}</strong><span>{context.student.full_name}</span></div>
        <div className={remaining < 300 ? "timer danger" : "timer"}>{formatTime(remaining)}</div>
        <button onClick={() => submit("student_submit")}>Submit Exam</button>
      </header>
      <aside className="question-palette">
        <strong>Questions</strong>
        <div>
          {questions.map((item, index) => (
            <button key={item.id} className={`${index === current ? "active" : ""} ${answers[item.id] ? "answered" : ""}`} onClick={() => setCurrent(index)}>{item.number}</button>
          ))}
        </div>
        <small>{answered} of {questions.length} answered</small>
      </aside>
      <section className="question-stage">
        <div className="question-card">
          <p>Question {question.number} - {question.type?.replaceAll("_", " ")}</p>
          <h1>{question.text}</h1>
          <AnswerControl question={question} value={answers[question.id] || ""} onChange={(value) => setAnswers((currentAnswers) => ({ ...currentAnswers, [question.id]: value }))} />
        </div>
        <div className="exam-actions">
          <button disabled={current === 0} onClick={() => setCurrent((value) => Math.max(0, value - 1))}>Previous</button>
          <button className="primary-button" disabled={current >= questions.length - 1} onClick={() => setCurrent((value) => Math.min(questions.length - 1, value + 1))}>Next</button>
        </div>
      </section>
    </div>
  );
}

function AnswerControl({ question, value, onChange }) {
  if (question.type === "theory" || question.type === "essay") {
    return <textarea className="theory-input" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Type your answer here..." />;
  }
  if (question.type === "fill_blank" || question.type === "fill_in_the_blank") {
    return <input className="answer-input" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Enter answer" />;
  }
  const options = question.type === "true_false" ? ["True", "False"] : question.options;
  return (
    <div className="option-list">
      {options.map((option, index) => {
        const label = typeof option === "string" ? option : option.text || option.label || option.value;
        const storedValue = question.type === "true_false" ? label : String(index);
        return (
          <button key={`${label}-${index}`} className={String(value) === String(storedValue) ? "selected" : ""} onClick={() => onChange(storedValue)}>
            <span>{String.fromCharCode(65 + index)}</span>{label}
          </button>
        );
      })}
    </div>
  );
}

function Summary({ context, onExit }) {
  return (
    <div className="screen narrow">
      <section className="panel summary-card">
        <div className="success-mark">✓</div>
        <h1>Submission Saved</h1>
        <p>{context.student.full_name}, your exam has been submitted locally. Results will sync to SchoolDom cloud when internet is available.</p>
        <div className="summary-grid">
          <span>Student ID<strong>{context.student.student_id}</strong></span>
          <span>Exam<strong>{context.exam.title}</strong></span>
          <span>Status<strong>Pending cloud sync</strong></span>
        </div>
        <button className="primary-button" onClick={onExit}>Return to Login</button>
      </section>
    </div>
  );
}

function SyncStatus({ snapshot, onCleanup }) {
  return (
    <div className="screen">
      <header className="screen-head">
        <div>
          <p>Offline reliability</p>
          <h1>Sync status and local recovery</h1>
        </div>
        <button onClick={onCleanup}>Cleanup Synced Cache</button>
      </header>
      <div className="metric-grid">
        <Metric label="Pending Sync" value={snapshot.queueCount || 0} />
        <Metric label="Local Sessions" value={snapshot.sessions?.length || 0} />
        <Metric label="LAN Mode" value="Manual" />
        <Metric label="Storage" value="Encrypted" />
      </div>
      <section className="panel">
        <div className="panel-head"><h2>Error Recovery</h2><span>Crash-safe autosave</span></div>
        <p className="muted">Every exam session is saved to SQLite once per second. If power fails, students log in again with the same Student ID and PIN to resume their saved session.</p>
      </section>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
