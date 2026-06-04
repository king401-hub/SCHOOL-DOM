import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const api = window.schoolDomCbt;
const NAIRA_SYMBOL = "\u20A6";

const fallbackApi = {
  bootstrap: async () => ({
    appName: "SchoolDom Student CBT",
    appVersion: "0.1.0",
    cloudUrl: "http://127.0.0.1:8000",
    snapshot: { exams: [], students: [], sessions: [], queueCount: 0, settings: {} },
  }),
  updates: {
    check: async () => ({ currentVersion: "0.1.0", latestVersion: "0.1.0", updateAvailable: false }),
    download: async () => ({ success: true }),
  },
  discoverRooms: async () => [],
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

function normalizeLanServerUrl(value) {
  const trimmed = String(value || "").trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  return /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
}

async function lanRequest(serverUrl, path, options = {}) {
  const response = await fetch(`${normalizeLanServerUrl(serverUrl)}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || `Admin server request failed (${response.status}).`);
  return payload;
}

async function saveStudentAnswers(context, answers) {
  if (context.lanServerUrl) {
    return lanRequest(context.lanServerUrl, `/api/sessions/${encodeURIComponent(context.session.id)}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
  }
  return api.student.saveAnswers({ sessionId: context.session.id, answers });
}

async function submitStudentExam(context, answers, cause) {
  if (context.lanServerUrl) {
    return lanRequest(context.lanServerUrl, `/api/sessions/${encodeURIComponent(context.session.id)}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers, cause }),
    });
  }
  await api.student.saveAnswers({ sessionId: context.session.id, answers });
  return api.student.submit({ sessionId: context.session.id, cause });
}

async function logStudentFocusLoss(context, reason) {
  if (context.lanServerUrl) {
    return lanRequest(context.lanServerUrl, `/api/sessions/${encodeURIComponent(context.session.id)}/focus-loss`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  }
  return api.student.focusLoss({ sessionId: context.session.id, reason });
}

export default function App() {
  const bridge = api || fallbackApi;
  const [booting, setBooting] = useState(true);
  const [appVersion, setAppVersion] = useState("");
  const [updateState, setUpdateState] = useState({ checking: false, message: "", info: null });
  const [cloudUrl, setCloudUrl] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [fallbackPin, setFallbackPin] = useState("");
  const [snapshot, setSnapshot] = useState({ exams: [], students: [], sessions: [], queueCount: 0, settings: {} });
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");
  const [studentContext, setStudentContext] = useState(null);
  const [examPayload, setExamPayload] = useState(null);
  const [phase, setPhase] = useState("login");
  const [lanServerUrl, setLanServerUrl] = useState(() => localStorage.getItem("schooldomLanServerUrl") || "");

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
        setAppVersion(boot.appVersion || "");
        setCloudUrl(boot.cloudUrl || "");
        setSnapshot(boot.snapshot || {});
      } catch (bootError) {
        setError(bootError.message || "Could not start SchoolDom Student CBT.");
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

  const checkForUpdates = useCallback(async () => {
    setUpdateState({ checking: true, message: "Checking for app updates...", info: null });
    try {
      const info = await bridge.updates.check({ cloudUrl });
      setUpdateState({
        checking: false,
        info,
        message: info.updateAvailable
          ? `Version ${info.latestVersion} is ready to download.`
          : info.error
            ? info.error
            : "This CBT app is already up to date.",
      });
    } catch (updateError) {
      setUpdateState({ checking: false, info: null, message: updateError.message || "Could not check for updates." });
    }
  }, [bridge, cloudUrl]);

  const downloadUpdate = useCallback(async () => {
    const info = updateState.info || {};
    setUpdateState((current) => ({ ...current, checking: true, message: "Opening the latest CBT installer..." }));
    try {
      await bridge.updates.download({ cloudUrl, downloadUrl: info.downloadUrl });
      setUpdateState((current) => ({
        ...current,
        checking: false,
        message: "The latest installer is opening. Close this app before running the installer.",
      }));
    } catch (updateError) {
      setUpdateState((current) => ({
        ...current,
        checking: false,
        message: updateError.message || "Could not open the update installer.",
      }));
    }
  }, [bridge, cloudUrl, updateState.info]);

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

  async function importLocalExam(payload) {
    setError("");
    setSyncMessage("Opening local question files...");
    try {
      const result = await api.admin.importLocalExam(payload);
      if (result.canceled) {
        setSyncMessage("");
        return;
      }
      setSnapshot(result.snapshot);
      setSyncMessage(`Created "${result.exam.title}" with ${result.imported.questions} question(s) for ${result.imported.students} student(s).`);
    } catch (importError) {
      setError(importError.message || "Could not create local CBT exam.");
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
    const nextLanServerUrl = normalizeLanServerUrl(payload.lanServerUrl);
    if (nextLanServerUrl) {
      localStorage.setItem("schooldomLanServerUrl", nextLanServerUrl);
      setLanServerUrl(nextLanServerUrl);
      const result = await lanRequest(nextLanServerUrl, "/api/login", {
        method: "POST",
        body: JSON.stringify({ studentId: payload.studentId, pin: payload.pin }),
      });
      if (!result.success) {
        setError(result.message || "Login failed.");
        return;
      }
      const examResult = await lanRequest(nextLanServerUrl, `/api/exams/${encodeURIComponent(result.exam.id)}`);
      if (!examResult.success) {
        setError(examResult.message || "Could not open exam.");
        return;
      }
      setStudentContext({ ...result, lanServerUrl: nextLanServerUrl });
      setExamPayload(examResult.exam);
      setPhase("instructions");
      return;
    }
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
            <small>Student CBT{appVersion ? ` v${appVersion}` : ""}</small>
          </div>
        </div>
        <nav>
          <button className="active" type="button">Student Exam</button>
        </nav>
        <DesktopUpdateCard
          checking={updateState.checking}
          message={updateState.message}
          info={updateState.info}
          onCheck={checkForUpdates}
          onDownload={downloadUpdate}
        />
      </aside>

      <section className="main-stage">
        {error ? <div className="error-banner">{error}<button onClick={() => setError("")}>Dismiss</button></div> : null}
        <StudentWorkspace
          phase={phase}
          setPhase={setPhase}
          context={studentContext}
          examPayload={examPayload}
          lanServerUrl={lanServerUrl}
          onLanServerUrl={setLanServerUrl}
          onLogin={handleStudentLogin}
          onExit={() => {
            setStudentContext(null);
            setExamPayload(null);
            setPhase("login");
            api?.window?.exitFullscreen?.();
          }}
        />
      </section>
    </main>
  );
}

function SplashScreen() {
  return (
    <div className="splash-screen">
      <div className="splash-mark">SD</div>
      <h1>SchoolDom Student CBT</h1>
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

function DesktopUpdateCard({ checking, message, info, onCheck, onDownload }) {
  return (
    <div className="desktop-update-card">
      <strong>App updates</strong>
      <small>{message || "Check for the latest SchoolDom CBT desktop app."}</small>
      <button type="button" onClick={onCheck} disabled={checking}>
        {checking ? "Checking..." : "Check Update"}
      </button>
      {info?.updateAvailable ? (
        <button type="button" className="primary-button" onClick={onDownload} disabled={checking || !info?.available}>
          Download Update
        </button>
      ) : null}
    </div>
  );
}

function AdminDashboard(props) {
  const { accessToken, cloudUrl, fallbackPin, snapshot, syncMessage, onAccessToken, onCloudUrl, onExportResults, onFallbackPin, onImportLocalExam, onImportPackage, onPushResults, onRefresh, onSync } = props;
  const [lanName, setLanName] = useState(snapshot.settings?.lanName || "School CBT Room");
  const [lanInstructions, setLanInstructions] = useState(snapshot.settings?.lanInstructions || "Admin will set Wi-Fi, hotspot, or lab network access manually.");
  const [localExam, setLocalExam] = useState({
    title: "Local CBT Exam",
    subject: "",
    durationMinutes: "60",
    pin: "",
    instructions: "Answer all questions. This exam was prepared locally by the school.",
    studentsText: "",
  });
  const submitted = snapshot.sessions?.filter((item) => item.status === "submitted").length || 0;
  const inProgress = snapshot.sessions?.filter((item) => item.status === "in_progress").length || 0;
  const updateLocalExam = (key, value) => setLocalExam((current) => ({ ...current, [key]: value }));
  const createLocalExam = (mode) => {
    if (!localExam.pin.trim()) return;
    onImportLocalExam({ ...localExam, mode });
  };
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

      <section className="panel local-exam-panel">
        <div className="panel-head">
          <h2>Create Local Exam</h2>
          <span>Files or folder</span>
        </div>
        <div className="form-grid">
          <label>
            Exam Title
            <input value={localExam.title} onChange={(event) => updateLocalExam("title", event.target.value)} placeholder="Example: JSS2 Mathematics Test" />
          </label>
          <label>
            Subject
            <input value={localExam.subject} onChange={(event) => updateLocalExam("subject", event.target.value)} placeholder="Example: Mathematics" />
          </label>
          <label>
            Duration Minutes
            <input value={localExam.durationMinutes} onChange={(event) => updateLocalExam("durationMinutes", event.target.value)} type="number" min="1" />
          </label>
          <label>
            Exam PIN
            <input value={localExam.pin} onChange={(event) => updateLocalExam("pin", event.target.value)} type="password" placeholder="Students enter this PIN" />
          </label>
        </div>
        <label>
          Local Students
          <textarea value={localExam.studentsText} onChange={(event) => updateLocalExam("studentsText", event.target.value)} rows="4" placeholder={"One student per line: StudentID, Full Name, Class\nSD001, Ada Okafor, JSS2"} />
        </label>
        <label>
          Instructions
          <textarea value={localExam.instructions} onChange={(event) => updateLocalExam("instructions", event.target.value)} rows="3" />
        </label>
        <div className="button-row">
          <button className="primary-button" disabled={!localExam.pin.trim()} onClick={() => createLocalExam("files")}>Add Question Files</button>
          <button disabled={!localExam.pin.trim()} onClick={() => createLocalExam("folder")}>Add Question Folder</button>
        </div>
        {!localExam.pin.trim() ? <p className="muted compact-note">Enter an exam PIN before selecting files.</p> : null}
        <p className="muted compact-note">Supports CBT JSON, CSV, TXT, MD, DOCX, plus folders. Other files are stored as local exam material.</p>
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

function StudentWorkspace({ phase, setPhase, context, examPayload, lanServerUrl, onLanServerUrl, onLogin, onExit }) {
  if (phase === "login") return <StudentLogin lanServerUrl={lanServerUrl} onLanServerUrl={onLanServerUrl} onLogin={onLogin} />;
  if (phase === "instructions") return <Instructions context={context} onStart={() => setPhase("exam")} />;
  if (phase === "summary") return <Summary context={context} onExit={onExit} />;
  return <ExamInterface context={context} examPayload={examPayload} onSubmitted={() => setPhase("summary")} />;
}

function StudentLogin({ lanServerUrl, onLanServerUrl, onLogin }) {
  const [studentId, setStudentId] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [serverUrl, setServerUrl] = useState(lanServerUrl || "");
  const [discovering, setDiscovering] = useState(false);
  const [rooms, setRooms] = useState([]);
  const [discoveryMessage, setDiscoveryMessage] = useState("");

  const chooseRoom = (room) => {
    setServerUrl(room.url);
    onLanServerUrl(room.url);
    setDiscoveryMessage(`Connected to ${room.name || "SchoolDom Admin"} at ${room.url}`);
  };

  const findRooms = async () => {
    setDiscovering(true);
    setDiscoveryMessage("Searching this Wi-Fi for SchoolDom Admin...");
    try {
      const found = await (api?.discoverRooms ? api.discoverRooms() : fallbackApi.discoverRooms());
      setRooms(found || []);
      setDiscoveryMessage(found?.length ? "Select the admin room below." : "No admin room found. Check that Admin app is open and allowed through Windows Firewall.");
    } catch (error) {
      setDiscoveryMessage(error.message || "Could not search this network.");
    } finally {
      setDiscovering(false);
    }
  };

  return (
    <div className="login-screen">
      <section className="login-card">
        <p>Secure student login</p>
        <h1>Start CBT Exam</h1>
        <button type="button" onClick={findRooms} disabled={discovering}>
          {discovering ? "Searching..." : "Find Admin Room"}
        </button>
        {discoveryMessage ? <small className="discovery-message">{discoveryMessage}</small> : null}
        {rooms.length ? (
          <div className="room-list">
            {rooms.map((room) => (
              <button type="button" key={room.url} onClick={() => chooseRoom(room)}>
                <strong>{room.name || "SchoolDom Admin"}</strong>
                <span>{room.url}</span>
                <small>{room.exams || 0} exam(s), {room.students || 0} student(s)</small>
              </button>
            ))}
          </div>
        ) : null}
        <label>Admin Server Address<input value={serverUrl} onChange={(event) => {
          setServerUrl(event.target.value);
          onLanServerUrl(event.target.value);
        }} placeholder="Example: http://192.168.1.23:4785" /></label>
        <label>Student ID<input value={studentId} onChange={(event) => setStudentId(event.target.value)} autoFocus /></label>
        <label>Exam PIN<input value={pin} onChange={(event) => setPin(event.target.value)} type="password" /></label>
        <button className="primary-button" disabled={busy} onClick={async () => {
          setBusy(true);
          try {
            await onLogin({ studentId, pin, lanServerUrl: serverUrl });
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
    await submitStudentExam(context, answersRef.current, cause);
    await api?.window?.exitFullscreen?.();
    onSubmitted();
  }, [context, onSubmitted]);

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
      saveStudentAnswers(context, answersRef.current).catch(() => null);
    }, 1000);
    return () => clearInterval(saver);
  }, [context]);

  useEffect(() => {
    const onBlur = () => logStudentFocusLoss(context, "window_blur").catch(() => null);
    const block = (event) => {
      if ((event.ctrlKey || event.metaKey) && ["r", "l", "n", "t", "w"].includes(event.key.toLowerCase())) {
        event.preventDefault();
        logStudentFocusLoss(context, `blocked_shortcut_${event.key}`).catch(() => null);
      }
    };
    window.addEventListener("blur", onBlur);
    window.addEventListener("keydown", block);
    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("keydown", block);
    };
  }, [context]);

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
        <div className="question-workspace">
          <div className="question-card">
            <p>Question {question.number} - {question.type?.replaceAll("_", " ")}</p>
            <h1>{question.text}</h1>
            <AnswerControl question={question} value={answers[question.id] || ""} onChange={(value) => setAnswers((currentAnswers) => ({ ...currentAnswers, [question.id]: value }))} />
          </div>
          <Calculator />
        </div>
        <div className="exam-actions">
          <button disabled={current === 0} onClick={() => setCurrent((value) => Math.max(0, value - 1))}>Previous</button>
          <button className="primary-button" disabled={current >= questions.length - 1} onClick={() => setCurrent((value) => Math.min(questions.length - 1, value + 1))}>Next</button>
        </div>
      </section>
    </div>
  );
}

function Calculator() {
  const [display, setDisplay] = useState("0");
  const [error, setError] = useState("");

  const append = (value) => {
    setError("");
    setDisplay((current) => {
      if (current === "Error") return value;
      if (current === "0" && /[0-9.]/.test(value)) return value;
      return `${current}${value}`;
    });
  };

  const clear = () => {
    setDisplay("0");
    setError("");
  };

  const backspace = () => {
    setError("");
    setDisplay((current) => {
      if (current.length <= 1 || current === "Error") return "0";
      return current.slice(0, -1);
    });
  };

  const calculate = () => {
    try {
      if (!/^[0-9+\-*/().%\s]+$/.test(display)) {
        throw new Error("Invalid input");
      }
      const result = Function(`"use strict"; return (${display})`)();
      if (!Number.isFinite(result)) {
        throw new Error("Invalid result");
      }
      setDisplay(String(Number(result.toFixed(8))));
      setError("");
    } catch {
      setDisplay("Error");
      setError("Check the calculation");
    }
  };

  const buttons = [
    { label: "C", action: clear, kind: "utility" },
    { label: "(", value: "(", kind: "utility" },
    { label: ")", value: ")", kind: "utility" },
    { label: "Back", action: backspace, kind: "utility" },
    { label: "7", value: "7" },
    { label: "8", value: "8" },
    { label: "9", value: "9" },
    { label: "/", value: "/", kind: "operator" },
    { label: "4", value: "4" },
    { label: "5", value: "5" },
    { label: "6", value: "6" },
    { label: "*", value: "*", kind: "operator" },
    { label: "1", value: "1" },
    { label: "2", value: "2" },
    { label: "3", value: "3" },
    { label: "-", value: "-", kind: "operator" },
    { label: "0", value: "0" },
    { label: ".", value: "." },
    { label: "%", value: "%", kind: "operator" },
    { label: "+", value: "+", kind: "operator" },
    { label: "=", action: calculate, kind: "equals wide" }
  ];

  return (
    <aside className="exam-calculator" aria-label="Calculator">
      <div className="calculator-head">
        <strong>Calculator</strong>
        <small>Basic</small>
      </div>
      <div className="calculator-display" title={display}>{display}</div>
      {error ? <small className="calculator-error">{error}</small> : <small className="calculator-hint">Use for simple arithmetic.</small>}
      <div className="calculator-grid">
        {buttons.map((button) => (
          <button
            key={button.label}
            className={button.kind || ""}
            onClick={() => (button.action ? button.action() : append(button.value))}
            type="button"
          >
            {button.label}
          </button>
        ))}
      </div>
    </aside>
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
