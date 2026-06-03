import { useCallback, useEffect, useMemo, useState } from "react";

const api = window.schoolDomAdmin;

const fallbackApi = {
  bootstrap: async () => ({
    appName: "SchoolDom Admin",
    appVersion: "0.1.0",
    serverUrl: "https://schooldom.academy",
    school: { name: "SchoolDom", school_code: "schooldom", logo: "", address: "", phone: "", email: "" },
    server: { online: true, host: "schooldom.academy" },
    downloads: { student_cbt: "https://schooldom.academy/app/download/student-cbt/" },
    dashboard: {
      settings: { name: "SchoolDom", ip_address: "schooldom.academy", refresh_interval: "30 sec" },
      content: { total: 0 },
      candidate: { total: 0, class: 0 },
      client: { total: 1 },
      test: { total: 0, licensed: 0, pending: 0, ongoing: 0, submitted: 0, batch_count: 0 },
    },
  }),
  settings: async () => ({ serverUrl: "https://schooldom.academy", schoolCode: "" }),
  saveSettings: async (payload) => payload,
  openCbtInstaller: async () => ({ success: true }),
  lan: {
    snapshot: async () => ({ running: false, urls: [], exams: [], students: [], sessions: [] }),
    start: async () => ({ running: true, urls: ["http://192.168.1.10:4785"], exams: [], students: [], sessions: [] }),
    stop: async () => ({ running: false, urls: [], exams: [], students: [], sessions: [] }),
    publishExam: async () => ({ running: true, urls: ["http://192.168.1.10:4785"], exams: [], students: [], sessions: [] }),
  },
};

function initials(name) {
  return String(name || "SD")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "SD";
}

function hostFromUrl(value) {
  try {
    return new URL(value).host;
  } catch {
    return value || "";
  }
}

