import { useCallback, useEffect, useState } from "react";
import { requestJson, resolveDocumentTheme, documentStylesForExport, resolveSchoolBrand } from "./AppShared";
import { API_BASE_URL } from "./appConstants";
import { AttendanceStatusPill, formatDateTime } from "./components/Attendance";

const PERSON_TYPES = [
  { id: "student", label: "Students" },
  { id: "teaching", label: "Teaching Staff" },
  { id: "non_teaching", label: "Non-Teaching Staff" },
];

const STUDENT_STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "excused", label: "Excused" },
];

const STAFF_STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "half_day", label: "Half day" },
  { value: "excused", label: "Excused" },
];

const STUDENT_COLUMNS = [
  { key: "date", label: "Date" },
  { key: "student_name", label: "Student Name" },
  { key: "student_id", label: "Student ID" },
  { key: "class_name", label: "Class" },
  { key: "status", label: "Status" },
  { key: "time_marked", label: "Time Marked" },
  { key: "marked_by", label: "Marked By" },
  { key: "method", label: "Method" },
  { key: "remarks", label: "Remarks" },
];

const STAFF_COLUMNS = [
  { key: "date", label: "Date" },
  { key: "staff_name", label: "Staff Name" },
  { key: "staff_code", label: "Staff ID" },
  { key: "staff_type", label: "Category" },
  { key: "status", label: "Status" },
  { key: "time_marked", label: "Time Marked" },
  { key: "marked_by", label: "Marked By" },
  { key: "method", label: "Method" },
  { key: "remarks", label: "Remarks" },
];

