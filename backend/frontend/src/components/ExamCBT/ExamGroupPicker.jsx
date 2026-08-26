import React, { useEffect, useState } from "react";
import "./ExamsList.css";
import { Spinner } from "../../AppShared";

/* Shown after a student enters a group Exam PIN (StudentCbtEntryView's
   is_group response) - lets them pick which subject to take next. No new
   status endpoint: ExamListView's existing group_id filter already returns
   is_submitted/active_attempt_id per exam, and Start/Resume calls the
   completely unchanged StartExamView, same as the regular exam list. */
const ExamGroupPicker = ({ groupId, session, onNavigate }) => {
  const [subjects, setSubjects] = useState(session?.group_exams || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(null);

  useEffect(() => {
    if (!session?.group_id || String(session.group_id) !== String(groupId)) {
      onNavigate?.("/student-cbt", { replace: true });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`/api/exams/list/?group_id=${encodeURIComponent(groupId)}`, {
          headers: session?.access ? { Authorization: `Bearer ${session.access}` } : {},
        });
        if (!response.ok) throw new Error("Could not load this exam group's subjects.");
        const data = await response.json();
        if (!cancelled) setSubjects(data);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "Could not refresh subject status - showing what was loaded at PIN entry.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupId]);

  const subjectState = (subject) => {
    if (subject.is_submitted || subject.submitted_attempt_id) {
      return { label: "Submitted", action: "View Result", className: "submitted", canStart: false, canViewResult: Boolean(subject.submitted_attempt_id) };
    }
    if (subject.active_attempt_id) {
      return { label: "In progress", action: "Resume Exam", className: "in-progress", canStart: true };
    }
    return { label: "Not started", action: "Start Exam", className: "open", canStart: true };
  };

  const allDone = subjects.length > 0 && subjects.every((subject) => subject.is_submitted || subject.submitted_attempt_id);

  const handleStart = async (subjectId) => {
    setStarting(subjectId);
    setError("");
    try {
      const response = await fetch(`/api/exams/${subjectId}/start/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
        },
        body: JSON.stringify({ is_offline: false }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || payload.detail || payload.message || "Could not start this subject.");
      }
      const data = await response.json();
      onNavigate?.(`/exam/${data.attempt_id}/`);
    } catch (startError) {
      setError(startError.message || "Could not start this subject.");
      setStarting(null);
    }
  };

  const handleFinish = () => {
    window.sessionStorage.removeItem("schooldom.session");
    onNavigate?.("/student-cbt", { replace: true });
  };

  if (loading) {
    return (
      <div className="exams-loading">
        <div className="spinner"></div>
        <p>Loading subjects...</p>
      </div>
    );
  }

  return (
    <div className="exams-list-page">
      <div className="exams-header">
        <h1>{session?.group_title || "Exam Group"}</h1>
        <p>Enter each subject one at a time. You can come back here between subjects.</p>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="exams-container">
        {subjects.length > 0 ? (
          <div className="exams-grid">
            {subjects.map((subject) => {
              const state = subjectState(subject);
              return (
                <div key={subject.id} className="exam-card">
                  <div className="exam-card-header">
                    <div>
                      <span className={`exam-status ${state.className}`}>{state.label}</span>
                      <h3>{subject.subject || subject.title}</h3>
                    </div>
                    <span className="exam-duration">{subject.duration_minutes} mins</span>
                  </div>
                  <div className="exam-card-body">
                    <p className="exam-questions">
                      <strong>Questions:</strong> {subject.question_count ?? 0}
                    </p>
                  </div>
                  <div className="exam-card-footer">
                    {state.canViewResult ? (
                      <button className="btn-start-exam btn-view-result" onClick={() => onNavigate?.(`/exam-result/${subject.submitted_attempt_id}/`)}>
                        View Result
                      </button>
                    ) : (
                      <button
                        className="btn-start-exam"
                        onClick={() => handleStart(subject.id)}
                        disabled={!state.canStart || starting === subject.id}
                      >
                        {starting === subject.id ? <><Spinner size={14} /> Starting...</> : state.action}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="no-exams">
            <p>No subjects found for this exam group.</p>
          </div>
        )}
      </div>

      <div className="exams-header" style={{ marginTop: "1rem" }}>
        <button type="button" className="btn-exam-back" onClick={handleFinish}>
          {allDone ? "Finish and exit" : "Exit without finishing all subjects"}
        </button>
      </div>
    </div>
  );
};

export default ExamGroupPicker;
