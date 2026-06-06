import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatDate, MetricCard, requestJson } from "./AppShared";

const IMPORT_SAMPLE = `1. What is the capital of France?
A. Paris
B. Lagos
C. Rome
D. Madrid
Answer: A`;

const TEXT_IMPORT_EXTENSIONS = new Set(["csv", "tsv", "txt", "tdx", "json", "qti", "xml"]);
const WORD_IMPORT_EXTENSIONS = new Set(["docx"]);

const bytesStartWithZipHeader = (bytes) => bytes?.[0] === 0x50 && bytes?.[1] === 0x4b;

const decodeTextBytes = (bytes) => new TextDecoder("utf-8").decode(bytes);

const looksReadableText = (text) => {
  const value = String(text || "").replace(/\s/g, "");
  if (!value) return false;
  const sample = value.slice(0, 4000);
  const replacementCount = (sample.match(/\uFFFD/g) || []).length;
  const controlCount = (sample.match(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g) || []).length;
  return (replacementCount + controlCount) / sample.length < 0.08;
};

const decodeReadableText = (bytes) => {
  const text = decodeTextBytes(bytes).replace(/\u0000/g, "");
  return looksReadableText(text) ? text : "";
};

const inflateBytes = async (bytes, format) => {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("Compressed TDX files are not supported in this browser.");
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(format));
  return new Uint8Array(await new Response(stream).arrayBuffer());
};

const tryDecompressText = async (bytes) => {
  const candidates = [bytes];
  if (bytes.length > 2) {
    candidates.push(bytes.slice(2));
  }
  for (const candidate of candidates) {
    for (const format of ["gzip", "deflate", "deflate-raw"]) {
      try {
        const inflated = await inflateBytes(candidate, format);
        const text = decodeReadableText(inflated);
        if (text) return text;
      } catch {
        // Try the next container/compression shape.
      }
    }
  }
  return "";
};

const getFileExtension = (fileName = "") => {
  const match = String(fileName).toLowerCase().match(/\.([a-z0-9]+)$/);
  return match ? match[1] : "";
};

