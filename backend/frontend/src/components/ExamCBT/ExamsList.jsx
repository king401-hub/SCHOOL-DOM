import React, { useEffect, useState } from "react";
import "./ExamsList.css";

const CBT_EXAMS_CACHE_KEY = "schooldom.cbt_available_exams";

function cacheScope(session) {
  return String(
    session?.school_code ||
      session?.school?.school_code ||
      session?.user?.tenant_id ||
      session?.user?.tenant ||
      session?.user?.id ||
      "anonymous"
  ).toLowerCase();
}

function scopedExamsCacheKey(session) {
  return `${CBT_EXAMS_CACHE_KEY}.${cacheScope(session)}`;
}

const ExamsList = ({ session, onNavigate }) => {
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(null);
  const [pinExam, setPinExam] = useState(null);
  const [examPin, setExamPin] = useState("");
  const [pinError, setPinError] = useState("");
  const [currentTime, setCurrentTime] = useState(() => new Date());

  useEffect(() => {
    const fetchExams = async () => {
      try {
        const headers = {};
        if (session?.access) {
          headers.Authorization = `Bearer ${session.access}`;
        }
        const response = await fetch("/api/exams/list/", { headers });
        if (!response.ok) throw new Error("Failed to fetch exams");
        const data = await response.json();
        setExams(data);
        window.localStorage.setItem(scopedExamsCacheKey(session), JSON.stringify(data));
      } catch (err) {
        const cached = JSON.parse(window.localStorage.getItem(scopedExamsCacheKey(session)) || "[]");
        if (cached.length) {
          setExams(cached);
          setError("Offline mode: showing the last exams loaded on this device.");
        } else {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchExams();
  }, [session]);

  useEffect(() => {
    const intervalId = window.setInterval(() => setCurrentTime(new Date()), 30000);
    return () => window.clearInterval(intervalId);
  }, []);

  const formatDateTime = (value) => {
    if (!value) return "Not set";
    return new Intl.DateTimeFormat("en-NG", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  };

  const getExamState = (exam) => {
    const startDate = new Date(exam.start_date);
    const endDate = new Date(exam.end_date);

    if (currentTime < startDate) {
      return {
        label: "Scheduled",
        action: `Starts ${formatDateTime(exam.start_date)}`,
        canStart: false,
        className: "scheduled",
      };
    }

    if (currentTime > endDate) {
      return {
        label: "Ended",
        action: "Exam ended",
        canStart: false,
        className: "ended",
      };
    }

    return {
      label: "Open now",
      action: "Start Exam",
      canStart: true,
      className: "open",
    };
  };

  const handleStartExam = async (examId, pin = "") => {
    setStarting(examId);
    setPinError("");
    try {
      const response = await fetch(`/api/exams/${examId}/start/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
        },
        body: JSON.stringify({ is_offline: false, pin }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || payload.detail || "Failed to start exam");
      }

      const data = await response.json();
      setPinExam(null);
      setExamPin("");
      onNavigate?.(`/exam/${data.attempt_id}/`);
    } catch (err) {
      if (pinExam) {
        setPinError(err.message);
      } else {
        alert(`Error: ${err.message}`);
      }
      setStarting(null);
    }
  };

  const requestStartExam = (exam) => {
    if (exam.pin_required) {
      setPinExam(exam);
      setExamPin("");
      setPinError("");
      return;
    }
    handleStartExam(exam.id);
  };

  const submitPin = (event) => {
    event.preventDefault();
    if (!pinExam) return;
    handleStartExam(pinExam.id, examPin);
  };

  if (loading) {
    return (
      <div className="exams-loading">
        <div className="spinner"></div>
        <p>Loading exams...</p>
      </div>
    );
  }

  return (
    <div className="exams-list-page">
      <div className="exams-header">
        <button type="button" className="btn-exam-back" onClick={() => onNavigate?.("/dashboard")}>
          Back to dashboard
        </button>
        <h1>Available Exams</h1>
        <p>Set exams appear here immediately, and open automatically at the scheduled time</p>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="exams-container">
        {exams.length > 0 ? (
          <div className="exams-grid">
            {exams.map((exam) => {
              const examState = getExamState(exam);
              const questionCount = exam.question_count ?? exam.questions?.length ?? 0;

              return (
                <div key={exam.id} className="exam-card">
                  <div className="exam-card-header">
                    <div>
                      <span className={`exam-status ${examState.className}`}>{examState.label}</span>
                      <h3>{exam.title}</h3>
                    </div>
                    <span className="exam-duration">{exam.duration_minutes} mins</span>
                  </div>

                  <div className="exam-card-body">
                    {(exam.subject_name || exam.subject) && (
                      <p className="exam-subject">
                        <strong>Subject:</strong> {exam.subject_name || exam.subject}
                      </p>
                    )}
                    {exam.class_name && (
                      <p className="exam-subject">
                        <strong>Class:</strong> {exam.class_name}
                      </p>
                    )}
                    <p className="exam-questions">
                      <strong>Questions:</strong> {questionCount}
                    </p>
                    <p className="exam-schedule">
                      <strong>Starts:</strong> {formatDateTime(exam.start_date)}
                    </p>
                    <p className="exam-schedule">
                      <strong>Ends:</strong> {formatDateTime(exam.end_date)}
                    </p>
                    {exam.pin_required && (
                      <p className="exam-pin-required">
                        <strong>PIN required</strong>
                      </p>
                    )}
                  </div>

                  <div className="exam-card-footer">
                    <button
                      className="btn-start-exam"
                      onClick={() => requestStartExam(exam)}
                      disabled={!examState.canStart || starting === exam.id}
                    >
                      {starting === exam.id ? "Starting..." : examState.action}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="no-exams">
            <p>No exams have been set for your class yet</p>
          </div>
        )}
      </div>

      {pinExam && (
        <div className="exam-pin-modal" role="dialog" aria-modal="true" aria-labelledby="exam-pin-title">
          <form className="exam-pin-card" onSubmit={submitPin}>
            <h2 id="exam-pin-title">Enter Exam PIN</h2>
            <p>{pinExam.title}</p>
            <input
              value={examPin}
              onChange={(event) => {
                setExamPin(event.target.value.toUpperCase());
                setPinError("");
              }}
              placeholder="Exam PIN"
              autoComplete="one-time-code"
              autoFocus
              required
            />
            {pinError && <div className="exam-pin-error">{pinError}</div>}
            <div className="exam-pin-actions">
              <button type="button" className="btn-exam-pin-secondary" onClick={() => setPinExam(null)}>
                Cancel
              </button>
              <button type="submit" className="btn-exam-pin-primary" disabled={starting === pinExam.id}>
                {starting === pinExam.id ? "Checking..." : "Continue"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default ExamsList;
