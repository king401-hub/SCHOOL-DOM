import { useCallback, useEffect, useState } from "react";
import { MetricCard, ScreenState, requestJson, resolveSchoolBrand } from "./AppShared";

const NAV_ITEMS = [
  { key: "overview", label: "Overview" },
  { key: "add-school", label: "Add School" },
  { key: "add-admin", label: "Add Admin" },
  { key: "finance", label: "Finance" },
];

function formatMoney(value) {
  const amount = Number(value || 0);
  return `₦${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function downloadFinanceCsv(schools, totals) {
  const csvEscape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const rows = [
    ["Branch", "Students", "Staff", "Collected", "Outstanding", "Collection Rate", "Status"],
    ...schools.map((row) => [
      row.name,
      row.students,
      row.staff,
      row.collected,
      row.outstanding,
      `${Number(row.rate).toFixed(1)}%`,
      row.status,
    ]),
    ["Total", totals.students, totals.staff, totals.collected, totals.outstanding, `${Number(totals.rate).toFixed(1)}%`, totals.status],
  ];
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "school-superadmin-finance.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function SchoolsTable({ schools }) {
  if (!schools.length) {
    return <p className="panel-empty">No schools in your group yet.</p>;
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>School</th>
            <th>Code</th>
            <th>Students</th>
            <th>Staff</th>
            <th>Collected</th>
            <th>Outstanding</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {schools.map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>{row.school_code}</td>
              <td>{row.students}</td>
              <td>{row.staff}</td>
              <td>{formatMoney(row.collected)}</td>
              <td>{formatMoney(row.outstanding)}</td>
              <td>
                <span className={`finance-status status-${String(row.status || "").toLowerCase().replace(/\s+/g, "-")}`}>
                  {row.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OverviewScreen({ session, overview, loading, error, onRetry, onGoToAddSchool }) {
  if (loading || error) {
    return <ScreenState loading={loading} error={error} onRetry={onRetry} />;
  }
  const schools = overview?.schools || [];
  const totals = overview?.totals || {};
  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>{overview?.school_group?.name || "Your School Group"}</h2>
        <p>{schools.length} school{schools.length === 1 ? "" : "s"} in your group.</p>
      </div>
      <div className="metric-grid">
        <MetricCard label="Schools" value={schools.length} icon="home" tone="blue" />
        <MetricCard label="Students" value={totals.students ?? 0} icon="overview" tone="green" />
        <MetricCard label="Staff" value={totals.staff ?? 0} icon="id" tone="purple" />
        <MetricCard label="Collected" value={formatMoney(totals.collected)} icon="money" tone="green" />
        <MetricCard label="Outstanding" value={formatMoney(totals.outstanding)} icon="money" tone="amber" />
      </div>
      <article className="app-panel">
        <div className="panel-head">
          <h3>Your Schools</h3>
        </div>
        {schools.length ? (
          <SchoolsTable schools={schools} />
        ) : (
          <div className="panel-empty" style={{ textAlign: "center", padding: "2rem 1rem" }}>
            <p>You haven't added a school yet.</p>
            <button type="button" onClick={onGoToAddSchool}>Add your first school</button>
          </div>
        )}
      </article>
    </section>
  );
}

function AddSchoolScreen({ session, onCreated }) {
  const [form, setForm] = useState({ name: "", address: "", email: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await requestJson(session, "POST", "/api/app/proprietor/schools/", form);
      setMessage(result?.message || "School added.");
      setForm({ name: "", address: "", email: "" });
      onCreated?.();
    } catch (err) {
      setError(err.message || "Could not add school.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Add School</h2>
        <p>Create a new school under your group. You can invite an admin for it next.</p>
      </div>
      <article className="app-panel">
        {message ? <p className="form-feedback success">{message}</p> : null}
        {error ? <p className="form-feedback error">{error}</p> : null}
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field full">
              School name
              <input
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="e.g. Xcel Academy - Lekki Campus"
                required
              />
            </label>
            <label className="panel-field">
              Address (optional)
              <input
                value={form.address}
                onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
                placeholder="Street, city"
              />
            </label>
            <label className="panel-field">
              School email (optional)
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="office@school.edu"
              />
            </label>
          </div>
          <div className="panel-form-actions">
            <button type="submit" disabled={busy || !form.name.trim()}>
              {busy ? "Adding..." : "Add school"}
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}

function AddAdminScreen({ session, schools }) {
  const [form, setForm] = useState({ school_id: "", name: "", email: "", role: "school_admin" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!form.school_id && schools.length) {
      setForm((prev) => ({ ...prev, school_id: String(schools[0].id) }));
    }
  }, [schools, form.school_id]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.school_id) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await requestJson(session, "POST", `/api/app/proprietor/schools/${form.school_id}/admins/`, {
        name: form.name,
        email: form.email,
        role: form.role,
      });
      setMessage(result?.message || "Admin added.");
      setForm((prev) => ({ ...prev, name: "", email: "" }));
    } catch (err) {
      setError(err.message || "Could not add admin.");
    } finally {
      setBusy(false);
    }
  };

  if (!schools.length) {
    return (
      <section className="screen-grid">
        <div className="screen-hero">
          <h2>Add Admin</h2>
          <p>Add a school to your group first before inviting an admin.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Add Admin</h2>
        <p>Invite a School Admin, Principal, or Accountant to run one of your schools. They'll get an email with their login details.</p>
      </div>
      <article className="app-panel">
        {message ? <p className="form-feedback success">{message}</p> : null}
        {error ? <p className="form-feedback error">{error}</p> : null}
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              School
              <select
                value={form.school_id}
                onChange={(event) => setForm((prev) => ({ ...prev, school_id: event.target.value }))}
              >
                {schools.map((school) => (
                  <option key={school.id} value={school.id}>{school.name}</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Role
              <select
                value={form.role}
                onChange={(event) => setForm((prev) => ({ ...prev, role: event.target.value }))}
              >
                <option value="school_admin">School Admin</option>
                <option value="principal">Principal</option>
                <option value="accountant">Accountant</option>
              </select>
            </label>
            <label className="panel-field">
              Full name
              <input
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Jane Doe"
                required
              />
            </label>
            <label className="panel-field">
              Email
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="jane@school.edu"
                required
              />
            </label>
          </div>
          <div className="panel-form-actions">
            <button type="submit" disabled={busy || !form.name.trim() || !form.email.trim()}>
              {busy ? "Adding..." : "Add admin"}
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}

function FinanceScreen({ session, finance, loading, error, onRetry }) {
  if (loading || error) {
    return <ScreenState loading={loading} error={error} onRetry={onRetry} />;
  }
  const schools = finance?.schools || [];
  const totals = finance?.totals || {};
  const defaulters = finance?.top_defaulters || [];
  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>Finance — All Schools</h2>
        <p>Collected vs. outstanding fees rolled up across your entire group.</p>
      </div>
      <div className="metric-grid">
        <MetricCard label="Collected" value={formatMoney(totals.collected)} icon="money" tone="green" />
        <MetricCard label="Outstanding" value={formatMoney(totals.outstanding)} icon="money" tone="amber" />
        <MetricCard label="Collection rate" value={`${Number(totals.rate || 0).toFixed(1)}%`} icon="overview" tone="blue" />
      </div>
      <article className="app-panel">
        <div className="panel-head">
          <h3>By School</h3>
          <button type="button" onClick={() => downloadFinanceCsv(schools, totals)} disabled={!schools.length}>
            Export CSV
          </button>
        </div>
        <SchoolsTable schools={schools} />
      </article>
      {defaulters.length ? (
        <article className="app-panel">
          <div className="panel-head">
            <h3>Top Defaulters</h3>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>Student</th><th>School</th><th>Amount</th><th>Status</th></tr>
              </thead>
              <tbody>
                {defaulters.map((row, index) => (
                  <tr key={index}>
                    <td>{row.student}</td>
                    <td>{row.school}</td>
                    <td>{formatMoney(row.amount)}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}
    </section>
  );
}

export function ProprietorShell({ session, onSignOut }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");
  const [finance, setFinance] = useState(null);
  const [financeLoading, setFinanceLoading] = useState(false);
  const [financeError, setFinanceError] = useState("");

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/proprietor/overview/");
      setOverview(result);
    } catch (err) {
      setOverviewError(err.message || "Could not load your school group.");
    } finally {
      setOverviewLoading(false);
    }
  }, [session]);

  const loadFinance = useCallback(async () => {
    setFinanceLoading(true);
    setFinanceError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/proprietor/finance/");
      setFinance(result);
    } catch (err) {
      setFinanceError(err.message || "Could not load finance data.");
    } finally {
      setFinanceLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    if (activeTab === "finance" && !finance && !financeLoading) {
      loadFinance();
    }
  }, [activeTab, finance, financeLoading, loadFinance]);

  const schoolBrand = resolveSchoolBrand(overview?.school_group, session?.school_group, session);
  const schools = overview?.schools || [];

  const handleSchoolCreated = () => {
    setActiveTab("overview");
    loadOverview();
  };

  return (
    <main className="signup-page dashboard-page">
      <section className="dashboard-shell">
        <header className="dashboard-header">
          <div>
            <p className="topbar-kicker">{schoolBrand.name}</p>
            <h1>Proprietor Dashboard</h1>
            <p>{session?.user?.full_name || session?.user?.email} - Proprietor/Director</p>
          </div>
          <div className="dashboard-actions">
            <button type="button" onClick={loadOverview} disabled={overviewLoading}>
              {overviewLoading ? "Refreshing..." : "Refresh"}
            </button>
            <button type="button" onClick={onSignOut}>Sign out</button>
          </div>
        </header>

        <nav className="proprietor-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`proprietor-nav-item${activeTab === item.key ? " active" : ""}`}
              onClick={() => setActiveTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {activeTab === "overview" ? (
          <OverviewScreen
            session={session}
            overview={overview}
            loading={overviewLoading}
            error={overviewError}
            onRetry={loadOverview}
            onGoToAddSchool={() => setActiveTab("add-school")}
          />
        ) : null}
        {activeTab === "add-school" ? (
          <AddSchoolScreen session={session} onCreated={handleSchoolCreated} />
        ) : null}
        {activeTab === "add-admin" ? (
          <AddAdminScreen session={session} schools={schools} />
        ) : null}
        {activeTab === "finance" ? (
          <FinanceScreen
            session={session}
            finance={finance}
            loading={financeLoading}
            error={financeError}
            onRetry={loadFinance}
          />
        ) : null}
      </section>
    </main>
  );
}