const readZipEntryBytes = async (arrayBuffer, targetName) => {
  const view = new DataView(arrayBuffer);
  const bytes = new Uint8Array(arrayBuffer);
  let eocdOffset = -1;
  for (let offset = bytes.length - 22; offset >= 0; offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) {
    throw new Error("This DOCX file could not be read.");
  }

  const entryCount = view.getUint16(eocdOffset + 10, true);
  const centralDirectoryOffset = view.getUint32(eocdOffset + 16, true);
  let offset = centralDirectoryOffset;

  for (let index = 0; index < entryCount; index += 1) {
    if (view.getUint32(offset, true) !== 0x02014b50) {
      break;
    }
    const compressionMethod = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const fileNameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localHeaderOffset = view.getUint32(offset + 42, true);
    const fileName = decodeTextBytes(bytes.slice(offset + 46, offset + 46 + fileNameLength));

    if (fileName === targetName) {
      if (view.getUint32(localHeaderOffset, true) !== 0x04034b50) {
        throw new Error("This DOCX file has an invalid document entry.");
      }
      const localNameLength = view.getUint16(localHeaderOffset + 26, true);
      const localExtraLength = view.getUint16(localHeaderOffset + 28, true);
      const dataStart = localHeaderOffset + 30 + localNameLength + localExtraLength;
      const compressedBytes = bytes.slice(dataStart, dataStart + compressedSize);
      if (compressionMethod === 0) {
        return compressedBytes;
      }
      if (compressionMethod !== 8 || typeof DecompressionStream === "undefined") {
        throw new Error("This DOCX compression format is not supported in this browser.");
      }
      const stream = new Blob([compressedBytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    }

    offset += 46 + fileNameLength + extraLength + commentLength;
  }

  throw new Error("This DOCX file does not contain a readable Word document.");
};

const docxXmlToText = (xmlText) => {
  const documentXml = new DOMParser().parseFromString(xmlText, "application/xml");
  if (documentXml.getElementsByTagName("parsererror").length) {
    throw new Error("The DOCX document XML could not be parsed.");
  }
  const paragraphs = Array.from(documentXml.getElementsByTagNameNS("*", "p"));
  return paragraphs
    .map((paragraph) => {
      const chunks = [];
      Array.from(paragraph.getElementsByTagNameNS("*", "r")).forEach((run) => {
        const verticalAlign = run.getElementsByTagNameNS("*", "vertAlign")[0]?.getAttribute("w:val")
          || run.getElementsByTagNameNS("*", "vertAlign")[0]?.getAttribute("val")
          || "";
        const text = Array.from(run.getElementsByTagNameNS("*", "t")).map((node) => node.textContent || "").join("");
        if (text) {
          if (verticalAlign === "superscript") {
            chunks.push(`<sup>${text}</sup>`);
          } else if (verticalAlign === "subscript") {
            chunks.push(`<sub>${text}</sub>`);
          } else {
            chunks.push(text);
          }
        }
        if (run.getElementsByTagNameNS("*", "tab").length) {
          chunks.push(" ");
        }
        if (run.getElementsByTagNameNS("*", "br").length) {
          chunks.push("\n");
        }
      });
      return chunks.join("").replace(/[ \t]{2,}/g, " ").trim();
    })
    .filter(Boolean)
    .join("\n");
};

const extractDocxText = async (arrayBuffer) => {
  const bytes = new Uint8Array(arrayBuffer);
  if (!bytesStartWithZipHeader(bytes)) {
    throw new Error("This does not look like a valid DOCX file.");
  }
  const documentBytes = await readZipEntryBytes(arrayBuffer, "word/document.xml");
  return docxXmlToText(decodeTextBytes(documentBytes));
};

const readImportFileText = async (file) => {
  const extension = getFileExtension(file.name);
  const arrayBuffer = await file.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  if (WORD_IMPORT_EXTENSIONS.has(extension) || bytesStartWithZipHeader(bytes)) {
    return extractDocxText(arrayBuffer);
  }
  if (extension === "tdx") {
    const text = decodeReadableText(bytes);
    if (text) return text;
    const decompressedText = await tryDecompressText(bytes);
    if (decompressedText) return decompressedText;
    throw new Error("This TDX file is compressed or proprietary and could not be converted to text in the browser.");
  }
  if (TEXT_IMPORT_EXTENSIONS.has(extension) || file.type.startsWith("text/") || !extension) {
    const text = decodeReadableText(bytes);
    if (text) return text;
    const decompressedText = await tryDecompressText(bytes);
    if (decompressedText) return decompressedText;
    throw new Error("This file is not readable as text. Convert it to TXT, CSV, or DOCX and try again.");
  }
  const text = decodeReadableText(bytes);
  if (text) return text;
  const decompressedText = await tryDecompressText(bytes);
  if (decompressedText) return decompressedText;
  throw new Error("This file is not readable as text. Convert it to TXT, CSV, or DOCX and try again.");
};

const splitCsvLine = (line, delimiter = ",") => {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
};

const normalizeAnswerIndex = (answer, options) => {
  const cleaned = String(answer || "").trim();
  if (!cleaned) return 0;
  const upper = cleaned.toUpperCase();
  if (/^[A-Z]$/.test(upper)) {
    const index = upper.charCodeAt(0) - 65;
    return index >= 0 && index < options.length ? index : 0;
  }
  const numeric = Number(cleaned);
  if (Number.isInteger(numeric) && numeric >= 1 && numeric <= options.length) {
    return numeric - 1;
  }
  const exact = options.findIndex((option) => option.trim().toLowerCase() === cleaned.toLowerCase());
  return exact >= 0 ? exact : 0;
};

const buildImportedQuestion = (item, index) => {
  const options = (item.options || []).map((option) => String(option || "").trim()).filter(Boolean);
  while (options.length < 4) {
    options.push("");
  }
  return {
    id: `import-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 7)}`,
    text: String(item.text || item.question || "").trim(),
    marks: String(item.points || item.marks || 1),
    options,
    correctIndex: normalizeAnswerIndex(item.correct_answer ?? item.answer ?? item.correctIndex, options),
    explanation: String(item.explanation || item.note || "").trim(),
    sourceLabel: item.sourceLabel || "Imported file",
  };
};

const parseJsonQuestions = (rawText) => {
  const parsed = JSON.parse(rawText);
  const rows = Array.isArray(parsed) ? parsed : parsed.questions;
  if (!Array.isArray(rows)) {
    throw new Error("JSON must be an array or an object with a questions array.");
  }
  return rows.map((item) => ({
    text: item.text || item.question || item.prompt,
    options: Array.isArray(item.options)
      ? item.options
      : [item.a, item.b, item.c, item.d, item.e].filter((option) => option !== undefined),
    answer: item.answer ?? item.correct_answer ?? item.correct,
    points: item.points || item.marks,
    explanation: item.explanation || item.note,
    sourceLabel: "Imported JSON",
  }));
};

const parseDelimitedQuestions = (rawText) => {
  const lines = rawText.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const delimiter = lines[0].includes("\t") ? "\t" : ",";
  const headers = splitCsvLine(lines[0], delimiter).map((header) => header.trim().toLowerCase());
  const questionIndex = headers.findIndex((header) => ["question", "text", "prompt"].includes(header));
  const answerIndex = headers.findIndex((header) => ["answer", "correct", "correct_answer"].includes(header));
  if (questionIndex < 0 || answerIndex < 0) return [];
  const optionIndexes = headers
    .map((header, index) => ({ header, index }))
    .filter(({ header }) => ["a", "b", "c", "d", "e", "option_a", "option_b", "option_c", "option_d", "option_e"].includes(header));
  const pointsIndex = headers.findIndex((header) => ["points", "marks", "score"].includes(header));
  const explanationIndex = headers.findIndex((header) => ["explanation", "note", "teacher_note"].includes(header));
  return lines.slice(1).map((line) => {
    const cells = splitCsvLine(line, delimiter);
    return {
      text: cells[questionIndex],
      options: optionIndexes.map(({ index }) => cells[index]).filter(Boolean),
      answer: cells[answerIndex],
      points: pointsIndex >= 0 ? cells[pointsIndex] : 1,
      explanation: explanationIndex >= 0 ? cells[explanationIndex] : "",
      sourceLabel: delimiter === "\t" ? "Imported TSV" : "Imported CSV",
    };
  });
};

const isQuestionStarterLine = (line) => {
  const value = String(line || "").trim();
  if (!value) return false;
  if (/^([A-E])[\).:-]\s+/i.test(value)) return false;
  if (/^(answer|correct|correct answer|explanation|note)\s*[:=-]/i.test(value)) return false;
  if (/^\d+[\).]\s+/.test(value)) return true;
  if (/[?؟]$/.test(value)) return true;
  return value.length > 12;
};

