import { useCallback, useEffect, useState } from "react";
import { formatDate, requestJson } from "../AppShared";
import RichText from "./RichText";

/* One student's whole submitted paper, question by question.

   Every number shown is the one the API summed from the individual questions,
   never ExamAttempt.score - that field holds the objective-only subtotal until
   theory grades are published, so trusting it would print a summary that
   disagrees with the rows directly beneath it. */

const STATUS_META = {
  correct: { label: "Correct", tone: "correct" },
  incorrect: { label: "Incorrect", tone: "incorrect" },
  partial: { label: "Partly correct", tone: "partial" },
  unanswered: { label: "Unanswered", tone: "unanswered" },
  pending: { label: "Pending Grading", tone: "pending" },
};

const FILTERS = [
  { key: "all", label: "All questions" },
  { key: "incorrect", label: "Wrong only" },
  { key: "pending", label: "Pending grading" },
  { key: "unanswered", label: "Unanswered" },
];

const tidyMarks = (value) => {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/\.?0+$/, "");
};

export default function ExamSubmissionModal({ session, attemptId, studentName, onClose }) {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    if (!session || !attemptId) return;
    setLoading(true);
    setError("");
    try {
      const result = await requestJson(session, "GET", `/api/exams/attempt/${attemptId}/review/`);
      setReview(result);
    } catch (loadError) {
      setError(loadError.message || "Could not load this submission.");
      setReview(null);
    } finally {
      setLoading(false);
    }
  }, [session, attemptId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const questions = review?.questions || [];
  const visible = questions.filter((row) => {
    if (filter === "all") return true;
    if (filter === "incorrect") return row.status === "incorrect" || row.status === "partial";
    return row.status === filter;
  });

  const pendingCount = Number(review?.pending_questions || 0);

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="submission-review-title"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <article className="app-panel edit-modal-card submission-modal">
        <div className="edit-modal-head">
          <div>
            <h3 id="submission-review-title">{review?.student_name || studentName || "Submission"}</h3>
            <p>{review ? `${review.exam_title || "Exam"}${review.subject ? ` · ${review.subject}` : ""}` : "Loading submission..."}</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {loading ? <p className="panel-empty">Loading submission...</p> : null}
        {error ? (
          <div className="form-feedback error">
            {error}
            <button type="button" className="table-action" style={{ marginLeft: "0.5rem" }} onClick={load}>Retry</button>
          </div>
        ) : null}

        {review ? (
          <>
            <div className="submission-score-hero">
              <div className="submission-score-main">
                <small>Score</small>
                <strong>{tidyMarks(review.score)} / {tidyMarks(review.total_marks)}</strong>
                <span>{review.percentage}%{review.grade ? ` · Grade ${review.grade}` : ""}{review.grade_remark ? ` (${review.grade_remark})` : ""}</span>
              </div>
              <div className="submission-score-counts">
                <span className="tone-correct"><strong>{review.correct_questions}</strong> passed</span>
                <span className="tone-incorrect"><strong>{review.incorrect_questions}</strong> failed</span>
                {review.partial_questions ? <span className="tone-partial"><strong>{review.partial_questions}</strong> partial</span> : null}
                <span className="tone-unanswered"><strong>{review.unanswered_questions}</strong> unanswered</span>
                {pendingCount ? <span className="tone-pending"><strong>{pendingCount}</strong> pending</span> : null}
              </div>
            </div>

            {pendingCount ? (
              <p className="form-feedback warning submission-pending-note">
                {pendingCount} theory question{pendingCount === 1 ? " is" : "s are"} still awaiting manual grading, so this
                total covers {tidyMarks(review.graded_marks)} of {tidyMarks(review.total_marks)} marks. The percentage and
                grade will change once grading is published.
              </p>
            ) : null}

            <div className="submission-meta-grid">
              <div><small>Student ID</small><strong>{review.student_id || "-"}</strong></div>
              <div><small>Class</small><strong>{review.class_name || "-"}</strong></div>
              <div><small>Exam</small><strong>{review.exam_title || "-"}</strong></div>
              <div><small>Subject</small><strong>{review.subject || "-"}</strong></div>
              <div><small>Exam type</small><strong>{review.exam_type || "-"}</strong></div>
              <div><small>Submitted</small><strong>{formatDate(review.submitted_at)}</strong></div>
              <div><small>Questions</small><strong>{review.total_questions}</strong></div>
              <div><small>Answered</small><strong>{review.answered_questions} of {review.total_questions}</strong></div>
            </div>

            <div className="submission-filter-row">
              {FILTERS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={`finance-record-tab${filter === option.key ? " active" : ""}`}
                  onClick={() => setFilter(option.key)}
                >
                  {option.label}
                </button>
              ))}
              {review.auto_submitted ? <span className="finance-status status-pending">Auto-submitted</span> : null}
            </div>

            <div className="submission-question-list">
              {visible.length ? visible.map((row) => {
                const meta = STATUS_META[row.status] || STATUS_META.unanswered;
                return (
                  <section key={row.question_id} className={`submission-question tone-${meta.tone}`}>
                    <header className="submission-question-head">
                      <span className="submission-question-number">Q{row.number}</span>
                      <span className={`submission-status-pill tone-${meta.tone}`}>{meta.label}</span>
                      <span className="submission-question-marks">
                        {row.status === "pending" ? `— / ${tidyMarks(row.marks_possible)}` : `${tidyMarks(row.marks_awarded)} / ${tidyMarks(row.marks_possible)}`}
                        <small> marks</small>
                      </span>
                    </header>

                    {row.passage?.passage_text ? (
                      <div className="submission-passage">
                        {row.passage.title ? <h5>{row.passage.title}</h5> : null}
                        <RichText value={row.passage.passage_text} />
                      </div>
                    ) : null}

                    {/* Rendered as HTML: question text comes from the rich-text
                        editor, so escaping it would show raw tags. */}
                    <RichText className="submission-question-text" value={row.question_text} placeholder={<em>(No question text)</em>} />
                    {row.image ? <img className="submission-question-image" src={row.image} alt="" /> : null}

                    <div className="submission-answer-grid">
                      <div className="submission-answer given">
                        <small>Student answer</small>
                        {row.student_answer
                          ? <RichText value={row.student_answer} />
                          : <em className="submission-blank">No answer submitted</em>}
                      </div>
                      {/* A correct answer is meaningless for an ungraded theory
                          question and would read as the mark scheme leaking into
                          a pending row, so it is shown only once graded. */}
                      {row.status !== "pending" && row.correct_answer ? (
                        <div className="submission-answer expected">
                          <small>Correct answer</small>
                          <RichText value={row.correct_answer} />
                        </div>
                      ) : null}
                    </div>

                    {row.teacher_feedback ? (
                      <p className="submission-feedback"><small>Teacher feedback</small> {row.teacher_feedback}</p>
                    ) : null}
                  </section>
                );
              }) : <p className="panel-empty">No questions match this filter.</p>}
            </div>
          </>
        ) : null}
      </article>
    </div>
  );
}
