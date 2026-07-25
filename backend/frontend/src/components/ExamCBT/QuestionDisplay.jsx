import React, { useState, useEffect } from "react";
import RichQuizText from "../RichQuizText";

const THEORY_QUESTION_TYPES = new Set(["short_answer", "paragraph", "essay"]);

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
  const isTheoryQuestion = THEORY_QUESTION_TYPES.has(question.question_type);
  const [localAnswer, setLocalAnswer] = useState(selectedAnswer);
  const [showFlagForm, setShowFlagForm] = useState(false);
  const [flagReason, setFlagReason] = useState("");
  const [openImage, setOpenImage] = useState(null);

  useEffect(() => {
    setLocalAnswer(selectedAnswer);
  }, [question.id, selectedAnswer]);

  const handleOptionChange = (optionIndex) => {
    setLocalAnswer(optionIndex);
    onSaveAnswer(question.id, optionIndex);
  };

  const handleTextAnswerChange = (event) => {
    setLocalAnswer(event.target.value);
  };

  const handleTextAnswerBlur = () => {
    onSaveAnswer(question.id, localAnswer ?? "", true);
  };

  // Theory answers save on blur/navigation, not every keystroke - flush
  // whatever's in the box first so Next/Previous/Submit never drop an
  // edit the student never blurred away from.
  const flushTheoryAnswer = () => {
    if (isTheoryQuestion) onSaveAnswer(question.id, localAnswer ?? "", true);
  };

  const handleClear = () => {
    setLocalAnswer(isTheoryQuestion ? "" : null);
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

  const renderClickableImage = (src, alt, className) => (
    <button type="button" className="question-image-button" onClick={() => setOpenImage({ src, alt })} aria-label={`Open ${alt}`}>
      <img src={src} alt={alt} className={className} />
    </button>
  );

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
            {question.group.image ? renderClickableImage(question.group.image, question.group.title || "Passage illustration", "question-passage-image") : null}
          </article>
        ) : null}
        <div className="question-text">
          <h2><RichQuizText text={question.text} /></h2>
          {question.image ? (
            renderClickableImage(question.image, "Question", "question-image")
          ) : null}
          {question.attachment ? (
            <a className="question-attachment-link" href={question.attachment} target="_blank" rel="noreferrer">
              📎 View attached file
            </a>
          ) : null}
        </div>

        {isTheoryQuestion ? (
          <div className="question-theory-answer">
            <textarea
              className={`theory-answer-box theory-answer-${question.question_type}`}
              rows={question.question_type === "short_answer" ? 3 : question.question_type === "paragraph" ? 8 : 14}
              value={localAnswer || ""}
              onChange={handleTextAnswerChange}
              onBlur={handleTextAnswerBlur}
              placeholder="Type your answer here..."
            />
          </div>
        ) : (
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
        )}

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
        <button className="btn-previous" onClick={() => { flushTheoryAnswer(); onPrevious(); }} disabled={!canGoPrevious}>
          Previous
        </button>
        <button className="btn-save-next" onClick={() => { flushTheoryAnswer(); onNext(); }} disabled={!canGoNext}>
          Save & Next
        </button>
        <button className="btn-submit-exam inline" onClick={() => { flushTheoryAnswer(); onSubmit(); }} disabled={submitting}>
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
      {openImage ? (
        <div className="question-image-modal" role="dialog" aria-modal="true" aria-label={openImage.alt}>
          <button type="button" className="question-image-modal-close" onClick={() => setOpenImage(null)}>
            Close
          </button>
          <img src={openImage.src} alt={openImage.alt} />
        </div>
      ) : null}
    </div>
  );
};

export default QuestionDisplay;
