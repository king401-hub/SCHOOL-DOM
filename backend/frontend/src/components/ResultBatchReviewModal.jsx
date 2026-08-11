import { useState } from "react";
import { formatDate, Spinner } from "../AppShared";

/* Shows exactly what a teacher pushed for a result batch - every row here is
   read straight from the stored StudentSubjectScore records the batch
   review/publish/delete actions already act on (see
   _result_batch_detail_payload on the backend). Nothing here is
   recalculated except the per-student total/percentage/grade, which are
   plain sums of those same stored scores run through the same grading
   source of truth used everywhere else - not an alternate calculation. */

const tidyMarks = (value) => {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/\.?0+$/, "");
};

export default function ResultBatchReviewModal({ batch, onClose, onPublish, onReject, onDelete, confirmDelete }) {
  const [actionBusy, setActionBusy] = useState("");
  const [actionError, setActionError] = useState("");

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
  const handleReject = () => runAction("reject", () => onReject(batch.id));
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

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="result-batch-review-title"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <article className="app-panel edit-modal-card result-batch-modal">
        <div className="edit-modal-head">
          <div>
            <h3 id="result-batch-review-title">{batch.title}</h3>
            <p>Exactly what {batch.teacher || "the teacher"} submitted for review.</p>
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
              </div>
            </section>
          )) : <p className="panel-empty">No student scores found in this submission.</p>}
        </div>

        <div className="result-batch-modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={Boolean(actionBusy)}>Close</button>
          <button type="button" className="table-action danger" onClick={handleDelete} disabled={Boolean(actionBusy)}>
            {actionBusy === "delete" ? <><Spinner size={12} /> Deleting...</> : "Delete"}
          </button>
          <button type="button" className="table-action danger" onClick={handleReject} disabled={Boolean(actionBusy)}>
            {actionBusy === "reject" ? <><Spinner size={12} /> Rejecting...</> : "Reject"}
          </button>
          <button type="button" className="btn-primary" onClick={handlePublish} disabled={Boolean(actionBusy)}>
            {actionBusy === "publish" ? <><Spinner size={12} /> Publishing...</> : "Publish Live"}
          </button>
        </div>
      </article>
    </div>
  );
}
