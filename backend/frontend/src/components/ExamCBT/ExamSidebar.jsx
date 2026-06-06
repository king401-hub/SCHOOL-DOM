import React from "react";

const ExamSidebar = ({ activeSection, onSectionChange, totalQuestions, answeredQuestions }) => {
  return (
    <div className="exam-sidebar">
      <div className="sidebar-header">
        <h3>TEST NAVIGATION</h3>
      </div>

      <div className="sidebar-menu">
        <button
          className={`sidebar-item ${activeSection === "instructions" ? "active" : ""}`}
          onClick={() => onSectionChange("instructions")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 6h16M4 12h16M4 18h16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          INSTRUCTIONS
        </button>

        <button
          className={`sidebar-item ${activeSection === "questions" ? "active" : ""}`}
          onClick={() => onSectionChange("questions")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M7 7h4v4H7zM7 13h4v4H7zM13 7h4v4h-4zM13 13h4v4h-4z" fill="currentColor" />
          </svg>
          QUESTIONS
          <span className="question-count">
            {answeredQuestions}/{totalQuestions}
          </span>
        </button>

        <button
          className={`sidebar-item ${activeSection === "calculator" ? "active" : ""}`}
          onClick={() => onSectionChange("calculator")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <rect x="5" y="3" width="14" height="18" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M16 15h0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          CALCULATOR
        </button>

        <button
          className={`sidebar-item ${activeSection === "submit" ? "active" : ""}`}
          onClick={() => onSectionChange("submit")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M3 12l9 9 12-12"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          SUBMIT TEST
        </button>
      </div>
    </div>
  );
};

export default ExamSidebar;
