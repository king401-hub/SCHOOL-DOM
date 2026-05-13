import React, { useState, useEffect } from "react";
import "./ExamResult.css";
import RichQuizText from "../RichQuizText";

const ExamResult = ({ attemptId, session, onNavigate }) => {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedReview, setExpandedReview] = useState(null);
  const isTeacher = session?.user?.role === "teacher";

  useEffect(() => {
    if (!isTeacher) {
      setLoading(false);
      return;
    }
    const fetchResult = async () => {
      try {
        const headers = {};
        if (session?.access) {
          headers.Authorization = `Bearer ${session.access}`;
        }
        const response = await fetch(`/api/exams/result/${attemptId}/`, { headers });
        const data = await response.json();
        setResult(data);
      } catch (error) {
        console.error("Failed to load result:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [attemptId, session, isTeacher]);

  if (!isTeacher) {
    return (
      <div className="exam-completed-screen">
        <div className="exam-completed-card">
          <span className="exam-completed-mark">✓</span>
          <p className="exam-completed-kicker">Submission received</p>
          <h1>Exam Completed</h1>
          <p>Your result has been sent to your teacher for review and record keeping.</p>
          <button onClick={() => onNavigate?.("/dashboard")} className="btn-home">
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="result-loading">
        <div className="spinner"></div>
        <p>Loading results...</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="result-error">
        <h2>Failed to load exam results</h2>
        <button onClick={() => onNavigate?.("/dashboard")} className="btn-home">
          Go to dashboard
        </button>
      </div>
    );
  }

  const percentage = result.percentage;
  const isPassed = result.is_passed;
  const resultStatus = isPassed ? "PASSED" : "FAILED";

  return (
    <div className="exam-result">
      <div className="result-header">
        <h1>Exam Results</h1>
        <p className="result-title">{result.exam_title}</p>
      </div>

      <div className="result-container">
        {/* Score Card */}
        <div className={`score-card ${isPassed ? "passed" : "failed"}`}>
          <div className="score-display">
            <div className="score-circle">
              <svg viewBox="0 0 100 100" className="score-gauge">
                <circle cx="50" cy="50" r="45" className="gauge-bg" />
                <circle
                  cx="50"
                  cy="50"
                  r="45"
                  className="gauge-fill"
                  style={{
                    strokeDasharray: `${percentage * 2.83} 283`,
                  }}
                />
              </svg>
              <div className="score-text">
                <span className="percentage">{percentage.toFixed(1)}%</span>
              </div>
            </div>

            <div className="score-info">
              <h2 className={`status ${isPassed ? "passed" : "failed"}`}>
                {resultStatus}
              </h2>
              <p className="grade">Grade: <strong>{result.grade}</strong></p>
              <p className="score-breakdown">
                Score: <strong>{result.score}/{result.total_points}</strong> Points
              </p>
            </div>
          </div>

          <div className="result-meta">
            <div className="meta-item">
              <span className="meta-label">Submitted At:</span>
              <span className="meta-value">
                {new Date(result.submitted_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Performance Summary */}
        <div className="performance-summary">
          <h3>Performance Summary</h3>
          <div className="summary-grid">
            <div className="summary-card">
              <div className="summary-number">{result.answers_review.length}</div>
              <div className="summary-label">Total Questions</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">
                {result.answers_review.filter(a => a.is_correct).length}
              </div>
              <div className="summary-label">Correct Answers</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">
                {result.answers_review.filter(a => !a.is_correct).length}
              </div>
              <div className="summary-label">Incorrect Answers</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">{result.score}</div>
              <div className="summary-label">Total Points Earned</div>
            </div>
          </div>
        </div>

        {/* Detailed Review */}
        <div className="detailed-review">
          <h3>Detailed Review</h3>
          <div className="review-list">
            {result.answers_review.map((answer, index) => (
              <div
                key={index}
                className={`review-item ${answer.is_correct ? "correct" : "incorrect"}`}
              >
                <div
                  className="review-header"
                  onClick={() =>
                    setExpandedReview(expandedReview === index ? null : index)
                  }
                >
                  <div className="review-question-number">
                    <span className="question-num">Q{answer.question_number}</span>
                    <span className={`status-badge ${answer.is_correct ? "correct" : "incorrect"}`}>
                      {answer.is_correct ? "✓ Correct" : "✗ Incorrect"}
                    </span>
                  </div>
                  <span className="points-info">
                    {answer.points_earned}/{answer.total_points} Points
                  </span>
                  <button
                    className={`expand-btn ${expandedReview === index ? "expanded" : ""}`}
                  >
                    ▼
                  </button>
                </div>

                {expandedReview === index && (
                  <div className="review-content">
                    <div className="question-text">
                      <strong>Question:</strong>
                      <p><RichQuizText text={answer.question_text} /></p>
                    </div>

                    <div className="answer-section">
                      <div className="your-answer">
                        <strong>Your Answer:</strong>
                        <p><RichQuizText text={answer.user_answer || "Not answered"} /></p>
                      </div>

                      {!answer.is_correct && (
                        <div className="correct-answer">
                          <strong>Correct Answer:</strong>
                          <p><RichQuizText text={answer.correct_answer} /></p>
                        </div>
                      )}
                    </div>

                    {answer.explanation && (
                      <div className="explanation">
                        <strong>Explanation:</strong>
                        <p><RichQuizText text={answer.explanation} /></p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="result-actions">
          <button className="btn-download" onClick={() => window.print()}>
            📥 Download Result
          </button>
          <button className="btn-home" onClick={() => onNavigate?.("/dashboard")}>
            ← Back to Home
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExamResult;
