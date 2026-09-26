import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { requestJson, Spinner } from "../AppShared";

// Small enough that one request stays well inside the server's worker timeout
// (a password is hashed for every student created).
const BATCH_SIZE = 10;
const PREVIEW_URL = "/api/app/students/import/preview/";
const COMMIT_URL = "/api/app/students/import/commit/";

const TEMPLATE_CSV = [
  "first_name,middle_name,last_name,class,gender,date_of_birth,guardian_name,guardian_phone,second_guardian_name,second_guardian_phone,guardian_email,home_address,student_email,password",
  'Ada,,Okafor,JSS 1,F,2013-05-14,,08012345678,,,,"12 Example Street, Lagos",,',
].join("\n");

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(filename, text) {
  const blob = new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function loginSheet(created) {
  const header = ["Student ID", "Name", "Class", "Login email", "Password", "Guardian", "Guardian phone"];
  const lines = created.map((item) =>
    [item.student_id, item.name, item.class_label, item.email, item.password, item.guardian_name, item.guardian_phone].map(csvCell).join(",")
  );
  return [header.map(csvCell).join(","), ...lines].join("\r\n");
}

export default function StudentImportModal({ session, onClose, onImported }) {
  const [stage, setStage] = useState("choose"); // choose | review | importing | done
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const [sourceRows, setSourceRows] = useState([]);
  const [classChoices, setClassChoices] = useState({});
  const [emailDomain, setEmailDomain] = useState("gmail.com");
  const [assignTokens, setAssignTokens] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [results, setResults] = useState(null);
  const latestCheck = useRef(0);
  const domainTimer = useRef(null);

  useEffect(() => () => clearTimeout(domainTimer.current), []);

  // A class typed for the whole file (no class column) is sent as the default
  // class; every other mapping goes in class_map, keyed by the text in the file.
  const splitChoices = (choices) => {
    const { "": defaultClass = "", ...classMap } = choices;
    return { defaultClass, classMap };
  };

  const check = useCallback(
    async ({ fileToSend = null, rows = null, choices, domain, first = false }) => {
      const id = ++latestCheck.current;
      const { defaultClass, classMap } = splitChoices(choices);
      setBusy(true);
      setError("");
      try {
        const payload = fileToSend
          ? { file: fileToSend, default_class_id: defaultClass, class_map: JSON.stringify(classMap), email_domain: domain }
          : { rows, default_class_id: defaultClass, class_map: classMap, email_domain: domain };
        const result = await requestJson(session, "POST", PREVIEW_URL, payload, { skipDuplicateCheck: true });
        if (id !== latestCheck.current) return;
        if (result.source_rows) setSourceRows(result.source_rows);
        setPreview(result);
        if (first) {
          const tokens = result.activation_tokens || {};
          setAssignTokens(tokens.needed > 0 && tokens.available >= tokens.needed);
          setStage("review");
        }
      } catch (err) {
        if (id !== latestCheck.current) return;
        setError(err.message || "Could not read that file.");
      } finally {
        if (id === latestCheck.current) setBusy(false);
      }
    },
    [session]
  );

  const chooseFile = (event) => {
    const picked = event.target.files?.[0] || null;
    setFile(picked);
    setError("");
  };

  const readFile = () => {
    if (!file) {
      setError("Choose the CSV file first.");
      return;
    }
    setClassChoices({});
    check({ fileToSend: file, choices: {}, domain: emailDomain, first: true });
  };

  const changeClass = (source, classId) => {
    const next = { ...classChoices };
    if (classId) next[source] = classId;
    else delete next[source];
    setClassChoices(next);
    check({ rows: sourceRows, choices: next, domain: emailDomain });
  };

  const changeDomain = (value) => {
    setEmailDomain(value);
    clearTimeout(domainTimer.current);
    domainTimer.current = setTimeout(() => check({ rows: sourceRows, choices: classChoices, domain: value }), 500);
  };

  const startImport = async () => {
    const creating = new Set(preview.rows.filter((row) => row.status === "create").map((row) => row.line));
    const queue = sourceRows.filter((row) => creating.has(row.line));
    const { defaultClass, classMap } = splitChoices(classChoices);
    const summary = { created: [], skipped: [], failed: [], warnings: [], tokens: 0, tokenMessage: "", stopped: "" };
    setStage("importing");
    setProgress({ done: 0, total: queue.length });
    for (let start = 0; start < queue.length; start += BATCH_SIZE) {
      try {
        const answer = await requestJson(
          session,
          "POST",
          COMMIT_URL,
          {
            rows: queue.slice(start, start + BATCH_SIZE),
            default_class_id: defaultClass,
            class_map: classMap,
            email_domain: emailDomain,
            assign_tokens: assignTokens,
          },
          { skipDuplicateCheck: true }
        );
        summary.created.push(...(answer.created || []));
        summary.skipped.push(...(answer.skipped || []));
        summary.failed.push(...(answer.failed || []));
        summary.warnings.push(...(answer.warnings || []));
        summary.tokens += answer.tokens_assigned || 0;
        summary.tokenMessage = summary.tokenMessage || answer.token_message || "";
      } catch (err) {
        summary.stopped = err.message || "The connection was lost.";
        break;
      }
      setProgress({ done: Math.min(start + BATCH_SIZE, queue.length), total: queue.length });
    }
    setResults(summary);
    setStage("done");
    if (summary.created.length) onImported?.();
  };

  const locked = stage === "importing";
  const counts = preview?.counts || { create: 0, skip: 0, error: 0 };
  const tokens = preview?.activation_tokens || { available: 0, needed: 0 };
  const needsClass = (preview?.classes || []).filter((item) => !item.class_id);

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="student-import-title"
      onClick={(event) => {
        if (event.target === event.currentTarget && !locked) onClose();
      }}
    >
      <article className="app-panel edit-modal-card student-import-card">
        <div className="edit-modal-head">
          <div>
            <h3 id="student-import-title">Import students from a spreadsheet</h3>
            <p>Add a whole class at once instead of typing each student.</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={onClose} disabled={locked} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="modal-form-wrap student-import-body">
          {stage === "choose" ? (
            <>
              <ol className="student-import-steps">
                <li>
                  Put your students in a spreadsheet with a <strong>first name</strong> and a <strong>surname</strong> column. Class, gender,
                  date of birth, phone number and home address are read too when they are there.{" "}
                  <button type="button" className="link-button" onClick={() => downloadCsv("students-template.csv", TEMPLATE_CSV)}>
                    Download a template
                  </button>
                </li>
                <li>In Excel choose <strong>File &gt; Save As &gt; CSV</strong>, then choose that file below.</li>
                <li>You will see exactly what will happen before anything is saved.</li>
              </ol>
              <label className="panel-field">
                CSV file
                <input type="file" accept=".csv,text/csv" onChange={chooseFile} />
              </label>
              <div className="student-import-rules">
                <strong>How the details are filled in</strong>
                <ul>
                  <li>A student without an email gets one made from one of their names, e.g. ada@{emailDomain || "gmail.com"}.</li>
                  <li>Every student gets their own password, shown once at the end.</li>
                  <li>Without a guardian name, the child's surname is used. Two phone numbers become Mr and Mrs plus the surname.</li>
                  <li>Someone already in the same class with the same name is skipped, so importing a file twice is safe.</li>
                </ul>
              </div>
              {error ? <p className="form-feedback error">{error}</p> : null}
              <div className="panel-form-actions">
                <button type="button" onClick={readFile} disabled={busy || !file}>
                  {busy ? <><Spinner /> Reading...</> : "Check file"}
                </button>
              </div>
            </>
          ) : null}

          {stage === "review" && preview ? (
            <>
              <div className="student-import-counts">
                <span className="student-import-count ok"><strong>{counts.create}</strong> ready to add</span>
                <span className="student-import-count"><strong>{counts.skip}</strong> already there</span>
                <span className={`student-import-count ${counts.error ? "bad" : ""}`}><strong>{counts.error}</strong> need attention</span>
                {busy ? <span className="student-import-count"><Spinner size={12} /> Checking...</span> : null}
              </div>

              <div className="student-import-section">
                <strong>Classes in your file</strong>
                <table className="data-table student-import-classes">
                  <tbody>
                    {preview.classes.map((item) => {
                      const chosen = classChoices[item.source] ?? item.class_id ?? "";
                      return (
                        <tr key={item.source || "(none)"}>
                          <td>{item.source || "(no class in the file)"} <small>{item.count} student{item.count === 1 ? "" : "s"}</small></td>
                          <td>
                            <select value={chosen} onChange={(event) => changeClass(item.source, event.target.value)} aria-label={`Class for ${item.source || "students with no class"}`}>
                              <option value="">Choose a class...</option>
                              {preview.available_classes.map((option) => (
                                <option key={option.id} value={option.id}>{option.label}</option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {needsClass.length ? <p className="form-feedback error">Choose a class for the ones above that are empty. Create the class first if it does not exist yet.</p> : null}
              </div>

              <div className="student-import-section">
                <label className="panel-field">
                  Email domain for students without an email
                  <input value={emailDomain} onChange={(event) => changeDomain(event.target.value)} placeholder="gmail.com" />
                </label>
                <small>
                  A generated address such as ada@{emailDomain || "gmail.com"} may belong to someone else, and whoever owns it could ask for that
                  student's password to be reset. Use your school's own domain if you have one.
                </small>
              </div>

              {counts.create > 0 ? (
                <label className="student-import-check">
                  <input type="checkbox" checked={assignTokens} onChange={(event) => setAssignTokens(event.target.checked)} />
                  <span>
                    Give each new student an activation token so they can sign in now
                    <small> (uses {counts.create} of your {tokens.available} tokens{tokens.available < counts.create ? " - not enough for everyone" : ""})</small>
                  </span>
                </label>
              ) : null}

              <div className="table-scroll student-import-rows">
                <table className="data-table">
                  <thead>
                    <tr><th>#</th><th>Student</th><th>Class</th><th>Login email</th><th>Guardian</th><th>Result</th></tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row) => (
                      <tr key={row.line} className={`student-import-row ${row.status}`}>
                        <td>{row.line}</td>
                        <td>{[row.last_name, row.first_name, row.middle_name].filter(Boolean).join(" ")}</td>
                        <td>{row.class_label || row.class_source || "-"}</td>
                        <td>{row.email || "-"}</td>
                        <td>{row.guardian_name ? `${row.guardian_name}${row.second_guardian_name ? ` & ${row.second_guardian_name}` : ""}` : "-"}</td>
                        <td>
                          {row.status === "create" ? (row.warnings?.length ? row.warnings.join(" ") : "Ready") : row.message}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {error ? <p className="form-feedback error">{error}</p> : null}
              <div className="panel-form-actions">
                <button type="button" className="table-action" onClick={() => { setStage("choose"); setPreview(null); }}>Choose another file</button>
                <button type="button" onClick={startImport} disabled={busy || counts.create === 0}>
                  Import {counts.create} student{counts.create === 1 ? "" : "s"}
                </button>
              </div>
            </>
          ) : null}

          {stage === "importing" ? (
            <div className="student-import-progress">
              <Spinner />
              <p>Adding students... {progress.done} of {progress.total}</p>
              <progress value={progress.done} max={Math.max(progress.total, 1)} />
              <small>Keep this window open until it finishes.</small>
            </div>
          ) : null}

          {stage === "done" && results ? (
            <>
              <p className={`form-feedback ${results.stopped ? "error" : "success"}`}>
                {results.stopped
                  ? `Stopped after ${results.created.length} student${results.created.length === 1 ? "" : "s"}: ${results.stopped} Upload the same file again to add the rest - anyone already added is skipped.`
                  : `${results.created.length} student${results.created.length === 1 ? "" : "s"} added.`}
              </p>
              {results.created.length ? (
                <div className="student-import-section">
                  <button type="button" onClick={() => downloadCsv("student-logins.csv", loginSheet(results.created))}>
                    Download login sheet
                  </button>
                  <p><small>
                    This is the only time the passwords are shown - they cannot be looked up later. Keep the sheet private and hand each
                    family their own line.
                  </small></p>
                </div>
              ) : null}
              {results.tokens ? <p>{results.tokens} activation token{results.tokens === 1 ? "" : "s"} assigned.</p> : null}
              {results.tokenMessage ? <p className="form-feedback error">Tokens: {results.tokenMessage} Assign them from the students list when you have more.</p> : null}
              {results.skipped.length ? <p>{results.skipped.length} skipped because they were already in the class.</p> : null}
              {results.warnings.length ? <ul>{results.warnings.map((text, index) => <li key={index}>{text}</li>)}</ul> : null}
              {results.failed.length ? (
                <div className="student-import-section">
                  <strong>{results.failed.length} not added</strong>
                  <ul>{results.failed.map((item) => <li key={item.line}>Line {item.line}, {item.name}: {item.message}</li>)}</ul>
                </div>
              ) : null}
              <div className="panel-form-actions">
                <button type="button" onClick={onClose}>Done</button>
              </div>
            </>
          ) : null}
        </div>
      </article>
    </div>
  );
}