const splitQuestionBlocks = (rawText) => {
  const normalizedLines = String(rawText || "")
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const blocks = [];
  let current = [];
  let hasOption = false;
  let hasAnswer = false;

  normalizedLines.forEach((line) => {
    const isOption = /^([A-E])[\).:-]\s+/i.test(line);
    const isAnswer = /^(answer|correct|correct answer)\s*[:=-]\s*(.+)$/i.test(line);
    const startsNewNumbered = /^\d+[\).]\s+/.test(line);
    const startsNewUnnumbered = !isOption && !isAnswer && hasOption && (hasAnswer || isQuestionStarterLine(line));

    if (current.length && (startsNewNumbered || startsNewUnnumbered)) {
      blocks.push(current.join("\n"));
      current = [];
      hasOption = false;
      hasAnswer = false;
    }

    current.push(line);
    if (isOption) hasOption = true;
    if (isAnswer) hasAnswer = true;
  });

  if (current.length) {
    blocks.push(current.join("\n"));
  }
  return blocks;
};

const parseTextQuestions = (rawText) => {
  const paragraphBlocks = rawText
    .replace(/\r/g, "")
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter(Boolean);
  const blocks = paragraphBlocks.length > 1 ? paragraphBlocks.flatMap(splitQuestionBlocks) : splitQuestionBlocks(rawText);
  return blocks.map((block) => {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    const options = [];
    let answer = "";
    let explanation = "";
    const questionLines = [];
    lines.forEach((line) => {
      const optionMatch = line.match(/^([A-E])[\).:-]\s*(.+)$/i);
      const answerMatch = line.match(/^(answer|correct|correct answer)\s*[:=-]\s*(.+)$/i);
      const explanationMatch = line.match(/^(explanation|note)\s*[:=-]\s*(.+)$/i);
      if (answerMatch) {
        answer = answerMatch[2];
      } else if (explanationMatch) {
        explanation = explanationMatch[2];
      } else if (optionMatch) {
        options.push(optionMatch[2].trim());
      } else {
        questionLines.push(line.replace(/^\d+[\).]\s*/, ""));
      }
    });
    return {
      text: questionLines.join(" ").trim(),
      options,
      answer,
      points: 1,
      explanation,
      sourceLabel: "Imported text",
    };
  });
};

