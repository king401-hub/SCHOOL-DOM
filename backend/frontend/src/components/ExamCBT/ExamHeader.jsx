import React from "react";

const ExamHeader = ({ title, timeRemaining, onSubmitClick, onCalculatorClick }) => {
  const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="exam-header">
      <div className="exam-header-left">
        <div className="cbt-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="2" width="20" height="14" rx="2" stroke="white" strokeWidth="2" />
            <line x1="2" y1="8" x2="22" y2="8" stroke="white" strokeWidth="2" />
            <line x1="6" y1="12" x2="6" y2="16" stroke="white" strokeWidth="2" />
            <line x1="18" y1="12" x2="18" y2="16" stroke="white" strokeWidth="2" />
          </svg>
          <span>CBT</span>
        </div>
      </div>

      <div className="exam-header-center">
        <h1>{title}</h1>
      </div>

      <div className="exam-header-right">
        <div className="time-left">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
            <path d="M12 6v6l4 2.4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <div>
            <div className="time-label">Time Left</div>
            <div className="time-value">{formatTime(timeRemaining)}</div>
          </div>
        </div>

        <button type="button" className="btn-calculator" onClick={onCalculatorClick}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="5" y="3" width="14" height="18" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M16 15h0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Calculator
        </button>

        <button className="btn-submit" onClick={onSubmitClick}>
          Submit Test
        </button>
      </div>
    </div>
  );
};

export default ExamHeader;
