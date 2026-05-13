import React from "react";

const SubmitModal = ({ totalQuestions, answeredQuestions, onConfirm, onCancel }) => {
  return (
    <div className="modal-overlay">
      <div className="modal-content submit-modal">
        <div className="modal-header">
          <h2>Submit Test?</h2>
          <button className="modal-close" onClick={onCancel}>×</button>
        </div>

        <div className="modal-body">
          <p>Are you sure you want to submit this exam?</p>
          
          <div className="submit-summary">
            <div className="summary-item">
              <span className="summary-label">Total Questions:</span>
              <span className="summary-value">{totalQuestions}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Answered:</span>
              <span className="summary-value">{answeredQuestions}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Not Answered:</span>
              <span className="summary-value">{totalQuestions - answeredQuestions}</span>
            </div>
          </div>

          {answeredQuestions < totalQuestions && (
            <div className="warning-box">
              <p>
                <strong>Warning:</strong> You have not answered all questions.
                You will still be able to submit.
              </p>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-cancel" onClick={onCancel}>
            No
          </button>
          <button className="btn-confirm" onClick={onConfirm}>
            Yes
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubmitModal;
