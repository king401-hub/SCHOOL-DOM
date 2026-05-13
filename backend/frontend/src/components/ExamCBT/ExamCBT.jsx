import React, { useState, useEffect, useCallback, useRef } from "react";
import "./ExamCBT.css";
import ExamHeader from "./ExamHeader";
import ExamSidebar from "./ExamSidebar";
import QuestionDisplay from "./QuestionDisplay";
import StudentInfo from "./StudentInfo";
import SubmitModal from "./SubmitModal";

const CBT_CACHE_KEY = "schooldom.cbt_attempt_cache";
const CBT_SUBMISSION_QUEUE_KEY = "schooldom.cbt_submission_queue";

function readJsonStore(key, fallback) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    window.localStorage.removeItem(key);
    return fallback;
  }
}

function writeJsonStore(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function cacheAttemptPackage(attemptId, payload) {
  const cache = readJsonStore(CBT_CACHE_KEY, {});
  cache[attemptId] = { ...payload, cached_at: new Date().toISOString() };
  writeJsonStore(CBT_CACHE_KEY, cache);
}

function updateCachedAnswers(attemptId, answers) {
  const cache = readJsonStore(CBT_CACHE_KEY, {});
  if (!cache[attemptId]) return;
  cache[attemptId] = { ...cache[attemptId], answers, cached_at: new Date().toISOString() };
  writeJsonStore(CBT_CACHE_KEY, cache);
}

function markCachedSubmitted(attemptId) {
  const cache = readJsonStore(CBT_CACHE_KEY, {});
  if (!cache[attemptId]) return;
  cache[attemptId] = {
    ...cache[attemptId],
    offline_submitted: true,
    submitted_at: new Date().toISOString(),
    cached_at: new Date().toISOString(),
  };
  writeJsonStore(CBT_CACHE_KEY, cache);
}

function queueOfflineSubmission(attemptId, payload) {
  const queue = readJsonStore(CBT_SUBMISSION_QUEUE_KEY, []);
  const next = queue.filter((item) => String(item.attempt_id) !== String(attemptId));
  next.push(payload);
  writeJsonStore(CBT_SUBMISSION_QUEUE_KEY, next);
}

async function syncQueuedSubmissions(session) {
  const queue = readJsonStore(CBT_SUBMISSION_QUEUE_KEY, []);
  if (!queue.length || !navigator.onLine) return;
  const remaining = [];
  for (const item of queue) {
    try {
      const response = await fetch("/api/exams/offline/sync/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
        },
        body: JSON.stringify(item),
      });
      if (!response.ok) throw new Error("Sync failed");
    } catch {
      remaining.push(item);
    }
  }
  writeJsonStore(CBT_SUBMISSION_QUEUE_KEY, remaining);
}

