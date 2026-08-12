import { useState } from "react";
import { formatDate, Spinner } from "../AppShared";

/* Shows exactly what a teacher pushed for a result batch - every row here is
   read straight from the stored StudentSubjectScore records the batch
   review/publish/delete actions already act on (see
   _result_batch_detail_payload on the backend). Nothing here is
   recalculated except the per-student total/percentage/grade, which are
   plain sums of those same stored scores run through the same grading
   source of truth used everywhere else - not an alternate calculation.

   Edit mode reveals the same component breakdown (theory/CBT/assessment/
   assignment/attendance/other) a teacher fills in on their own score-entry
   form, so an admin corrects a submission using the same fields it was
   built from instead of a single flattened "score" number. */

const tidyMarks = (value) => {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/\.?0+$/, "");
};

const COMPONENT_FIELDS = [
  ["theory_score", "Theory"],
  ["cbt_score", "CBT"],
  ["assessment_score", "Assessment"],
  ["assignment_score", "Assignment"],
  ["attendance_score", "Attendance"],
  ["other_score", "Other"],
];

const editValuesForSubject = (subject) => ({
  theory_score: String(subject.components?.theory ?? 0),
  cbt_score: String(subject.components?.cbt ?? 0),
  assessment_score: String(subject.components?.assessment ?? 0),
  assignment_score: String(subject.components?.assignment ?? 0),
  attendance_score: String(subject.components?.attendance ?? 0),
  other_score: String(subject.components?.other ?? 0),
  max_score: String(subject.max_score ?? 100),
  remarks: subject.remark || "",
});