const parseImportedQuestions = (rawText) => {
  const text = String(rawText || "").trim();
  if (!text) {
    throw new Error("Paste questions or choose a file before importing.");
  }
  if (/^PK/.test(text) && text.includes("[Content_Types].xml")) {
    throw new Error("This looks like raw DOCX data. Choose the .docx file instead so it can be converted to text.");
  }
  let parsedRows = [];
  if (/^[\[{]/.test(text)) {
    parsedRows = parseJsonQuestions(text);
  } else {
    parsedRows = parseDelimitedQuestions(text);
    if (!parsedRows.length) {
      parsedRows = parseTextQuestions(text);
    }
  }
  const questions = parsedRows.map(buildImportedQuestion).filter((question) => {
    const filledOptions = question.options.filter(Boolean);
    return question.text.length >= 3 && filledOptions.length >= 2 && filledOptions[question.correctIndex];
  });
  if (!questions.length) {
    throw new Error("No valid MCQ questions found. Check the format and correct answer labels.");
  }
  return questions;
};

const isBlankBuilderQuestion = (question) =>
  !String(question?.text || "").trim() &&
  !(question?.options || []).some((option) => String(option || "").trim()) &&
  !String(question?.explanation || "").trim();

const newBuilderQuestion = () => ({
  id: Date.now(),
  text: "",
  marks: "1",
  options: ["", "", "", ""],
  correctIndex: 0,
  explanation: "",
  groupKey: "",
  group: { title: "", group_type: "passage", passage_text: "", imagePreview: "" },
  questionImagePreview: "",
});

const filePreviewUrl = (file) => (file ? URL.createObjectURL(file) : "");
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
    { ...newBuilderQuestion(), id: 1 },
  ]);
  const [bankQuestions, setBankQuestions] = useState([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [bankError, setBankError] = useState("");
  const [selectedBankQuestionIds, setSelectedBankQuestionIds] = useState([]);
  const [importText, setImportText] = useState("");
  const [importFeedback, setImportFeedback] = useState("");
  const [importError, setImportError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [publishedPin, setPublishedPin] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState("");
  const isEditing = Boolean(initialExam?.id);
  const selectedClass = classOptions.find((item) => String(item.id) === String(form.classId));
  const selectedSubject = subjectOptions.find((item) => String(item.id) === String(form.subjectId));
  const canPublishExam = ["school_admin", "principal", "super_admin"].includes(session?.user?.role);
  const canUseCbtQuestionBank = session?.user?.role !== "teacher";
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
        groupKey: item.group?.id ? `bank-group-${item.group.id}` : "",
        group: item.group
          ? { ...item.group, imagePreview: item.group.image || "" }
          : { title: "", group_type: "passage", passage_text: "", imagePreview: "" },
        questionImagePreview: item.image || "",
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
    if (!session || !canUseCbtQuestionBank) {
      setBankQuestions([]);
      setSelectedBankQuestionIds([]);
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
  }, [canUseCbtQuestionBank, form.subjectId, session]);

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
        groupKey: question.group?.id ? `group-${question.group.id}` : "",
        group: question.group
          ? { ...question.group, imagePreview: question.group.image || "" }
          : { title: "", group_type: "passage", passage_text: "", imagePreview: "" },
        questionImagePreview: question.image || "",
      };
    });
    setQuestions(
      loadedQuestions.length
        ? loadedQuestions
        : [{ ...newBuilderQuestion(), id: 1 }]
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
      const groupKey = question.groupKey || "";
      return {
        text: question.text.trim(),
        points: Number(question.marks) || 1,
        options,
        correct_answer: (question.options || [])[Number(question.correctIndex)]?.trim() || "",
        explanation: question.explanation?.trim() || "",
        source_question_id: question.cbtBankQuestionId || undefined,
        question_image_field: question.questionImageFile ? `question_image_${question.id}` : "",
        group_key: groupKey,
        group: groupKey
          ? {
              key: groupKey,
              title: question.group?.title || "",
              group_type: question.group?.group_type || "passage",
              passage_text: question.group?.passage_text || "",
              image_field: question.group?.imageFile ? `passage_image_${groupKey}` : "",
            }
          : null,
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
        is_published: canPublishExam ? form.publishNow : false,
        questions: preparedQuestions,
      };
      const hasImages = questions.some((question) => question.questionImageFile || question.group?.imageFile);
      let requestPayload = payload;
      if (hasImages) {
        const formData = new FormData();
        Object.entries(payload).forEach(([key, value]) => {
          formData.append(key, key === "questions" ? JSON.stringify(value) : value);
        });
        const addedPassageImages = new Set();
        questions.forEach((question) => {
          if (question.questionImageFile) {
            formData.append(`question_image_${question.id}`, question.questionImageFile);
          }
          if (question.groupKey && question.group?.imageFile && !addedPassageImages.has(question.groupKey)) {
            formData.append(`passage_image_${question.groupKey}`, question.group.imageFile);
            addedPassageImages.add(question.groupKey);
          }
        });
        requestPayload = formData;
      }
      const result = isEditing ? await onUpdateExam(initialExam.id, requestPayload) : await onCreateExam(requestPayload);
      const savedExam = result?.exam || {};
      const hasExistingPin = Boolean(
        savedExam.pin_required ||
          Number(savedExam.active_pin_count || 0) > 0 ||
          initialExam?.pin_required ||
          Number(initialExam?.active_pin_count || 0) > 0
      );
      if (canPublishExam && form.publishNow && savedExam.id && !hasExistingPin) {
        const pinResult = await requestJson(session, "POST", "/api/app/exams/pins/", {
          exam_id: savedExam.id,
          usage_policy: "reusable",
          expires_at: savedExam.end_date || payload.end_date,
        });
        setPublishedPin({
          pin: pinResult.plain_pin || "",
          examTitle: savedExam.title || payload.title,
          expiresAt: savedExam.end_date || payload.end_date,
        });
        setCopyFeedback("");
        setFeedback("Exam published. Share the CBT PIN with eligible students.");
      } else {
        setFeedback(
          hasExistingPin && canPublishExam && form.publishNow
            ? "Exam updated. Existing CBT PIN remains active."
            : result?.message || (canPublishExam ? "Exam saved." : "Exam sent to admin for publishing.")
        );
      }
    } catch (saveError) {
      setError(saveError.message || "Could not save exam.");
    } finally {
      setSaving(false);
    }
  };

  const copyPublishedPin = async () => {
    if (!publishedPin?.pin) return;
    try {
      await navigator.clipboard.writeText(publishedPin.pin);
      setCopyFeedback("Copied.");
    } catch {
      setCopyFeedback("Select and copy the PIN manually.");
    }
  };

  const addSection = () => {
    setSections((previous) => [...previous, { id: Date.now(), title: `Section ${String.fromCharCode(65 + previous.length)}`, marks: "10" }]);
  };

  const addQuestion = () => {
    setQuestions((previous) => [...previous, newBuilderQuestion()]);
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

  const importStandardQuestions = () => {
    setImportError("");
    setImportFeedback("");
    try {
      const importedQuestions = parseImportedQuestions(importText);
      setQuestions((previous) =>
        previous.length === 1 && isBlankBuilderQuestion(previous[0]) ? importedQuestions : [...previous, ...importedQuestions]
      );
      setImportText("");
      setError("");
      setImportFeedback(`${importedQuestions.length} question${importedQuestions.length === 1 ? "" : "s"} imported.`);
    } catch (importParseError) {
      setImportError(importParseError.message || "Could not import questions.");
    }
  };

  const handleImportFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await readImportFileText(file);
      setImportText(text);
      setImportError("");
      setImportFeedback(`${file.name} converted to editable text. Review it, then import.`);
    } catch (fileError) {
      setImportFeedback("");
      setImportError(fileError.message || "Could not read the selected file.");
    }
    event.target.value = "";
  };

  const updateQuestion = (questionId, patch) => {
    setQuestions((previous) => previous.map((item) => (item.id === questionId ? { ...item, ...patch } : item)));
  };

  const updateQuestionGroup = (questionId, patch) => {
    setQuestions((previous) =>
      previous.map((item) => {
        const source = previous.find((question) => question.id === questionId);
        if (!source?.groupKey || item.groupKey !== source.groupKey) {
          return item.id === questionId ? { ...item, group: { ...(item.group || {}), ...patch } } : item;
        }
        return { ...item, group: { ...(item.group || {}), ...patch } };
      })
    );
  };

  const attachQuestionToGroup = (questionId, groupKey) => {
    const source = questions.find((item) => item.groupKey === groupKey && item.id !== questionId);
    updateQuestion(questionId, {
      groupKey,
      group: source?.group || { title: "", group_type: "passage", passage_text: "", imagePreview: "" },
    });
  };

  const createQuestionGroup = (questionId) => {
    updateQuestion(questionId, {
      groupKey: `group-${Date.now()}`,
      group: { title: "", group_type: "passage", passage_text: "", imagePreview: "" },
    });
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

  const groupOptions = questions
    .filter((item) => item.groupKey)
    .reduce((options, item) => {
      if (!options.some((option) => option.key === item.groupKey)) {
        options.push({
          key: item.groupKey,
          label: item.group?.title || `${item.group?.group_type || "Passage"} group`,
        });
      }
      return options;
    }, []);

  return (
    <section className={`exam-builder-shell ${isEditing ? "exam-builder-editing" : ""}`}>
      {publishedPin ? (
        <div className="cbt-info-modal" role="dialog" aria-modal="true" aria-labelledby="published-pin-title">
          <div className="cbt-info-card cbt-pin-card">
            <p className="cbt-info-kicker">Exam published</p>
            <h3 id="published-pin-title">CBT exam PIN</h3>
            <p>
              Share this PIN with students for {publishedPin.examTitle || "this exam"}. It is shown now so it can be copied before you close this popup.
            </p>
            <div className="cbt-pin-display" aria-label="Generated CBT exam PIN">
              {publishedPin.pin}
            </div>
            {publishedPin.expiresAt ? (
              <p className="cbt-pin-meta">Expires when the exam window closes: {formatDate(publishedPin.expiresAt)}</p>
            ) : null}
            {copyFeedback ? <p className="cbt-pin-copy-feedback">{copyFeedback}</p> : null}
            <div className="cbt-flag-actions">
              <button type="button" onClick={copyPublishedPin}>Copy PIN</button>
              <button type="button" onClick={() => setPublishedPin(null)}>Done</button>
            </div>
          </div>
        </div>
      ) : null}
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
              {saving ? "Saving..." : canPublishExam ? "Save Exam" : "Send to Admin"}
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
              {canUseCbtQuestionBank ? <div className="cbt-bank-picker">
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
              </div> : null}
              <div className="standard-question-import">
                <div className="cbt-bank-picker-head">
                  <div>
                    <h3>Import standard questions</h3>
                    <p>Teachers and admins can paste or upload MCQs from common school question formats.</p>
                  </div>
                  <div className="table-actions-inline">
                    <label className="table-action file-action">
                      Choose file
                      <input type="file" onChange={handleImportFile} />
                    </label>
                    <button type="button" className="table-action active" onClick={importStandardQuestions}>
                      Import questions
                    </button>
                  </div>
                </div>
                <textarea
                  className="standard-import-textarea"
                  value={importText}
                  onChange={(event) => {
                    setImportText(event.target.value);
                    setImportError("");
                    setImportFeedback("");
                  }}
                  placeholder={IMPORT_SAMPLE}
                  rows={8}
                />
                {importError ? <p className="form-feedback error">{importError}</p> : null}
                {importFeedback ? <p className="form-feedback success">{importFeedback}</p> : null}
              </div>
              {questions.map((question, index) => (
                <div key={question.id} className="exam-builder-question">
                  {question.sourceLabel ? <div className="cbt-question-source">From {question.sourceLabel}</div> : null}
                  <div className="exam-builder-row">
                    <label className="panel-field full">Question {index + 1}<textarea value={question.text} onChange={(event) => updateQuestion(question.id, { text: event.target.value })} rows={3} /></label>
                    <label className="panel-field">Type<input value="Objective MCQ" readOnly /></label>
                    <label className="panel-field">Marks<input type="number" min="1" value={question.marks} onChange={(event) => updateQuestion(question.id, { marks: event.target.value })} /></label>
                  </div>
                  <div className="exam-builder-row question-media-row">
                    <label className="panel-field">
                      Question image
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(event) => {
                          const file = event.target.files?.[0] || null;
                          updateQuestion(question.id, {
                            questionImageFile: file,
                            questionImagePreview: file ? filePreviewUrl(file) : question.questionImagePreview || "",
                          });
                        }}
                      />
                    </label>
                    {question.questionImagePreview ? (
                      <img className="question-builder-image-preview" src={question.questionImagePreview} alt="Question attachment preview" />
                    ) : null}
                  </div>
                  <div className="question-group-builder">
                    <div className="exam-builder-row">
                      <label className="panel-field">
                        Passage / group
                        <select
                          value={question.groupKey || ""}
                          onChange={(event) => {
                            const nextKey = event.target.value;
                            if (!nextKey) updateQuestion(question.id, { groupKey: "", group: { title: "", group_type: "passage", passage_text: "", imagePreview: "" } });
                            else attachQuestionToGroup(question.id, nextKey);
                          }}
                        >
                          <option value="">Standalone question</option>
                          {groupOptions.map((group) => (
                            <option key={group.key} value={group.key}>{group.label}</option>
                          ))}
                        </select>
                      </label>
                      <button type="button" className="table-action" onClick={() => createQuestionGroup(question.id)}>
                        New passage group
                      </button>
                    </div>
                    {question.groupKey ? (
                      <>
                        <div className="exam-builder-row">
                          <label className="panel-field">
                            Group type
                            <select value={question.group?.group_type || "passage"} onChange={(event) => updateQuestionGroup(question.id, { group_type: event.target.value })}>
                              <option value="passage">Passage</option>
                              <option value="comprehension">Comprehension</option>
                              <option value="register">Register</option>
                              <option value="diagram">Diagram / chart</option>
                              <option value="other">Other</option>
                            </select>
                          </label>
                          <label className="panel-field full">
                            Group title
                            <input value={question.group?.title || ""} onChange={(event) => updateQuestionGroup(question.id, { title: event.target.value })} placeholder="e.g. Passage A" />
                          </label>
                        </div>
                        <label className="panel-field full">
                          Passage / shared prompt
                          <textarea
                            value={question.group?.passage_text || ""}
                            onChange={(event) => updateQuestionGroup(question.id, { passage_text: event.target.value })}
                            rows={4}
                            placeholder="Text shown once before all linked questions"
                          />
                        </label>
                        <div className="exam-builder-row question-media-row">
                          <label className="panel-field">
                            Passage image
                            <input
                              type="file"
                              accept="image/*"
                              onChange={(event) => {
                                const file = event.target.files?.[0] || null;
                                updateQuestionGroup(question.id, {
                                  imageFile: file,
                                  imagePreview: file ? filePreviewUrl(file) : question.group?.imagePreview || "",
                                });
                              }}
                            />
                          </label>
                          {question.group?.imagePreview ? (
                            <img className="question-builder-image-preview" src={question.group.imagePreview} alt="Passage attachment preview" />
                          ) : null}
                        </div>
                      </>
                    ) : null}
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
              {canPublishExam ? (
                <label className="remember-row"><input type="checkbox" checked={form.publishNow} onChange={(event) => setField("publishNow", event.target.checked)} /> Publish immediately</label>
              ) : (
                <p className="student-panel-sub">Saving sends this exam to an administrator for publishing.</p>
              )}
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
  const [pinBusy, setPinBusy] = useState("");
  const [pinMessage, setPinMessage] = useState("");
  const [pinPlain, setPinPlain] = useState("");
  const canManagePins = ["school_admin", "principal", "super_admin"].includes(session?.user?.role);

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

  const generatePin = async (exam) => {
    setPinBusy(`generate-${exam.id}`);
    setPinMessage("");
    setPinPlain("");
    try {
      const result = await requestJson(session, "POST", "/api/app/exams/pins/", {
        exam_id: exam.id,
        usage_policy: "reusable",
        expires_at: exam.end_date,
      });
      setPinPlain(result.plain_pin || "");
      setPinMessage(`PIN generated for ${exam.title}.`);
      await loadExams();
    } catch (pinError) {
      setPinMessage(pinError.message || "Could not generate PIN.");
    } finally {
      setPinBusy("");
    }
  };

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
      {pinMessage ? <p className={`form-feedback ${pinPlain ? "success" : "error"}`}>{pinMessage}{pinPlain ? ` PIN: ${pinPlain}` : ""}</p> : null}

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
                {canManagePins ? <th>PIN</th> : null}
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
                  {canManagePins ? (
                    <td>
                      <button
                        type="button"
                        className={`table-action ${exam.pin_required ? "active" : ""}`}
                        onClick={() => generatePin(exam)}
                        disabled={pinBusy === `generate-${exam.id}`}
                      >
                        {pinBusy === `generate-${exam.id}` ? "Generating..." : exam.pin_required ? `Active (${exam.active_pin_count || 1})` : "Generate PIN"}
                      </button>
                    </td>
                  ) : null}
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
  const [attachments, setAttachments] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const attachmentInputRef = useRef(null);

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
    if (!form.body.trim() && attachments.length === 0) {
      setError("Write a message or choose an attachment before sending.");
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
        attachments,
      });
      setFeedback(result?.message || "Message sent to the class.");
      setForm((prev) => ({ ...prev, subject: "", body: "" }));
      setAttachments([]);
      if (attachmentInputRef.current) {
        attachmentInputRef.current.value = "";
      }
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
          <label className="panel-field full">
            Attachments
            <input ref={attachmentInputRef} type="file" multiple onChange={(event) => setAttachments(Array.from(event.target.files || []).slice(0, 5))} />
            {attachments.length ? <small className="field-note">{attachments.map((file) => file.name).join(", ")}</small> : null}
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