const ExamCBT = ({ attemptId, session, onNavigate }) => {
  const [examData, setExamData] = useState(null);
  const [attemptData, setAttemptData] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [navSection, setNavSection] = useState("questions");
  const [studentInfo, setStudentInfo] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [flagStatus, setFlagStatus] = useState({});
  const [offlineMode, setOfflineMode] = useState(false);
  const [securityWarning, setSecurityWarning] = useState("");
  const [securityWarningOpen, setSecurityWarningOpen] = useState(false);
  const [fullscreenPrompt, setFullscreenPrompt] = useState(false);
  const warningIssuedRef = useRef(false);
  const completedRef = useRef(false);
  const submittingRef = useRef(false);
  const answersRef = useRef({});
  const violationCooldownRef = useRef(0);

  useEffect(() => {
    completedRef.current = completed;
  }, [completed]);

  useEffect(() => {
    submittingRef.current = submitting;
  }, [submitting]);

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  const requestExamFullscreen = useCallback(async () => {
    const root = document.documentElement;
    try {
      if (!document.fullscreenElement && root.requestFullscreen) {
        await root.requestFullscreen();
      }
      setFullscreenPrompt(false);
      return true;
    } catch {
      setFullscreenPrompt(true);
      return false;
    }
  }, []);

  // Fetch exam data
  useEffect(() => {
    const fetchExamData = async () => {
      try {
        const headers = {};
        if (session?.access) {
          headers.Authorization = `Bearer ${session.access}`;
        }
        const response = await fetch(`/api/exams/attempt/${attemptId}/`, { headers });
        if (!response.ok) throw new Error("Could not load online attempt");
        const data = await response.json();
        
        setExamData(data.exam);
        setAttemptData(data.attempt);
        setQuestions(data.questions);
        setAnswers(data.answers || {});
        setTimeRemaining(data.time_remaining_seconds || data.exam.duration_minutes * 60);
        setStudentInfo(data.student);
        cacheAttemptPackage(attemptId, data);
        setLoading(false);
      } catch (error) {
        console.error("Failed to load exam:", error);
        const cached = readJsonStore(CBT_CACHE_KEY, {})[attemptId];
        if (cached?.exam && cached?.questions?.length) {
          setOfflineMode(true);
          setExamData(cached.exam);
          setAttemptData(cached.attempt);
          setQuestions(cached.questions);
          setAnswers(cached.answers || {});
          setTimeRemaining(cached.time_remaining_seconds || cached.exam.duration_minutes * 60);
          setStudentInfo(cached.student);
          if (cached.offline_submitted) {
            setCompleted(true);
          }
        }
        setLoading(false);
      }
    };

    fetchExamData();
  }, [attemptId, session]);

  // Save answer
  const handleSaveAnswer = useCallback(
    async (questionId, selectedOptions) => {
      const nextAnswers = { ...answersRef.current, [questionId]: selectedOptions };
      answersRef.current = nextAnswers;
      setAnswers(nextAnswers);
      updateCachedAnswers(attemptId, nextAnswers);

      try {
        const response = await fetch(`/api/exams/attempt/${attemptId}/answer/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
          },
          body: JSON.stringify({
            question_id: questionId,
            selected_options: selectedOptions,
          }),
        });
        if (!response.ok) throw new Error("Could not save answer online");
        if (offlineMode) setOfflineMode(false);
      } catch (error) {
        setOfflineMode(true);
        console.error("Failed to save answer:", error);
      }
    },
    [attemptId, offlineMode, session]
  );

  // Clear response
  const handleClearResponse = () => {
    const currentQuestion = questions[currentQuestionIndex];
    handleSaveAnswer(currentQuestion.id, null);
  };

  const handleFlagQuestion = useCallback(
    async (questionId, reason) => {
      setFlagStatus((prev) => ({ ...prev, [questionId]: { busy: true } }));
      try {
        const response = await fetch(`/api/exams/attempt/${attemptId}/flag-question/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
          },
          body: JSON.stringify({
            question_id: questionId,
            reason,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || data.message || "Could not send the question report.");
        }
        setFlagStatus((prev) => ({ ...prev, [questionId]: { busy: false, success: true } }));
      } catch (error) {
        setFlagStatus((prev) => ({
          ...prev,
          [questionId]: {
            busy: false,
            error: error.message || "Could not send the question report.",
          },
        }));
        throw error;
      }
    },
    [attemptId, session]
  );

  // Navigate to question
  const handleNavigateToQuestion = (index) => {
    setCurrentQuestionIndex(index);
  };

  // Save and go to next
  const handleSaveAndNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    }
  };

  // Go to previous
  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1);
    }
  };

  // Submit exam
  const handleSubmitExam = useCallback(async () => {
    if (submittingRef.current || completedRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setSubmitError("");
    try {
      await syncQueuedSubmissions(session);
      const response = await fetch(`/api/exams/attempt/${attemptId}/submit/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access ? { Authorization: `Bearer ${session.access}` } : {}),
        },
      });

      if (response.ok) {
        await response.json();
        setShowSubmitModal(false);
        setCompleted(true);
        return;
      }
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || data.message || "Error submitting exam. Please try again.");
    } catch (error) {
      console.error("Failed to submit exam:", error);
      const cached = readJsonStore(CBT_CACHE_KEY, {})[attemptId];
      const looksOffline =
        !navigator.onLine ||
        error?.name === "TypeError" ||
        String(error?.message || "").toLowerCase().includes("fetch") ||
        String(error?.message || "").toLowerCase().includes("network");
      if (cached?.exam && looksOffline) {
        queueOfflineSubmission(attemptId, {
          offline_attempt_id: `offline-${attemptId}`,
          attempt_id: attemptId,
          exam_id: cached.exam.id,
          started_at: cached.attempt?.start_time || new Date().toISOString(),
          submitted_at: new Date().toISOString(),
          answers: answersRef.current,
        });
        markCachedSubmitted(attemptId);
        setOfflineMode(true);
        setShowSubmitModal(false);
        setCompleted(true);
        return;
      }
      setSubmitError(error.message || "Error submitting exam. Please try again.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }, [attemptId, session]);

  const handleSecurityViolation = useCallback(
    async (reason) => {
      if (!examData || completedRef.current || submittingRef.current) {
        return;
      }
      const now = Date.now();
      if (now - violationCooldownRef.current < 1200) {
        return;
      }
      violationCooldownRef.current = now;

      if (!warningIssuedRef.current) {
        warningIssuedRef.current = true;
        setSecurityWarning(`${reason}. This is your only warning. The exam will be submitted automatically if it happens again.`);
        setSecurityWarningOpen(true);
        return;
      }

      setSecurityWarning(`${reason}. The exam is being submitted automatically.`);
      setSecurityWarningOpen(true);
      await handleSubmitExam();
    },
    [examData, handleSubmitExam]
  );

  // Timer countdown
  useEffect(() => {
    if (!examData || timeRemaining <= 0) return;

    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          handleSubmitExam();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [examData, handleSubmitExam, timeRemaining]);

  useEffect(() => {
    if (!examData || completed) {
      return undefined;
    }

    requestExamFullscreen();

    const blockInteraction = (event) => {
      event.preventDefault();
      setSecurityWarning((current) => current || "Copy, paste, and right-click are disabled during this exam.");
    };
    const blockKeys = (event) => {
      const key = String(event.key || "").toLowerCase();
      if ((event.ctrlKey || event.metaKey) && ["c", "x", "v", "a", "s", "p"].includes(key)) {
        event.preventDefault();
        setSecurityWarning((current) => current || "Keyboard shortcuts for copy, paste, save, and print are disabled during this exam.");
        setSecurityWarningOpen(true);
      }
      if ((event.ctrlKey || event.metaKey) && ["t", "n", "w"].includes(key)) {
        event.preventDefault();
        handleSecurityViolation("Opening another tab or window was attempted");
      }
      if (event.key === "F12" || ((event.ctrlKey || event.metaKey) && event.shiftKey && ["i", "j", "c"].includes(key))) {
        event.preventDefault();
        handleSecurityViolation("Developer tools access was attempted");
      }
    };
    const handleVisibilityChange = () => {
      if (document.hidden) {
        handleSecurityViolation("Opening or switching to another tab was detected");
      }
    };
    const handleBlur = () => {
      window.setTimeout(() => {
        if (!document.hasFocus() && !completedRef.current && !submittingRef.current) {
          handleSecurityViolation("Leaving the exam window was detected");
        }
      }, 250);
    };
    const handleBeforeUnload = (event) => {
      if (!completedRef.current && !submittingRef.current) {
        event.preventDefault();
        event.returnValue = "Leaving this exam page will be recorded as a warning.";
        handleSecurityViolation("Leaving or reloading the exam page was attempted");
      }
    };
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && !completedRef.current && !submittingRef.current) {
        setFullscreenPrompt(true);
        handleSecurityViolation("Exiting full-screen mode was detected");
      }
    };

    document.addEventListener("contextmenu", blockInteraction);
    document.addEventListener("copy", blockInteraction);
    document.addEventListener("cut", blockInteraction);
    document.addEventListener("paste", blockInteraction);
    document.addEventListener("keydown", blockKeys);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      document.removeEventListener("contextmenu", blockInteraction);
      document.removeEventListener("copy", blockInteraction);
      document.removeEventListener("cut", blockInteraction);
      document.removeEventListener("paste", blockInteraction);
      document.removeEventListener("keydown", blockKeys);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [completed, examData, handleSecurityViolation, requestExamFullscreen]);

  useEffect(() => {
    const sync = () => syncQueuedSubmissions(session);
    window.addEventListener("online", sync);
    sync();
    return () => window.removeEventListener("online", sync);
  }, [session]);

  if (loading) {
    return (
      <div className="exam-loading">
        <div className="spinner"></div>
        <p>Loading exam...</p>
      </div>
    );
  }

  if (!examData || !questions.length) {
    return <div className="exam-error">Failed to load exam data</div>;
  }

  if (completed) {
    return (
      <div className="exam-completed-screen">
        <div className="exam-completed-card">
          <span className="exam-completed-mark">✓</span>
          <p className="exam-completed-kicker">Submission received</p>
          <h1>Exam Completed</h1>
          <p>{offlineMode ? "Your answers were saved offline and will sync for grading when internet is available." : "Your answers have been submitted successfully. Your teacher will review the result and keep it for records."}</p>
          <button type="button" className="btn-home" onClick={() => onNavigate?.("/dashboard", { replace: true })}>
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  const answeredCount = Object.keys(answers).filter((k) => answers[k] !== null).length;
  const sessionStudentInfo = {
    name: session?.user?.full_name || session?.user?.name || session?.user?.email || "Student",
    id: session?.user?.student_id || session?.user?.admission_number || session?.user?.username || session?.user?.email || "Student ID",
    avatar: session?.user?.profile_picture || "",
  };
  const resolvedStudentInfo = {
    ...sessionStudentInfo,
    ...(studentInfo || {}),
    name: studentInfo?.name || studentInfo?.full_name || sessionStudentInfo.name,
    id: studentInfo?.id || studentInfo?.student_id || studentInfo?.admission_number || sessionStudentInfo.id,
    avatar: studentInfo?.avatar || studentInfo?.profile_picture || sessionStudentInfo.avatar,
  };

  return (
    <div className="exam-cbt">
      {fullscreenPrompt ? (
        <div className="exam-security-gate">
          <div className="exam-security-card">
            <h2>Full-screen mode required</h2>
            <p>This exam must remain in full-screen mode until it is submitted.</p>
            <button type="button" onClick={requestExamFullscreen}>
              Enter Full Screen
            </button>
          </div>
        </div>
      ) : null}
      {securityWarning ? (
        <div className="exam-security-warning" role="alert">
          {securityWarning}
        </div>
      ) : null}
      {securityWarning && securityWarningOpen && !fullscreenPrompt ? (
        <div className="exam-security-alert" role="alertdialog" aria-modal="true" aria-labelledby="exam-security-alert-title">
          <div className="exam-security-alert-card">
            <p className="exam-security-alert-kicker">Exam integrity warning</p>
            <h2 id="exam-security-alert-title">Stay on the exam page</h2>
            <p>{securityWarning}</p>
            <button
              type="button"
              onClick={() => {
                setSecurityWarningOpen(false);
                requestExamFullscreen();
              }}
            >
              Continue Exam
            </button>
          </div>
        </div>
      ) : null}
      <ExamHeader
        title={`${examData.title}${offlineMode ? " (Offline)" : ""}`}
        timeRemaining={timeRemaining}
        onSubmitClick={() => setShowSubmitModal(true)}
      />

        <div className="exam-container">
        <ExamSidebar
          activeSection={navSection}
          onSectionChange={setNavSection}
          totalQuestions={questions.length}
          answeredQuestions={answeredCount}
        />

        {navSection === "questions" ? (
          <>
            <QuestionDisplay
              question={currentQuestion}
              questionNumber={currentQuestionIndex + 1}
              totalQuestions={questions.length}
              section={examData.title}
              selectedAnswer={answers[currentQuestion.id] ?? null}
              onSaveAnswer={handleSaveAnswer}
              onClearResponse={handleClearResponse}
              onNext={handleSaveAndNext}
              onPrevious={handlePrevious}
              canGoNext={currentQuestionIndex < questions.length - 1}
              canGoPrevious={currentQuestionIndex > 0}
              onSubmit={() => setShowSubmitModal(true)}
              submitting={submitting}
              onFlagQuestion={handleFlagQuestion}
              flagStatus={flagStatus[currentQuestion.id]}
            />

            <StudentInfo
              studentInfo={resolvedStudentInfo}
              questionNavigator={{
                total: questions.length,
                current: currentQuestionIndex + 1,
                answered: answeredCount,
                answers,
              }}
              onNavigateToQuestion={handleNavigateToQuestion}
            />
          </>
        ) : navSection === "instructions" ? (
          <div className="exam-instructions">
            <h2>Exam Instructions</h2>
            <div className="instructions-content">
              {examData.instructions ? (
                <div dangerouslySetInnerHTML={{ __html: examData.instructions }} />
              ) : (
                <>
                  <h3>General Instructions</h3>
                  <ul>
                    <li>Read each question carefully before selecting an answer</li>
                    <li>You can review and change your answers before submission</li>
                    <li>Click "Save & Next" to proceed to the next question</li>
                    <li>Your answers are automatically saved as you proceed</li>
                    <li>You have {examData.duration_minutes} minutes to complete this exam</li>
                    <li>Click "Submit Test" when you are ready to submit your exam</li>
                  </ul>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="exam-submit-section">
            <h2>Submit Test</h2>
            <div className="submit-summary">
              <p>
                Total Questions: <strong>{questions.length}</strong>
              </p>
              <p>
                Answered: <strong>{answeredCount}</strong>
              </p>
              <p>
                Not Answered:{" "}
                <strong>{questions.length - answeredCount}</strong>
              </p>
              <button
                className="btn-submit-exam"
                onClick={() => setShowSubmitModal(true)}
              >
                Submit Test
              </button>
            </div>
          </div>
        )}
      </div>

      {showSubmitModal && (
        <SubmitModal
          totalQuestions={questions.length}
          answeredQuestions={answeredCount}
          onConfirm={handleSubmitExam}
          onCancel={() => setShowSubmitModal(false)}
        />
      )}
      {submitError ? <div className="exam-submit-error">{submitError}</div> : null}
    </div>
  );
};

export default ExamCBT;