export default function ResultBatchReviewModal({ batch, onClose, onPublish, onEditScore, onDelete, onBatchUpdated, confirmDelete }) {
  const [actionBusy, setActionBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editValues, setEditValues] = useState({});
  const [dirtyIds, setDirtyIds] = useState(() => new Set());
  const [savingAll, setSavingAll] = useState(false);

  if (!batch) return null;

  const runAction = async (key, task) => {
    setActionBusy(key);
    setActionError("");
    try {
      await task();
      onClose();
    } catch (err) {
      setActionError(err.message || "Could not update this result batch.");
    } finally {
      setActionBusy("");
    }
  };

  const handlePublish = () => runAction("publish", () => onPublish(batch.id));
  const handleDelete = async () => {
    const ok = await confirmDelete?.({
      title: "Delete Results Batch",
      message: `Delete "${batch.title}" and all ${batch.score_count || 0} score record(s)?`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    runAction("delete", () => onDelete(batch.id));
  };

  const students = batch.students || [];

  const enterEditMode = () => {
    const values = {};
    students.forEach((student) => {
      student.subjects.forEach((subject) => {
        values[subject.id] = editValuesForSubject(subject);
      });
    });
    setEditValues(values);
    setDirtyIds(new Set());
    setActionError("");
    setEditMode(true);
  };

  const cancelEditMode = () => {
    setEditMode(false);
    setEditValues({});
    setDirtyIds(new Set());
    setActionError("");
  };

  const handleFieldChange = (subjectId, field, value) => {
    setEditValues((prev) => ({ ...prev, [subjectId]: { ...prev[subjectId], [field]: value } }));
    setDirtyIds((prev) => new Set(prev).add(subjectId));
  };

  const previewScore = (subjectId) => {
    const values = editValues[subjectId];
    if (!values) return { score: 0, max: 100, percentage: null };
    const score = COMPONENT_FIELDS.reduce((sum, [field]) => sum + (Number(values[field]) || 0), 0);
    const max = Number(values.max_score) || 0;
    return { score, max, percentage: max ? Math.round((score / max) * 10000) / 100 : null };
  };

  const handleSaveAll = async () => {
    if (!dirtyIds.size) {
      cancelEditMode();
      return;
    }
    setSavingAll(true);
    setActionError("");
    try {
      let latestBatch = batch;
      for (const subjectId of dirtyIds) {
        const values = editValues[subjectId];
        const payload = {
          max_score: Number(values.max_score) || 0,
          remarks: values.remarks,
        };
        COMPONENT_FIELDS.forEach(([field]) => { payload[field] = Number(values[field]) || 0; });
        const result = await onEditScore(subjectId, payload);
        if (result?.batch) latestBatch = result.batch;
      }
      onBatchUpdated?.(latestBatch);
      cancelEditMode();
    } catch (err) {
      setActionError(err.message || "Could not save these changes.");
    } finally {
      setSavingAll(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="result-batch-review-title"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <article className={`app-panel edit-modal-card result-batch-modal${editMode ? " is-editing" : ""}`}>
        <div className="edit-modal-head">
          <div>
            <h3 id="result-batch-review-title">{batch.title}</h3>
            <p>{editMode ? `Editing what ${batch.teacher || "the teacher"} submitted - same fields as their score entry form.` : `Exactly what ${batch.teacher || "the teacher"} submitted for review.`}</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="submission-meta-grid">
          <div><small>Class</small><strong>{batch.class_name || "-"}</strong></div>
          <div><small>Term</small><strong>{batch.term || "-"}</strong></div>
          <div><small>Teacher</small><strong>{batch.teacher || "-"}</strong></div>
          <div><small>Submitted</small><strong>{formatDate(batch.submitted_at)}</strong></div>
          <div><small>Status</small><strong>{batch.status}</strong></div>
          <div><small>Students / Scores</small><strong>{batch.student_count} / {batch.score_count}</strong></div>
        </div>

        {batch.admin_note ? <p className="form-feedback info">Admin note: {batch.admin_note}</p> : null}
        {actionError ? <p className="form-feedback error">{actionError}</p> : null}

        <div className="result-batch-student-list">
          {students.length ? students.map((student) => (
            <section key={student.student_id} className="result-batch-student">
              <header className="result-batch-student-head">
                <div>
                  <strong>{student.name}</strong>
                  <small>{student.student_id}</small>
                </div>
                <div className="result-batch-student-summary">
                  <span><small>Total</small>{tidyMarks(student.total_score)} / {tidyMarks(student.total_max)}</span>
                  <span><small>Percentage</small>{student.percentage != null ? `${student.percentage}%` : "-"}</span>
                  <span><small>Grade</small>{student.grade || "-"}</span>
                </div>
              </header>
              <div className="data-table-wrap">
                {editMode ? (
                  <table className="data-table result-batch-edit-table">
                    <thead>
                      <tr>
                        <th>Subject</th>
                        {COMPONENT_FIELDS.map(([field, label]) => <th key={field}>{label}</th>)}
                        <th>Max</th>
                        <th>Score / %</th>
                        <th>Remark</th>
                      </tr>
                    </thead>
                    <tbody>
                      {student.subjects.map((subject) => {
                        const values = editValues[subject.id] || editValuesForSubject(subject);
                        const preview = previewScore(subject.id);
                        return (
                          <tr key={subject.id}>
                            <td className="report-subject-name">{subject.subject || "-"}</td>
                            {COMPONENT_FIELDS.map(([field]) => (
                              <td key={field}>
                                <input
                                  type="number"
                                  className="result-batch-score-input"
                                  value={values[field]}
                                  onChange={(event) => handleFieldChange(subject.id, field, event.target.value)}
                                  min="0"
                                />
                              </td>
                            ))}
                            <td>
                              <input
                                type="number"
                                className="result-batch-score-input"
                                value={values.max_score}
                                onChange={(event) => handleFieldChange(subject.id, "max_score", event.target.value)}
                                min="1"
                              />
                            </td>
                            <td className="result-batch-score-preview">
                              {tidyMarks(preview.score)} / {tidyMarks(preview.max)}
                              {preview.percentage != null ? ` (${preview.percentage}%)` : ""}
                            </td>
                            <td>
                              <input
                                type="text"
                                className="result-batch-score-input result-batch-remark-input"
                                value={values.remarks}
                                onChange={(event) => handleFieldChange(subject.id, "remarks", event.target.value)}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr><th>Subject</th><th>Score</th><th>Max</th><th>%</th><th>Grade</th><th>Remark</th></tr>
                    </thead>
                    <tbody>
                      {student.subjects.map((subject) => (
                        <tr key={subject.id}>
                          <td>{subject.subject || "-"}</td>
                          <td>{tidyMarks(subject.score)}</td>
                          <td>{tidyMarks(subject.max_score)}</td>
                          <td>{subject.percentage != null ? `${subject.percentage}%` : "-"}</td>
                          <td>{subject.grade || "-"}</td>
                          <td>{subject.remark || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          )) : <p className="panel-empty">No student scores found in this submission.</p>}
        </div>

        <div className="result-batch-modal-actions">
          {editMode ? (
            <>
              <button type="button" className="btn-secondary" onClick={cancelEditMode} disabled={savingAll}>Cancel</button>
              <button type="button" className="btn-primary" onClick={handleSaveAll} disabled={savingAll}>
                {savingAll ? <><Spinner size={12} /> Saving...</> : dirtyIds.size ? `Save Changes (${dirtyIds.size})` : "Done"}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="btn-secondary" onClick={onClose} disabled={Boolean(actionBusy)}>Close</button>
              <button type="button" className="table-action danger" onClick={handleDelete} disabled={Boolean(actionBusy)}>
                {actionBusy === "delete" ? <><Spinner size={12} /> Deleting...</> : "Delete"}
              </button>
              <button type="button" className="table-action" onClick={enterEditMode} disabled={Boolean(actionBusy)}>
                Edit
              </button>
              <button type="button" className="btn-primary" onClick={handlePublish} disabled={Boolean(actionBusy)}>
                {actionBusy === "publish" ? <><Spinner size={12} /> Publishing...</> : "Publish Live"}
              </button>
            </>
          )}
        </div>
      </article>
    </div>
  );
}
