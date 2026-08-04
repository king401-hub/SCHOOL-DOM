import { useCallback, useEffect, useState } from "react";
import { ScreenState, requestJson } from "../../AppShared";
import "./Alumni.css";
import AlumniStudentDetail from "./AlumniStudentDetail";
import { AlumniPill, REASON_COLORS, STATUS_COLORS, Value, formatDay } from "./alumniHelpers";

const SCOPES = [
  { key: "all", label: "All students" },
  { key: "active", label: "Currently enrolled" },
  { key: "archived", label: "Archived only" },
];

export default function AlumniScreen({ data, loading, error, onRetry, session }) {
  const [students, setStudents] = useState([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [selectedKey, setSelectedKey] = useState("");

  const [search, setSearch] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [className, setClassName] = useState("");
  const [scope, setScope] = useState("all");

  const summary = data?.summary || {};
  const academicYears = data?.academic_years || [];
  const classes = data?.classes || [];

  const loadStudents = useCallback(async () => {
    setListLoading(true);
    setListError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (academicYear) params.set("academic_year", academicYear);
      if (className) params.set("class_name", className);
      if (scope) params.set("scope", scope);
      const query = params.toString();
      const result = await requestJson(
        session,
        "GET",
        `/api/alumni/students/${query ? `?${query}` : ""}`,
      );
      setStudents(result.students || []);
    } catch (err) {
      setListError(err.message || "Unable to load the student archive.");
    } finally {
      setListLoading(false);
    }
  }, [session, search, academicYear, className, scope]);

  // Debounced so typing in the search box does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(loadStudents, 250);
    return () => clearTimeout(timer);
  }, [loadStudents]);

  if (selectedKey) {
    return (
      <section className="screen-grid alumni-screen">
        <div className="screen-hero">
          <div>
            <h2>Student Archive</h2>
            <p>Complete permanent history for one student. Read-only.</p>
          </div>
        </div>
        <AlumniStudentDetail
          session={session}
          studentKey={selectedKey}
          onBack={() => setSelectedKey("")}
        />
      </section>
    );
  }

  return (
    <section className="screen-grid alumni-screen">
      <div className="screen-hero">
        <div>
          <h2>Alumni &amp; Student Archive</h2>
          <p>
            Every student the school has ever had, kept permanently. Pick a session and class, or search by
            name or Student ID, then open a student to see their complete read-only history.
          </p>
        </div>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <div className="alumni-stats">
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.active_students ?? 0}</div>
          <div className="stat-label">Currently enrolled</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.archived_students ?? 0}</div>
          <div className="stat-label">Archived records</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.sealed_records ?? 0}</div>
          <div className="stat-label">Permanently sealed</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.total_records ?? 0}</div>
          <div className="stat-label">Students on record</div>
        </div>
      </div>

      <article className="app-panel">
        <div className="alumni-filters">
          <label>
            Academic year
            <select value={academicYear} onChange={(event) => setAcademicYear(event.target.value)}>
              <option value="">All sessions</option>
              {academicYears.map((year) => (
                <option key={year.name} value={year.name}>{year.name}</option>
              ))}
            </select>
          </label>
          <label>
            Class
            <select value={className} onChange={(event) => setClassName(event.target.value)}>
              <option value="">All classes</option>
              {classes.map((item) => (
                <option key={item.name} value={item.name}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            Show
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              {SCOPES.map((item) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </label>
          <label>
            Search
            <input
              type="search"
              value={search}
              placeholder="Student name or Student ID"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>

        {listError ? <p className="form-feedback error">{listError}</p> : null}

        {listLoading ? (
          <p>Loading students...</p>
        ) : students.length === 0 ? (
          <p>No students match these filters.</p>
        ) : (
          <div className="alumni-table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Name</th>
                  <th>Student ID</th>
                  <th>Class</th>
                  <th>Session</th>
                  <th>Admitted</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {students.map((student) => (
                  <tr
                    key={student.key}
                    className="alumni-row-clickable"
                    onClick={() => setSelectedKey(student.key)}
                  >
                    <td>
                      {student.profile_picture ? (
                        <img className="alumni-avatar" src={student.profile_picture} alt={student.name} />
                      ) : (
                        <div className="alumni-avatar" />
                      )}
                    </td>
                    <td>{student.name}</td>
                    <td><Value>{student.student_id}</Value></td>
                    <td><Value>{student.class_name}</Value></td>
                    <td><Value>{student.academic_year}</Value></td>
                    <td>{student.admission_date ? formatDay(student.admission_date) : "-"}</td>
                    <td>
                      <AlumniPill value={student.status} colorMap={STATUS_COLORS} />
                      {student.archive_reason ? (
                        <>
                          {" "}
                          <AlumniPill value={student.archive_reason} colorMap={REASON_COLORS} />
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="alumni-empty">
          Showing {students.length} student{students.length === 1 ? "" : "s"}. Archived records stay here permanently,
          including students who have graduated, transferred, or been removed from the active list.
        </p>
      </article>
    </section>
  );
}
