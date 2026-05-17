import React, { useState, useEffect } from "react";
import RichQuizText from "../RichQuizText";

const QuestionDisplay = ({
  question,
  questionNumber,
  totalQuestions,
  section,
  selectedAnswer,
  onSaveAnswer,
  onClearResponse,
  onNext,
  onPrevious,
  canGoNext,
  canGoPrevious,
  onSubmit,
  submitting,
  onFlagQuestion,
  flagStatus,
}) => {
  const [localAnswer, setLocalAnswer] = useState(selectedAnswer);
  const [showFlagForm, setShowFlagForm] = useState(false);
  const [flagReason, setFlagReason] = useState("");

  useEffect(() => {
    setLocalAnswer(selectedAnswer);
  }, [question.id, selectedAnswer]);

  const handleOptionChange = (optionIndex) => {
    setLocalAnswer(optionIndex);
    onSaveAnswer(question.id, optionIndex);
  };

  const handleClear = () => {
    setLocalAnswer(null);
    onClearResponse();
  };

  const handleFlagSubmit = async (event) => {
    event.preventDefault();
    try {
      await onFlagQuestion?.(question.id, flagReason);
      setFlagReason("");
      setShowFlagForm(false);
    } catch {
      // The parent status message gives the student the actionable error.
    }
  };

  const getOptionLabel = (index) => {
    const labels = ["A", "B", "C", "D", "E"];
    return labels[index] || String.fromCharCode(65 + index);
  };

  return (
    <div className="question-display">
      <div className="question-header">
        <div className="section-info">
          <span className="section-label">Section:</span>
          <span className="section-name">{section}</span>
        </div>
        <div className="question-counter">Question {questionNumber} of {totalQuestions}</div>
      </div>

      <div className="question-content">
        {question.group ? (
          <article className="question-passage-card">
            <div className="question-passage-head">
              <span>{question.group.group_type || "passage"}</span>
              <strong>{question.group.title || "Shared passage"}</strong>
            </div>
            {question.group.passage_text ? <div className="question-passage-text"><RichQuizText text={question.group.passage_text} /></div> : null}
            {question.group.image ? <img src={question.group.image} alt={question.group.title || "Passage illustration"} className="question-passage-image" /> : null}
          </article>
        ) : null}
        <div className="question-text">
          <h2><RichQuizText text={question.text} /></h2>
          {question.image ? (
            <img src={question.image} alt="Question" className="question-image" />
          ) : null}
        </div>

        <div className="question-options">
          {question.options?.map((option, index) => (
            <label key={index} className={`option-label ${localAnswer === index ? "selected" : ""}`}>
              <input
                type="radio"
                name={`question-${question.id}`}
                value={index}
                checked={localAnswer === index}
                onChange={() => handleOptionChange(index)}
                className="option-input"
              />
              <span className="option-letter">{getOptionLabel(index)}.</span>
              <span className="option-text"><RichQuizText text={option} /></span>
            </label>
          ))}
        </div>

        <button className="btn-clear-response" onClick={handleClear}>
          Clear Response
        </button>
        <button type="button" className="btn-flag-question" onClick={() => setShowFlagForm(true)}>
          Flag inappropriate question
        </button>
        {flagStatus?.error ? <p className="question-flag-feedback error">{flagStatus.error}</p> : null}
        {flagStatus?.success ? <p className="question-flag-feedback success">Question report sent.</p> : null}
      </div>

      <div className="question-navigation">
        <button className="btn-previous" onClick={onPrevious} disabled={!canGoPrevious}>
          Previous
        </button>
        <button className="btn-save-next" onClick={onNext} disabled={!canGoNext}>
          Save & Next
        </button>
        <button className="btn-submit-exam inline" onClick={onSubmit} disabled={submitting}>
          {submitting ? "Submitting..." : "Submit Test"}
        </button>
      </div>
      {showFlagForm ? (
        <div className="question-flag-modal" role="dialog" aria-modal="true" aria-labelledby="question-flag-title">
          <form className="question-flag-card" onSubmit={handleFlagSubmit}>
            <h3 id="question-flag-title">Flag inappropriate question</h3>
            <p>Describe what is inappropriate or wrong with this question.</p>
            <textarea
              value={flagReason}
              onChange={(event) => setFlagReason(event.target.value)}
              maxLength={2000}
              required
              autoFocus
            />
            {flagStatus?.error ? <p className="question-flag-feedback error">{flagStatus.error}</p> : null}
            <div className="question-flag-actions">
              <button type="button" onClick={() => setShowFlagForm(false)} disabled={flagStatus?.busy}>
                Cancel
              </button>
              <button type="submit" disabled={flagStatus?.busy || !flagReason.trim()}>
                {flagStatus?.busy ? "Sending..." : "Send report"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
};

export default QuestionDisplay;
