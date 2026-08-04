import { useCallback, useEffect, useState } from "react";
import { ScreenState, requestJson } from "../../AppShared";
import "./Alumni.css";
import AlumniStudentDetail from "./AlumniStudentDetail";
import { AlumniPill, REASON_COLORS, Value, formatDay } from "./alumniHelpers";

export default function AlumniScreen({ data, loading, error, onRetry, session }) {
  const [students, setStudents] = useState([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [selectedKey, setSelectedKey] = useState("");

  const [search, setSearch] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [className, setClassName] = useState("");
  const [reason, setReason] = useState("");

  const summary = data?.summary || {};
  const academicYears = data?.academic_years || [];
  const classes = data?.classes || [];
  const reasons = data?.archive_reasons || [];

  const loadStudents = useCallback(async () => {
    setListLoading(true);
    setListError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (academicYear) params.set("academic_year", academicYear);
      if (className) params.set("class_name", className);
      if (reason) params.set("reason", reason);
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
  }, [session, search, academicYear, className, reason]);

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
            Every student who has left the school, kept permanently. Students are added here by promoting them
            to Alumni from Classes. Pick a session and class, or search by name or Student ID, then open a
            student to see their complete read-only history.
          </p>
        </div>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <div className="alumni-stats">
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.total_alumni ?? 0}</div>
          <div className="stat-label">Total alumni</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.graduated ?? 0}</div>
          <div className="stat-label">Graduated</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.transferred ?? 0}</div>
          <div className="stat-label">Transferred</div>
        </div>
        <div className="alumni-stat-card">
          <div className="stat-value">{summary.sealed_records ?? 0}</div>
          <div className="stat-label">Permanently sealed</div>
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
            Reason for leaving
            <select value={reason} onChange={(event) => setReason(event.target.value)}>
              <option value="">All reasons</option>
              {reasons.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
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
          <p>Loading alumni...</p>
        ) : students.length === 0 ? (
          <p>
            No alumni match these filters. Students appear here once they are promoted to Alumni from the
            Classes screen, or when they are transferred, withdrawn, or removed from the school.
          </p>
        ) : (
          <div className="alumni-table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Name</th>
                  <th>Student ID</th>
                  <th>Last class</th>
                  <th>Session</th>
                  <th>Admitted</th>
                  <th>Left</th>
                  <th>Reason</th>
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
                    <td>{student.archived_at ? formatDay(student.archived_at) : "-"}</td>
                    <td><AlumniPill value={student.archive_reason} colorMap={REASON_COLORS} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="alumni-empty">
          Showing {students.length} alumnus{students.length === 1 ? "" : "es"}. These records stay here permanently,
          even after a former student is removed from the school entirely.
        </p>
      </article>
    </section>
  );
}
