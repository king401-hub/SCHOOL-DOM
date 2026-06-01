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
      const settings = await bridge.settings();
      if (!active) return;
      setServerUrl(settings.serverUrl || "");
      setSchoolCode(settings.schoolCode || "");
      await loadDashboard({ serverUrl: settings.serverUrl || "", schoolCode: settings.schoolCode || "" });
    })();
    const interval = window.setInterval(() => loadDashboard().catch(() => null), 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
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
        <span>Server <b>{data?.server?.online && !error ? "On" : "Off"}</b></span>
      </header>

      <section className="dashboard-grid">
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
