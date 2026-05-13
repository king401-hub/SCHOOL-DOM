import React, { useState } from "react";

const StudentInfo = ({ studentInfo, questionNavigator, onNavigateToQuestion }) => {
  const [expandNav, setExpandNav] = useState(false);

  const getQuestionStatus = (index) => {
    const questionId = index + 1;
    const isAnswered = questionNavigator.answers[questionId] !== null && questionNavigator.answers[questionId] !== undefined;
    const isCurrent = index === questionNavigator.current - 1;
    
    if (isCurrent) return "current";
    if (isAnswered) return "answered";
    return "unanswered";
  };

  const renderQuestionGrid = () => {
    const questions = [];
    const itemsPerRow = 5;
    
    for (let i = 0; i < questionNavigator.total; i++) {
      questions.push(
        <button
          key={i}
          className={`question-number ${getQuestionStatus(i)}`}
          onClick={() => onNavigateToQuestion(i)}
          title={`Question ${i + 1}`}
        >
          {i + 1}
        </button>
      );
    }

    return questions;
  };

  return (
    <div className="student-info">
      <div className="student-profile">
        <div className="student-avatar">
          {studentInfo?.avatar ? (
            <img src={studentInfo.avatar} alt={studentInfo.name} />
          ) : (
            <svg width="60" height="60" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="8" r="4" />
              <path d="M 12 14 C 7.6 14 4 16.7 4 20 L 4 22 L 20 22 L 20 20 C 20 16.7 16.4 14 12 14 Z" />
            </svg>
          )}
        </div>
        <div className="student-details">
          <h3 className="student-name">{studentInfo?.name || "Student Name"}</h3>
          <p className="student-id">{studentInfo?.id || "STU000000"}</p>
        </div>
      </div>

      <div className="question-navigator">
        <div className="navigator-header">
          <h4>Questions</h4>
          <button
            className="toggle-nav"
            onClick={() => setExpandNav(!expandNav)}
            aria-label="Toggle navigator"
          >
            {expandNav ? "−" : "+"}
          </button>
        </div>

        {expandNav && (
          <div className="question-grid">
            {renderQuestionGrid()}
          </div>
        )}

        <div className="navigator-legend">
          <div className="legend-item">
            <span className="legend-dot answered"></span>
            <span>Answered</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot current"></span>
            <span>Current</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot unanswered"></span>
            <span>Unanswered</span>
          </div>
        </div>
      </div>

      <div className="navigator-stats">
        <p>
          <span className="stat-label">Total:</span>
          <span className="stat-value">{questionNavigator.total}</span>
        </p>
        <p>
          <span className="stat-label">Answered:</span>
          <span className="stat-value">{questionNavigator.answered}</span>
        </p>
      </div>
    </div>
  );
};

export default StudentInfo;
