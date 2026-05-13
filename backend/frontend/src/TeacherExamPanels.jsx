import { useCallback, useEffect, useMemo, useState } from "react";
import { formatDate, MetricCard, requestJson } from "./AppShared";
export function TeacherExamManager({
  questionTemplates = [],
  pendingSubmissions = [],
  classes = [],
  onCreateQuestion,
  onGradeSubmission,
}) {
  const [questionForm, setQuestionForm] = useState({
    title: "",
    description: "",
    classId: "",
    dueDate: "",
    maxScore: "100",
  });
  const [questionFeedback, setQuestionFeedback] = useState("");
  const [isSubmittingQuestion, setIsSubmittingQuestion] = useState(false);
  const [gradingStatus, setGradingStatus] = useState({});

  const handleQuestionSubmit = async (event) => {
    event.preventDefault();
    setQuestionFeedback("");
    if (!questionForm.title.trim() || !questionForm.classId) {
      setQuestionFeedback("Provide a title and select a class.");
      return;
    }
    setIsSubmittingQuestion(true);
    try {
      await onCreateQuestion({
        title: questionForm.title.trim(),
        description: questionForm.description.trim(),
        class_id: questionForm.classId,
        due_date: questionForm.dueDate || undefined,
        max_score: Number(questionForm.maxScore) || 0,
      });
      setQuestionFeedback("Question added.");
      setQuestionForm({ title: "", description: "", classId: "", dueDate: "", maxScore: "100" });
    } catch (submitError) {
      setQuestionFeedback(submitError.message || "Could not save the question.");
    } finally {
      setIsSubmittingQuestion(false);
    }
  };

  const handleGrade = async (submissionId, payload) => {
    setGradingStatus((prev) => ({ ...prev, [submissionId]: { busy: true } }));
    try {
      await onGradeSubmission(submissionId, payload);
      setGradingStatus((prev) => ({ ...prev, [submissionId]: { busy: false, success: true } }));
    } catch (gradeError) {
      setGradingStatus((prev) => ({
        ...prev,
        [submissionId]: {
          busy: false,
          error: gradeError.message || "Could not save grade.",
        },
      }));
    }
  };

  return (
    <article className="app-panel exam-manager">
      <h3>Exam question builder</h3>
      <form className="panel-form" onSubmit={handleQuestionSubmit}>
        <div className="panel-form-grid">
          <label className="panel-field">
            Title
            <input
              value={questionForm.title}
              onChange={(event) => setQuestionForm((prev) => ({ ...prev, title: event.target.value }))}
            />
          </label>
          <label className="panel-field">
            Class
            <select
              value={questionForm.classId}
              onChange={(event) => setQuestionForm((prev) => ({ ...prev, classId: event.target.value }))}
            >
              <option value="">Select class</option>
              {classes.map((item) => (
              <option key={item.id} value={item.id}>
                  {item.label || item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            Due date
            <input
              type="date"
              value={questionForm.dueDate}
              onChange={(event) => setQuestionForm((prev) => ({ ...prev, dueDate: event.target.value }))}
            />
          </label>
          <label className="panel-field">
            Max score
            <input
              type="number"
              min="0"
              value={questionForm.maxScore}
              onChange={(event) => setQuestionForm((prev) => ({ ...prev, maxScore: event.target.value }))}
            />
          </label>
          <label className="panel-field full">
            Description
            <textarea
              value={questionForm.description}
              onChange={(event) => setQuestionForm((prev) => ({ ...prev, description: event.target.value }))}
            />
          </label>
        </div>
        {questionFeedback ? <p className="form-feedback success">{questionFeedback}</p> : null}
        <div className="panel-form-actions">
          <button type="submit" disabled={isSubmittingQuestion}>
            {isSubmittingQuestion ? "Saving..." : "Save question"}
          </button>
        </div>
      </form>
      <section className="panel-list">
        <h4>Question templates</h4>
        {questionTemplates.length === 0 ? (
          <p className="panel-empty">No questions yet.</p>
        ) : (
          questionTemplates.map((item) => (
            <div key={item.id} className="message-item">
              <div className="message-head">
                <p>{item.title}</p>
                <small>{formatDate(item.created_at)}</small>
              </div>
              <span className="message-meta">
                {item.class_name} • {item.difficulty || "Standard"} • {item.max_score ?? "-"} pts
              </span>
              <p className="message-body">{item.description}</p>
            </div>
          ))
        )}
      </section>
      <section className="panel-list">
        <h4>Mark submissions</h4>
        {pendingSubmissions.length === 0 ? (
          <p className="panel-empty">No submissions awaiting review.</p>
        ) : (
          pendingSubmissions.map((submission) => (
            <div key={submission.id} className="message-item">
              <div className="message-head">
                <p>
                  {submission.student_name} • {submission.exam_title || submission.question_title}
                </p>
                <small>{formatDate(submission.submitted_at)}</small>
              </div>
              <span className="message-meta">
                Class: {submission.class_name} • {submission.status || "Pending"}
              </span>
              <p className="message-body">{submission.answer_preview || submission.answer_body}</p>
              <form
                className="panel-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const score = Number(event.target.score.value);
                  const comment = event.target.comment.value.trim();
                  handleGrade(submission.id, { score, comment });
                }}
              >
                <div className="panel-form-grid">
                  <label className="panel-field">
                    Score
                    <input name="score" type="number" min="0" defaultValue={submission.score ?? ""} />
                  </label>
                  <label className="panel-field full">
                    Feedback
                    <textarea name="comment" defaultValue={submission.feedback || ""} />
                  </label>
                </div>
                {gradingStatus[submission.id]?.error ? (
                  <p className="form-feedback error">{gradingStatus[submission.id].error}</p>
                ) : null}
                {gradingStatus[submission.id]?.success ? (
                  <p className="form-feedback success">Score saved.</p>
                ) : null}
                <div className="panel-form-actions">
                  <button type="submit" enabled={gradingStatus[submission.id]?.busy}>
                    {gradingStatus[submission.id]?.busy ? "Saving..." : "Save score"}
                  </button>
                </div>
              </form>
            </div>
          ))
        )}
      </section>
    </article>
  );
}

export function TeacherExamBuilder({
  session,
  classOptions = [],
  subjectOptions = [],
  teacherName = "",
  initialExam = null,
  onCreateExam,
  onUpdateExam,
  onBackToList,
}) {
  const [activeSection, setActiveSection] = useState("details");
  const [form, setForm] = useState({
    title: "Mid Term Examination",
    code: "",
    description: "",
    classId: "",
    subjectId: "",
    examDate: "",
    startTime: "10:00",
    endTime: "12:00",
    duration: "120",
    instructions: "1. Read all questions carefully before answering.\n2. All questions are compulsory.\n3. Do not refresh or close the browser during the exam.\n4. Submit the exam before the time is over.",
    randomizeQuestions: true,
    showResults: false,
    publishNow: false,
  });
  const [sections, setSections] = useState([{ id: 1, title: "Section A", marks: "50" }]);
  const [questions, setQuestions] = useState([
    { id: 1, text: "", marks: "1", options: ["", "", "", ""], correctIndex: 0, explanation: "" },
  ]);
  const [bankQuestions, setBankQuestions] = useState([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [bankError, setBankError] = useState("");
  const [selectedBankQuestionIds, setSelectedBankQuestionIds] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const isEditing = Boolean(initialExam?.id);
  const selectedClass = classOptions.find((item) => String(item.id) === String(form.classId));
  const selectedSubject = subjectOptions.find((item) => String(item.id) === String(form.subjectId));
  const builderSections = [
    ["details", "Exam Details"],
    ["sections", "Sections"],
    ["questions", "Questions"],
    ["settings", "Settings"],
    ["review", "Review"],
  ];

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }));
  const dateValue = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
  };
  const timeValue = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  };
  const makeDateTime = (dateValue, timeValue) => {
    if (!dateValue || !timeValue) return "";
    const date = new Date(`${dateValue}T${timeValue}`);
    return Number.isNaN(date.getTime()) ? "" : date.toISOString();
  };
  const normalizeBankQuestion = (item) => {
    const options = [...(item.options || [])];
    while (options.length < 4) {
      options.push("");
    }
    const correctIndex = Math.max(0, options.findIndex((option) => option === item.correct_answer));
    return {
      id: `bank-${item.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      cbtBankQuestionId: item.id,
      sourceLabel: item.bank_name || "CBT question bank",
      text: item.text || "",
      marks: String(item.points || 1),
      options,
      correctIndex,
      explanation: item.explanation || "",
    };
  };
  const calculatedDuration = useMemo(() => {
    const start = form.examDate && form.startTime ? new Date(`${form.examDate}T${form.startTime}`) : null;
    const end = form.examDate && form.endTime ? new Date(`${form.examDate}T${form.endTime}`) : null;
    if (!start || !end || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return 0;
    }
    const minutes = Math.floor((end.getTime() - start.getTime()) / 60000);
    return minutes > 0 ? minutes : 0;
  }, [form.endTime, form.examDate, form.startTime]);

  const loadBankQuestions = useCallback(async () => {
    if (!session) {
      return;
    }
    setBankLoading(true);
    setBankError("");
    try {
      const params = new URLSearchParams();
      if (form.subjectId) {
        params.set("subject_id", form.subjectId);
      }
      params.set("limit", "200");
      const result = await requestJson(session, "GET", `/api/app/exams/question-bank/?${params.toString()}`);
      setBankQuestions(result.questions || []);
    } catch (loadError) {
      setBankError(loadError.message || "Could not load CBT question bank.");
    } finally {
      setBankLoading(false);
    }
  }, [form.subjectId, session]);

  useEffect(() => {
    loadBankQuestions();
  }, [loadBankQuestions]);

  useEffect(() => {
    if (!initialExam) {
      return;
    }
    setForm({
      title: initialExam.title || "",
      code: initialExam.code || "",
      description: initialExam.description || "",
      classId: initialExam.class_id || "",
      subjectId: initialExam.subject_id || "",
      examDate: dateValue(initialExam.start_date),
      startTime: timeValue(initialExam.start_date),
      endTime: timeValue(initialExam.end_date),
      duration: String(initialExam.duration_minutes || 60),
      instructions: initialExam.instructions || "",
      randomizeQuestions: Boolean(initialExam.shuffle_questions),
      showResults: Boolean(initialExam.show_results_immediately),
      publishNow: Boolean(initialExam.is_published),
    });
    const loadedQuestions = (initialExam.questions || []).map((question, index) => {
      const options = [...(question.options || [])];
      while (options.length < 4) {
        options.push("");
      }
      const correctIndex = Math.max(0, options.findIndex((option) => option === question.correct_answer));
      return {
        id: question.id || index + 1,
        text: question.text || "",
        marks: String(question.points || 1),
        options,
        correctIndex,
        explanation: question.explanation || "",
        cbtBankQuestionId: question.source_question_id || null,
        sourceLabel: question.source_question_id ? "CBT question bank" : "",
      };
    });
    setQuestions(
      loadedQuestions.length
        ? loadedQuestions
        : [{ id: 1, text: "", marks: "1", options: ["", "", "", ""], correctIndex: 0, explanation: "" }]
    );
    setSections([{ id: 1, title: "Section A", marks: String(initialExam.duration_minutes || 50) }]);
    setActiveSection("details");
    setFeedback("");
    setError("");
  }, [initialExam]);

  const handleSaveExam = async () => {
    setError("");
    setFeedback("");
    if (!form.title.trim() || !form.examDate || !form.startTime || !form.endTime) {
      setError("Exam title, date, start time, and end time are required.");
      setActiveSection("details");
      return;
    }
    if (calculatedDuration <= 0) {
      setError("Exam end time must be after the start time.");
      setActiveSection("details");
      return;
    }
    const preparedQuestions = questions.map((question) => {
      const options = (question.options || []).map((option) => option.trim()).filter(Boolean);
      return {
        text: question.text.trim(),
        points: Number(question.marks) || 1,
        options,
        correct_answer: (question.options || [])[Number(question.correctIndex)]?.trim() || "",
        explanation: question.explanation?.trim() || "",
        source_question_id: question.cbtBankQuestionId || undefined,
      };
    });
    const invalidQuestion = preparedQuestions.find(
      (question) => !question.text || question.options.length < 2 || !question.correct_answer
    );
    if (invalidQuestion) {
      setError("Each CBT question needs text, at least two options, and a selected correct answer.");
      setActiveSection("questions");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        class_id: form.classId || "",
        subject_id: form.subjectId || "",
        start_date: makeDateTime(form.examDate, form.startTime),
        end_date: makeDateTime(form.examDate, form.endTime),
        duration_minutes: calculatedDuration,
        assessment_type: "exam",
        instructions: form.instructions,
        shuffle_questions: form.randomizeQuestions,
        show_results_immediately: false,
        is_published: form.publishNow,
        questions: preparedQuestions,
      };
      const result = isEditing ? await onUpdateExam(initialExam.id, payload) : await onCreateExam(payload);
      setFeedback(result?.message || "Exam saved.");
    } catch (saveError) {
      setError(saveError.message || "Could not save exam.");
    } finally {
      setSaving(false);
    }
  };

  const addSection = () => {
    setSections((previous) => [...previous, { id: Date.now(), title: `Section ${String.fromCharCode(65 + previous.length)}`, marks: "10" }]);
  };

  const addQuestion = () => {
    setQuestions((previous) => [
      ...previous,
      { id: Date.now(), text: "", marks: "1", options: ["", "", "", ""], correctIndex: 0, explanation: "" },
    ]);
  };

  const toggleBankQuestion = (questionId) => {
    setSelectedBankQuestionIds((previous) =>
      previous.includes(questionId) ? previous.filter((id) => id !== questionId) : [...previous, questionId]
    );
  };

  const addSelectedBankQuestions = () => {
    const existingBankIds = new Set(questions.map((item) => item.cbtBankQuestionId).filter(Boolean));
    const selectedQuestions = bankQuestions.filter(
      (item) => selectedBankQuestionIds.includes(item.id) && !existingBankIds.has(item.id)
    );
    if (!selectedQuestions.length) {
      setError("Select at least one new CBT bank question to add.");
      setActiveSection("questions");
      return;
    }
    setQuestions((previous) => [...previous, ...selectedQuestions.map(normalizeBankQuestion)]);
    setSelectedBankQuestionIds([]);
    setError("");
    setFeedback(`${selectedQuestions.length} CBT bank question${selectedQuestions.length === 1 ? "" : "s"} added.`);
  };

  const updateQuestion = (questionId, patch) => {
    setQuestions((previous) => previous.map((item) => (item.id === questionId ? { ...item, ...patch } : item)));
  };

  const updateQuestionOption = (questionId, optionIndex, value) => {
    setQuestions((previous) =>
      previous.map((item) => {
        if (item.id !== questionId) return item;
        const options = [...(item.options || ["", "", "", ""])];
        options[optionIndex] = value;
        return { ...item, options };
      })
    );
  };

  return (
    <section className={`exam-builder-shell ${isEditing ? "exam-builder-editing" : ""}`}>
      <aside className="exam-builder-sidebar">
        <div className="exam-builder-brand">
          <div className="exam-builder-mark">E</div>
          <strong>Exam Builder</strong>
        </div>
        <nav aria-label="Exam builder sections">
          {builderSections.map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={activeSection === key ? "active" : ""}
              onClick={() => setActiveSection(key)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="exam-builder-user">
          <div className="avatar">{teacherName ? teacherName.slice(0, 2).toUpperCase() : "T"}</div>
          <div>
            <p>{teacherName || "Teacher"}</p>
            <span>Teacher</span>
          </div>
        </div>
      </aside>

      <main className="exam-builder-main">
        <div className="exam-builder-top">
          <div>
            <h2 id={isEditing ? "edit-exam-title" : undefined}>{isEditing ? "Edit Exam" : "Create New Exam"}</h2>
            <p>{isEditing ? `Exams / ${form.title || "Edit Exam"}` : "Exams / Create New Exam"}</p>
          </div>
          <div className="exam-builder-actions">
            {isEditing ? (
              <button type="button" className="table-action" onClick={onBackToList}>
                Back to Past Exams
              </button>
            ) : null}
            <button type="button" className="table-action" onClick={() => setActiveSection("review")}>
              Preview Exam
            </button>
            <button type="button" onClick={handleSaveExam} disabled={saving}>
              {saving ? "Saving..." : "Save Exam"}
            </button>
          </div>
        </div>

        {(feedback || error) ? (
          <div className={`form-feedback ${error ? "error" : "success"}`}>
            {error || feedback}
          </div>
        ) : null}

        <article className="exam-builder-card">
          <div className="exam-builder-tabs">
            {builderSections.map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={activeSection === key ? "active" : ""}
                onClick={() => setActiveSection(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {activeSection === "details" ? (
            <div className="exam-builder-form">
              <label className="panel-field">Exam Title<input value={form.title} onChange={(event) => setField("title", event.target.value)} /></label>
              <label className="panel-field">Exam Code<input value={form.code} onChange={(event) => setField("code", event.target.value)} placeholder="Optional" /></label>
              <label className="panel-field full">Description<textarea value={form.description} onChange={(event) => setField("description", event.target.value)} rows={4} /></label>
              <label className="panel-field">Class / Course<select value={form.classId} onChange={(event) => setField("classId", event.target.value)}><option value="">All classes</option>{classOptions.map((item) => <option key={item.id} value={item.id}>{item.label || item.name}</option>)}</select></label>
              <label className="panel-field">Subject<select value={form.subjectId} onChange={(event) => setField("subjectId", event.target.value)}><option value="">General</option>{subjectOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label className="panel-field">Teacher<input value={teacherName || "Teacher"} readOnly /></label>
              <label className="panel-field">Exam Date<input type="date" value={form.examDate} onChange={(event) => setField("examDate", event.target.value)} /></label>
              <label className="panel-field">Start Time<input type="time" value={form.startTime} onChange={(event) => setField("startTime", event.target.value)} /></label>
              <label className="panel-field">End Time<input type="time" value={form.endTime} onChange={(event) => setField("endTime", event.target.value)} /></label>
              <label className="panel-field">Duration<input value={calculatedDuration ? `${calculatedDuration} minutes` : "Set start and end time"} readOnly /></label>
              <label className="panel-field full">Instructions for Students<textarea value={form.instructions} onChange={(event) => setField("instructions", event.target.value)} rows={6} /></label>
            </div>
          ) : null}

          {activeSection === "sections" ? (
            <div className="exam-builder-list">
              {sections.map((section, index) => (
                <div key={section.id} className="exam-builder-row">
                  <label className="panel-field">Section Title<input value={section.title} onChange={(event) => setSections((previous) => previous.map((item) => item.id === section.id ? { ...item, title: event.target.value } : item))} /></label>
                  <label className="panel-field">Marks<input type="number" value={section.marks} onChange={(event) => setSections((previous) => previous.map((item) => item.id === section.id ? { ...item, marks: event.target.value } : item))} /></label>
                  <span>#{index + 1}</span>
                </div>
              ))}
              <button type="button" className="table-action" onClick={addSection}>Add section</button>
            </div>
          ) : null}

          {activeSection === "questions" ? (
            <div className="exam-builder-list">
              <div className="cbt-bank-picker">
                <div className="cbt-bank-picker-head">
                  <div>
                    <h3>CBT question bank</h3>
                    <p>Import preloaded CBT questions for this exam. Quiz questions are kept separate.</p>
                  </div>
                  <div className="table-actions-inline">
                    <button type="button" className="table-action" onClick={loadBankQuestions} disabled={bankLoading}>
                      {bankLoading ? "Loading..." : "Refresh bank"}
                    </button>
                    <button
                      type="button"
                      className="table-action active"
                      onClick={addSelectedBankQuestions}
                      disabled={!selectedBankQuestionIds.length}
                    >
                      Add selected
                    </button>
                  </div>
                </div>
                {bankError ? <p className="form-feedback error">{bankError}</p> : null}
                {bankQuestions.length === 0 ? (
                  <p className="panel-empty">
                    {bankLoading ? "Loading CBT bank questions..." : "No CBT bank questions found for this subject."}
                  </p>
                ) : (
                  <div className="cbt-bank-question-list">
                    {bankQuestions.slice(0, 12).map((item) => {
                      const alreadyAdded = questions.some((question) => question.cbtBankQuestionId === item.id);
                      return (
                        <label key={item.id} className={`cbt-bank-question ${alreadyAdded ? "disabled" : ""}`}>
                          <input
                            type="checkbox"
                            checked={selectedBankQuestionIds.includes(item.id)}
                            disabled={alreadyAdded}
                            onChange={() => toggleBankQuestion(item.id)}
                          />
                          <span>
                            <strong>{item.text}</strong>
                            <small>
                              {item.bank_name || "CBT bank"} · {item.subject_name || "General"} · {item.points || 1} mark
                              {alreadyAdded ? " · already added" : ""}
                            </small>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
              {questions.map((question, index) => (
                <div key={question.id} className="exam-builder-question">
                  {question.sourceLabel ? <div className="cbt-question-source">From {question.sourceLabel}</div> : null}
                  <div className="exam-builder-row">
                    <label className="panel-field full">Question {index + 1}<textarea value={question.text} onChange={(event) => updateQuestion(question.id, { text: event.target.value })} rows={3} /></label>
                    <label className="panel-field">Type<input value="Objective MCQ" readOnly /></label>
                    <label className="panel-field">Marks<input type="number" min="1" value={question.marks} onChange={(event) => updateQuestion(question.id, { marks: event.target.value })} /></label>
                  </div>
                  <div className="cbt-option-grid">
                    {(question.options || []).map((option, optionIndex) => (
                      <label key={optionIndex} className="panel-field">
                        Option {String.fromCharCode(65 + optionIndex)}
                        <input
                          value={option}
                          onChange={(event) => updateQuestionOption(question.id, optionIndex, event.target.value)}
                          placeholder={`Answer option ${String.fromCharCode(65 + optionIndex)}`}
                        />
                      </label>
                    ))}
                  </div>
                  <div className="exam-builder-row">
                    <label className="panel-field">
                      Correct answer
                      <select
                        value={question.correctIndex}
                        onChange={(event) => updateQuestion(question.id, { correctIndex: Number(event.target.value) })}
                      >
                        {(question.options || []).map((option, optionIndex) => (
                          <option key={optionIndex} value={optionIndex}>
                            {String.fromCharCode(65 + optionIndex)} {option ? `- ${option.slice(0, 40)}` : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="panel-field full">
                      Teacher note / explanation
                      <textarea
                        value={question.explanation}
                        onChange={(event) => updateQuestion(question.id, { explanation: event.target.value })}
                        rows={2}
                        placeholder="Optional review note for teacher records"
                      />
                    </label>
                  </div>
                </div>
              ))}
              <button type="button" className="table-action" onClick={addQuestion}>Add question</button>
            </div>
          ) : null}

          {activeSection === "settings" ? (
            <div className="exam-builder-settings">
              <label className="remember-row"><input type="checkbox" checked={form.randomizeQuestions} onChange={(event) => setField("randomizeQuestions", event.target.checked)} /> Randomize questions</label>
              <label className="remember-row"><input type="checkbox" checked={form.showResults} disabled /> Send results to teacher only after submission</label>
              <label className="remember-row"><input type="checkbox" checked={form.publishNow} onChange={(event) => setField("publishNow", event.target.checked)} /> Publish immediately</label>
            </div>
          ) : null}

          {activeSection === "review" ? (
            <div className="exam-review-grid">
              <MetricCard label="Exam" value={form.title || "Untitled"} trend={form.code || "No code"} />
              <MetricCard label="Class" value={selectedClass?.label || selectedClass?.name || "All classes"} trend={selectedSubject?.name || "General"} />
              <MetricCard label="Duration" value={`${calculatedDuration || 0} mins`} trend={`${form.startTime || "-"} to ${form.endTime || "-"}`} />
              <MetricCard label="Questions" value={questions.length} trend={`${sections.length} sections`} />
              <article className="app-panel full">
                <h3>Instructions</h3>
                <p className="message-body">{form.instructions}</p>
              </article>
            </div>
          ) : null}
        </article>
      </main>
    </section>
  );
}

export function TeacherPastExamsPanel({ session, onEditExam, loadingExamId = "", editError = "" }) {
  const [exams, setExams] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");

  const loadExams = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/exams/");
      setExams(result.exams || []);
      setSummary(result.summary || {});
    } catch (loadError) {
      setError(loadError.message || "Could not load exams.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  const now = Date.now();
  const isPastExam = (exam) => {
    const endValue = exam.end_date || exam.start_date;
    if (!endValue) return false;
    const examTime = new Date(endValue).getTime();
    return Number.isNaN(examTime) ? false : examTime < now;
  };
  const isUpcomingExam = (exam) => {
    const startValue = exam.start_date || exam.end_date;
    if (!startValue) return false;
    const examTime = new Date(startValue).getTime();
    return Number.isNaN(examTime) ? false : examTime >= now;
  };
  const pastExams = exams.filter(isPastExam);
  const upcomingExams = exams.filter(isUpcomingExam);
  const visibleExams =
    filter === "past"
      ? pastExams
      : filter === "upcoming"
        ? upcomingExams
        : exams;

  return (
    <section className="app-panel teacher-past-exams-panel">
      <div className="student-panel-head">
        <div>
          <h3>My Exams</h3>
          <p className="student-panel-sub">View exams you have set, including past exams, and edit their setup when needed.</p>
        </div>
        <button type="button" className="table-action" onClick={loadExams} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="exam-review-grid">
        <MetricCard label="Total Exams" value={summary.total_exams ?? exams.length} trend="Teacher-created records" />
        <MetricCard label="Published" value={summary.published_exams ?? 0} trend="Visible to students" />
        <MetricCard label="Past Exams" value={pastExams.length} trend="Closed exam windows" />
        <MetricCard label="Upcoming" value={upcomingExams.length} trend="Scheduled exam windows" />
      </div>

      {error ? <p className="form-feedback error">{error}</p> : null}
      {editError ? <p className="form-feedback error">{editError}</p> : null}

      <div className="segmented-control inbox-filter">
        <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
          All ({exams.length})
        </button>
        <button type="button" className={filter === "past" ? "active" : ""} onClick={() => setFilter("past")}>
          Past ({pastExams.length})
        </button>
        <button type="button" className={filter === "upcoming" ? "active" : ""} onClick={() => setFilter("upcoming")}>
          Upcoming ({upcomingExams.length})
        </button>
      </div>

      {loading ? (
        <p className="panel-empty">Loading exams...</p>
      ) : visibleExams.length === 0 ? (
        <p className="panel-empty">No exams found for this filter.</p>
      ) : (
        <div className="table-scroll">
          <table className="student-table">
            <thead>
              <tr>
                <th>Exam</th>
                <th>Class</th>
                <th>Subject</th>
                <th>Schedule</th>
                <th>Window</th>
                <th>Status</th>
                <th>Submissions</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleExams.map((exam) => {
                const closed = isPastExam(exam);
                const upcoming = isUpcomingExam(exam);
                return (
                <tr key={exam.id}>
                  <td>{exam.title || "Untitled exam"}</td>
                  <td>{exam.class_name || "All classes"}</td>
                  <td>{exam.subject || "General"}</td>
                  <td>{formatDate(exam.end_date || exam.start_date)}</td>
                  <td>
                    <span className={`student-status-pill status-${closed ? "absent" : upcoming ? "present" : "unmarked"}`}>
                      {closed ? "Past" : upcoming ? "Upcoming" : "Open"}
                    </span>
                  </td>
                  <td>
                    <span className={`student-status-pill status-${exam.is_published ? "present" : "unmarked"}`}>
                      {exam.is_published ? "Published" : "Draft"}
                    </span>
                  </td>
                  <td>{exam.submissions ?? 0}</td>
                  <td>
                    <button
                      type="button"
                      className="table-action"
                      onClick={() => onEditExam?.(exam.id)}
                      disabled={String(loadingExamId) === String(exam.id)}
                    >
                      {String(loadingExamId) === String(exam.id) ? "Opening..." : "View / Edit"}
                    </button>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function ClassMessageComposer({ classOptions = [], onSend }) {
  const [form, setForm] = useState({ classId: "", subject: "", body: "" });
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (classOptions.length === 0) {
      return;
    }
    setForm((previous) => ({
      ...previous,
      classId: previous.classId || classOptions[0].id,
    }));
  }, [classOptions]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.classId) {
      setError("Select a class before sending.");
  return;
    }
    if (!form.body.trim()) {
      setError("Write a message before sending.");
      return;
    }
    setError("");
    setFeedback("");
    setIsSending(true);
    try {
      const result = await onSend({
        class_id: form.classId,
        subject: form.subject.trim(),
        body: form.body.trim(),
      });
      setFeedback(result?.message || "Message sent to the class.");
      setForm((prev) => ({ ...prev, subject: "", body: "" }));
    } catch (sendError) {
      setError(sendError.message || "Could not send class message.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <article className="app-panel class-message-panel">
      <h3>Message students in a class</h3>
      <form className="panel-form" onSubmit={handleSubmit}>
        <div className="panel-form-grid">
          <label className="panel-field">
            Class
            <select
              value={form.classId}
              onChange={(event) => setForm((prev) => ({ ...prev, classId: event.target.value }))}
            >
              <option value="">Select class</option>
              {classOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label || item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            Subject
            <input
              value={form.subject}
              onChange={(event) => setForm((prev) => ({ ...prev, subject: event.target.value }))}
              placeholder="Optional subject"
            />
          </label>
          <label className="panel-field full">
            Message
            <textarea
              value={form.body}
              onChange={(event) => setForm((prev) => ({ ...prev, body: event.target.value }))}
              placeholder="Write your announcement for this class"
            />
          </label>
        </div>
        {error ? <p className="form-feedback error">{error}</p> : null}
        {feedback ? <p className="form-feedback success">{feedback}</p> : null}
        <div className="panel-form-actions">
          <button type="submit" disabled={isSending || !classOptions.length}>
            {isSending ? "Sending…" : "Send to class"}
          </button>
        </div>
      </form>
    </article>
  );
}