function formatLogDate(value) {
  if (!value) return "-";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

async function downloadAuthedFile(session, endpoint, filename) {
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
}

export function AttendanceLogsPanel({ session }) {
  const [personType, setPersonType] = useState("student");
  const isStaffMode = personType !== "student";

  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState("");
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState("");
  const [staffList, setStaffList] = useState([]);
  const [staffId, setStaffId] = useState("");

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sort, setSort] = useState("-date");
  const [page, setPage] = useState(1);
  const limit = 20;

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [exportBusy, setExportBusy] = useState(false);

  const activePersonId = isStaffMode ? staffId : studentId;
  const selectedStudent = students.find((item) => String(item.id) === String(studentId));
  const selectedStaff = staffList.find((item) => String(item.id) === String(staffId));
  const selectedClass = classes.find((item) => String(item.id) === String(classId));

  // Reset the person selector whenever the mode toggles, and reload the
  // class list once (only relevant to student mode).
  useEffect(() => {
    setClassId("");
    setStudentId("");
    setStaffId("");
    setResult(null);
  }, [personType]);

  useEffect(() => {
    if (personType !== "student" || !session) return undefined;
    let cancelled = false;
    requestJson(session, "GET", "/api/app/attendance/logs/classes/")
      .then((res) => {
        if (!cancelled) setClasses(res.classes || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [session, personType]);

  useEffect(() => {
    setStudentId("");
    if (personType !== "student" || !classId || !session) {
      setStudents([]);
      return undefined;
    }
    let cancelled = false;
    requestJson(session, "GET", `/api/app/attendance/logs/classes/${classId}/students/`)
      .then((res) => {
        if (!cancelled) setStudents(res.students || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [session, personType, classId]);

  useEffect(() => {
    setStaffId("");
    if (!isStaffMode || !session) {
      setStaffList([]);
      return undefined;
    }
    let cancelled = false;
    requestJson(session, "GET", `/api/hr/attendance-logs/staff/?staff_type=${personType}`)
      .then((res) => {
        if (!cancelled) setStaffList(res.staff || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [session, personType, isStaffMode]);

  useEffect(() => {
    setPage(1);
  }, [activePersonId, startDate, endDate, statusFilter, sort]);

  const buildParams = useCallback(
    (forExport) => {
      const params = new URLSearchParams();
      if (isStaffMode) {
        params.set("staff_id", activePersonId);
      } else {
        params.set("student_id", activePersonId);
      }
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      if (statusFilter) params.set("status", statusFilter);
      if (search) params.set("search", search);
      params.set("sort", sort);
      if (!forExport) {
        params.set("page", String(page));
        params.set("limit", String(limit));
      }
      return params;
    },
    [isStaffMode, activePersonId, startDate, endDate, statusFilter, search, sort, page]
  );

  const fetchLogs = useCallback(async () => {
    if (!activePersonId || !session) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const params = buildParams(false);
      const endpoint = isStaffMode
        ? `/api/hr/attendance-logs/records/?${params.toString()}`
        : `/api/app/attendance/logs/students/?${params.toString()}`;
      const res = await requestJson(session, "GET", endpoint);
      setResult(res);
    } catch (fetchError) {
      setError(fetchError.message || "Could not load attendance logs.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [session, isStaffMode, activePersonId, buildParams]);

  useEffect(() => {
    const timer = window.setTimeout(fetchLogs, 300);
    return () => window.clearTimeout(timer);
  }, [fetchLogs]);

  const columns = isStaffMode ? STAFF_COLUMNS : STUDENT_COLUMNS;
  const statusOptions = isStaffMode ? STAFF_STATUS_OPTIONS : STUDENT_STATUS_OPTIONS;
  const rows = result?.results || [];
  const summary = result?.summary || null;
  const totalPages = result ? Math.max(1, Math.ceil((result.count || 0) / limit)) : 1;

  const personLabel = isStaffMode ? selectedStaff?.name : selectedStudent?.name;

  const handleSort = (columnKey) => {
    if (columnKey !== "date" && columnKey !== "status") return;
    setSort((current) => (current === columnKey ? `-${columnKey}` : current === `-${columnKey}` ? columnKey : `-${columnKey}`));
  };

  const handleExport = async () => {
    if (!activePersonId) return;
    setExportBusy(true);
    setError("");
    try {
      const params = buildParams(true);
      const endpoint = isStaffMode
        ? `/api/hr/attendance-logs/records/export/?${params.toString()}`
        : `/api/app/attendance/logs/students/export/?${params.toString()}`;
      const filename = `${(personLabel || "attendance").toLowerCase().replace(/[^a-z0-9]+/g, "-")}-attendance-logs.csv`;
      await downloadAuthedFile(session, endpoint, filename);
    } catch (exportError) {
      setError(exportError.message || "Could not export attendance logs.");
    } finally {
      setExportBusy(false);
    }
  };

  const handlePrint = async () => {
    if (!activePersonId) return;
    setError("");
    try {
      const params = buildParams(true);
      const endpoint = isStaffMode
        ? `/api/hr/attendance-logs/records/?${params.toString()}&limit=2000&page=1`
        : `/api/app/attendance/logs/students/?${params.toString()}&limit=2000&page=1`;
      const full = await requestJson(session, "GET", endpoint);
      const theme = resolveDocumentTheme(session?.school);
      const brand = resolveSchoolBrand(session?.school);
      const printRows = full.results || [];
      const tableHead = columns.map((col) => `<th>${col.label}</th>`).join("");
      const tableBody = printRows.length
        ? printRows
            .map(
              (row) =>
                `<tr>${columns
                  .map((col) => {
                    let value = row[col.key];
                    if (col.key === "date") value = formatLogDate(value);
                    else if (col.key === "time_marked") value = formatDateTime(value);
                    return `<td>${value === null || value === undefined || value === "" ? "-" : String(value)}</td>`;
                  })
                  .join("")}</tr>`
            )
            .join("")
        : `<tr><td colspan="${columns.length}">No attendance records found for this selection.</td></tr>`;
      const summaryLine = full.summary
        ? `Total school days ${full.summary.total_school_days} &bull; Present ${full.summary.days_present} &bull; Absent ${full.summary.days_absent} &bull; Late ${full.summary.days_late} &bull; Excused ${full.summary.days_excused} &bull; Attendance ${full.summary.attendance_percentage}%`
        : "";
      const printWindow = window.open("", "_blank", "width=1200,height=800");
      if (!printWindow) {
        setError("Allow popups to print this document.");
        return;
      }
      printWindow.document.write(`
        <!doctype html>
        <html>
          <head>
            <title>Attendance Logs - ${personLabel || ""}</title>
            <style>${documentStylesForExport(theme)}
              .sheet{width:max-content;min-width:100%;padding:24px;font-family:var(--doc-font-family),Arial,sans-serif}.paper{background:#fff;border:1px solid #cbd5e1;padding:24px;box-shadow:0 18px 45px rgba(15,23,42,.12)}.school-name{margin:0 0 4px;font-size:18px;font-weight:900;text-transform:uppercase;color:var(--doc-secondary)}.sheet h1{margin:0 0 6px;font-size:22px;text-transform:uppercase;color:var(--doc-secondary)}.sheet p{margin:0 0 10px;color:#475569}.sheet table{border-collapse:collapse;width:100%;font-size:12px}.sheet th,.sheet td{border:var(--doc-border-width) var(--doc-border-style) #94a3b8;padding:6px 8px;text-align:left;white-space:nowrap}.sheet th{background:#e8f2fb;text-transform:uppercase;font-size:11px}.actions{margin:0 0 14px;display:flex;gap:10px}.actions button{border:0;border-radius:8px;background:var(--doc-accent);color:#fff;padding:10px 14px;font-weight:800;cursor:pointer}@media print{body{background:#fff}.actions{display:none}.sheet{padding:0}.paper{box-shadow:none;border:0}}
            </style>
          </head>
          <body>
            <main class="sheet">
              <div class="paper">
                <div class="actions"><button onclick="window.print()">Print / Save PDF</button></div>
                <div class="school-name">${brand.name || "School"}</div>
                <h1>Attendance Logs - ${personLabel || ""}</h1>
                <p>${startDate || "Start of history"} to ${endDate || "today"} &bull; ${summaryLine}</p>
                <table><thead><tr>${tableHead}</tr></thead><tbody>${tableBody}</tbody></table>
              </div>
            </main>
          </body>
        </html>
      `);
      printWindow.document.close();
    } catch (printError) {
      setError(printError.message || "Could not prepare the printable attendance log.");
    }
  };

  return (
    <section className="attendance-logs-panel">
      <article className="app-panel">
        <div className="panel-head">
          <h3>Attendance Logs</h3>
          <small>Complete historical attendance from the date each person first started, unless a date range narrows it.</small>
        </div>

        <div className="segmented-control" style={{ justifyContent: "flex-start", marginBottom: "0.75rem" }}>
          {PERSON_TYPES.map((type) => (
            <button key={type.id} type="button" className={personType === type.id ? "active" : ""} onClick={() => setPersonType(type.id)}>
              {type.label}
            </button>
          ))}
        </div>

        <div className="panel-form-grid">
          {personType === "student" ? (
            <>
              <label className="panel-field">
                Class
                <select value={classId} onChange={(event) => setClassId(event.target.value)}>
                  <option value="">Select class</option>
                  {classes.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="panel-field">
                Student
                <select value={studentId} onChange={(event) => setStudentId(event.target.value)} disabled={!classId}>
                  <option value="">Select student</option>
                  {students.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.student_id})
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <label className="panel-field">
              Staff
              <select value={staffId} onChange={(event) => setStaffId(event.target.value)}>
                <option value="">Select staff</option>
                {staffList.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.staff_code})
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="panel-field">
            Start Date
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="panel-field">
            End Date
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </div>

        {activePersonId ? (
          <>
            <div className="panel-form-grid" style={{ marginTop: "0.75rem" }}>
              <label className="panel-field">
                Search
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search marked by, remarks..." />
              </label>
              <label className="panel-field">
                Status
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="panel-field" style={{ alignSelf: "end", display: "flex", gap: "0.5rem" }}>
                <button type="button" className="btn-secondary" onClick={handlePrint} disabled={!rows.length}>
                  Print
                </button>
                <button type="button" className="btn-secondary" onClick={handleExport} disabled={exportBusy || !rows.length}>
                  {exportBusy ? "Exporting..." : "Export to Excel"}
                </button>
              </div>
            </div>

            {summary ? (
              <div className="heat-metric-grid" style={{ marginTop: "1rem" }}>
                <div className="heat-metric-card">
                  <span>Total School Days</span>
                  <strong>{summary.total_school_days}</strong>
                </div>
                <div className="heat-metric-card">
                  <span>Days Present</span>
                  <strong>{summary.days_present}</strong>
                </div>
                <div className="heat-metric-card">
                  <span>Days Absent</span>
                  <strong>{summary.days_absent}</strong>
                </div>
                <div className="heat-metric-card">
                  <span>Days Late</span>
                  <strong>{summary.days_late}</strong>
                </div>
                <div className="heat-metric-card">
                  <span>Excused Days</span>
                  <strong>{summary.days_excused}</strong>
                </div>
                <div className="heat-metric-card">
                  <span>Attendance %</span>
                  <strong>{summary.attendance_percentage}%</strong>
                </div>
              </div>
            ) : null}

            {error ? <p className="form-feedback error">{error}</p> : null}

            <div style={{ overflowX: "auto", marginTop: "1rem" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        style={{ cursor: col.key === "date" || col.key === "status" ? "pointer" : "default" }}
                      >
                        {col.label}
                        {sort === col.key ? " ↑" : sort === `-${col.key}` ? " ↓" : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={columns.length}>Loading...</td>
                    </tr>
                  ) : rows.length ? (
                    rows.map((row, index) => (
                      <tr key={`${row.date}-${index}`}>
                        {columns.map((col) => (
                          <td key={col.key}>
                            {col.key === "status" ? (
                              <AttendanceStatusPill status={row.status} />
                            ) : col.key === "date" ? (
                              formatLogDate(row.date)
                            ) : col.key === "time_marked" ? (
                              formatDateTime(row.time_marked)
                            ) : (
                              row[col.key] || "-"
                            )}
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={columns.length}>No attendance records found for this selection.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {result ? (
              <div className="panel-form-actions" style={{ justifyContent: "space-between", marginTop: "0.75rem" }}>
                <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Prev
                </button>
                <span>
                  Page {page} of {totalPages} &bull; {result.count} record{result.count === 1 ? "" : "s"}
                </span>
                <button type="button" className="btn-secondary" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                  Next
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <p className="panel-empty">
            {personType === "student"
              ? classId
                ? "Select a student to view their attendance history."
                : "Select a class, then a student, to view their attendance history."
              : "Select a staff member to view their attendance history."}
          </p>
        )}
      </article>
    </section>
  );
}