export default function App() {
  const bridge = api || fallbackApi;
  const [booting, setBooting] = useState(true);
  const [data, setData] = useState(null);
  const [serverUrl, setServerUrl] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [installing, setInstalling] = useState(false);
  const [lan, setLan] = useState({ running: false, urls: [], exams: [], students: [], sessions: [] });
  const [examForm, setExamForm] = useState({
    title: "Offline CBT Exam",
    subject: "",
    durationMinutes: "60",
    pin: "",
    studentsText: "",
    instructions: "Answer all questions. Submit before the timer ends.",
    questionsText: "Question 1\n\nQuestion 2",
  });

  const loadDashboard = useCallback(
    async (options = {}) => {
      setError("");
      try {
        const payload = await bridge.bootstrap({
          serverUrl: options.serverUrl ?? serverUrl,
          schoolCode: options.schoolCode ?? schoolCode,
        });
        setData(payload);
        setServerUrl(payload.serverUrl || options.serverUrl || serverUrl);
        setSchoolCode(payload.school?.school_code || options.schoolCode || schoolCode);
        setNotice(`Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
      } catch (loadError) {
        setError(loadError.message || "Could not reach the SchoolDom server.");
      } finally {
        setBooting(false);
      }
    },
    [bridge, schoolCode, serverUrl]
  );

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const settings = await bridge.settings();
        if (!active) return;
        setServerUrl(settings.serverUrl || "");
        setSchoolCode(settings.schoolCode || "");
        await loadDashboard({ serverUrl: settings.serverUrl || "", schoolCode: settings.schoolCode || "" });
      } catch (settingsError) {
        if (!active) return;
        setError(settingsError.message || "Could not load app settings.");
        setBooting(false);
      }
    })();
    const interval = window.setInterval(() => loadDashboard().catch(() => null), 30000);
    const lanInterval = window.setInterval(() => bridge.lan?.snapshot?.().then(setLan).catch(() => null), 3000);
    bridge.lan?.start?.().then(setLan).catch(() => null);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.clearInterval(lanInterval);
    };
  }, []);

  const school = data?.school || {};
  const dashboard = data?.dashboard || {};
  const settings = dashboard.settings || {};
  const test = dashboard.test || {};

  const schoolDetails = useMemo(
    () => [
      ["Name", school.name || "SchoolDom"],
      ["Code", school.school_code || "-"],
      ["Phone", school.phone || "-"],
      ["Email", school.email || "-"],
      ["Address", school.address || "-"],
    ],
    [school]
  );

  const saveAndRefresh = async (event) => {
    event.preventDefault();
    setNotice("Saving settings...");
    await bridge.saveSettings({ serverUrl, schoolCode });
    await loadDashboard({ serverUrl, schoolCode });
  };

  const installCbt = async () => {
    setInstalling(true);
    setNotice("Downloading the CBT app installer...");
    try {
      await bridge.openCbtInstaller({ serverUrl: data?.serverUrl || serverUrl, downloadUrl: data?.downloads?.student_cbt });
      setNotice("The real CBT installer is opening. Use it on student computers.");
    } catch (installError) {
      setError(installError.message || "Could not open the CBT installer.");
    } finally {
      setInstalling(false);
    }
  };

  const updateExamForm = (key, value) => setExamForm((current) => ({ ...current, [key]: value }));

  const publishLanExam = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("Publishing exam to the local network...");
    try {
      const nextLan = await bridge.lan.publishExam(examForm);
      setLan(nextLan);
      setNotice("Exam published. Students can connect using the LAN address.");
    } catch (publishError) {
      setError(publishError.message || "Could not publish the offline exam.");
    }
  };

  const startLan = async () => {
    setLan(await bridge.lan.start());
    setNotice("Offline exam room is online on this router.");
  };

  const stopLan = async () => {
    setLan(await bridge.lan.stop());
    setNotice("Offline exam room stopped.");
  };

  if (booting) {
    return (
      <main className="splash-screen">
        <div className="brand-mark">SD</div>
        <h1>SchoolDom Admin</h1>
        <p>Loading school dashboard...</p>
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <header className="topbar">
        <strong>Home / Dashboard</strong>
        <span>LAN <b>{lan.running ? "On" : "Off"}</b></span>
      </header>

      <section className="dashboard-grid">
        <article className="tile lan-tile">
          <TileHead icon="content" title="Offline Exam Room" />
          <Field label="Status" value={lan.running ? "Running" : "Stopped"} />
          <Field label="Student Address" value={lan.urls?.[0] || "Start room"} />
          <Field label="Published Exams" value={lan.exams?.length || 0} />
          <Field label="Students" value={lan.students?.length || 0} />
          <Field label="Submissions" value={(lan.sessions || []).filter((session) => session.status === "submitted").length} />
          <div className="button-row">
            <button type="button" onClick={startLan}>Start Room</button>
            <button type="button" onClick={stopLan}>Stop Room</button>
          </div>
        </article>

        <article className="tile publish-tile">
          <TileHead icon="test" title="Publish Offline Exam" />
          <form onSubmit={publishLanExam} className="publish-form">
            <div className="form-grid">
              <label>
                Exam Title
                <input value={examForm.title} onChange={(event) => updateExamForm("title", event.target.value)} />
              </label>
              <label>
                Subject
                <input value={examForm.subject} onChange={(event) => updateExamForm("subject", event.target.value)} />
              </label>
              <label>
                Duration Minutes
                <input type="number" min="1" value={examForm.durationMinutes} onChange={(event) => updateExamForm("durationMinutes", event.target.value)} />
              </label>
              <label>
                Exam PIN
                <input type="password" value={examForm.pin} onChange={(event) => updateExamForm("pin", event.target.value)} />
              </label>
            </div>
            <label>
              Students
              <textarea value={examForm.studentsText} onChange={(event) => updateExamForm("studentsText", event.target.value)} rows="4" placeholder={"One per line: StudentID, Full Name, Class\nSD001, Ada Okafor, JSS2"} />
            </label>
            <label>
              Questions
              <textarea value={examForm.questionsText} onChange={(event) => updateExamForm("questionsText", event.target.value)} rows="7" placeholder={"Separate theory questions with blank lines, or paste JSON questions."} />
            </label>
            <label>
              Instructions
              <textarea value={examForm.instructions} onChange={(event) => updateExamForm("instructions", event.target.value)} rows="3" />
            </label>
            <button type="submit" disabled={!examForm.pin.trim()}>Publish to Router</button>
          </form>
        </article>

        <article className="tile settings-tile">
          <TileHead icon="gear" title="Settings" />
          <form onSubmit={saveAndRefresh} className="settings-form">
            <label>
              Server URL
              <input value={serverUrl} onChange={(event) => setServerUrl(event.target.value)} />
            </label>
            <label>
              School Code
              <input value={schoolCode} onChange={(event) => setSchoolCode(event.target.value)} placeholder="Optional" />
            </label>
            <Field label="Name" value={settings.name || school.name || "SchoolDom"} />
            <Field label="IP Address" value={settings.ip_address || hostFromUrl(serverUrl)} />
            <Field label="Refresh Interval" value={settings.refresh_interval || "30 sec"} />
            <button type="submit">Refresh</button>
          </form>
        </article>

        <article className="tile content-tile">
          <TileHead icon="content" title="Content" />
          <Field label="Total" value={dashboard.content?.total ?? 0} />
        </article>

        <article className="tile candidate-tile">
          <TileHead icon="candidate" title="Candidate" />
          <Field label="Total" value={dashboard.candidate?.total ?? 0} />
          <Field label="Class" value={dashboard.candidate?.class ?? 0} />
        </article>

        <article className="tile test-tile">
          <TileHead icon="test" title="Test" />
          <Field label="Total" value={test.total ?? 0} />
          <Field label="Published" value={test.licensed ?? 0} />
          <Field label="Pending" value={test.pending ?? 0} />
          <Field label="Ongoing" value={test.ongoing ?? 0} />
          <Field label="Submitted" value={test.submitted ?? 0} />
          <Field label="Batch Count" value={test.batch_count ?? 0} />
        </article>

        <article className="tile client-tile">
          <TileHead icon="client" title="Client" />
          <Field label="Total" value={dashboard.client?.total ?? 1} />
          <Field label="Install From" value="Admin App" />
          <button className="install-button" type="button" onClick={installCbt} disabled={installing}>
            {installing ? "Opening..." : "Install CBT App"}
          </button>
        </article>

        <article className="tile school-tile">
          <TileHead icon="school" title="School Details" />
          <div className="school-logo">
            {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{initials(school.name)}</span>}
          </div>
          {schoolDetails.map(([label, value]) => <Field key={label} label={label} value={value} />)}
        </article>

        <article className="tile sessions-tile">
          <TileHead icon="candidate" title="Live Student Sessions" />
          <div className="session-list">
            {(lan.sessions || []).slice(0, 10).map((session) => (
              <div key={session.id}>
                <span>{session.student_id}</span>
                <strong>{session.status}</strong>
              </div>
            ))}
            {!lan.sessions?.length ? <p>No student sessions yet.</p> : null}
          </div>
        </article>
      </section>

      {notice || error ? (
        <div className={`toast ${error ? "error" : ""}`}>
          {error || notice}
          <button type="button" onClick={() => { setError(""); setNotice(""); }}>Dismiss</button>
        </div>
      ) : null}
    </main>
  );
}

function Field({ label, value }) {
  return (
    <div className="field-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TileHead({ icon, title }) {
  return (
    <header className="tile-head">
      <span className={`tile-icon ${icon}`} aria-hidden="true" />
      <h2>{title}</h2>
    </header>
  );
}
