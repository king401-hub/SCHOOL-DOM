import { useCallback, useEffect, useMemo, useState } from "react";

const api = window.schoolDomAdmin;

const fallbackApi = {
  bootstrap: async () => ({
    appName: "SchoolDom Admin",
    appVersion: "0.1.0",
    serverUrl: "https://schooldom.academy",
    school: { name: "SchoolDom", school_code: "schooldom", logo: "", address: "", phone: "", email: "" },
    server: { online: true, host: "schooldom.academy" },
    downloads: { student_cbt: "https://schooldom.academy/app/download/student-cbt/" },
    local_data: { school: {}, classes: [], students: [], exams: [], activation_tokens: {} },
    dashboard: {
      settings: { name: "SchoolDom", ip_address: "schooldom.academy", refresh_interval: "30 sec" },
      content: { total: 0 },
      candidate: { total: 0, class: 0 },
      client: { total: 1 },
      test: { total: 0, licensed: 0, pending: 0, ongoing: 0, submitted: 0, batch_count: 0 },
    },
  }),
  settings: async () => ({ serverUrl: "https://schooldom.academy", schoolCode: "" }),
  saveSettings: async (payload) => payload,
  openCbtInstaller: async () => ({ success: true }),
  lan: {
    snapshot: async () => ({ running: false, urls: [], exams: [], students: [], sessions: [] }),
    start: async () => ({ running: true, urls: ["http://192.168.1.10:4785"], exams: [], students: [], sessions: [] }),
    stop: async () => ({ running: false, urls: [], exams: [], students: [], sessions: [] }),
    publishExam: async () => ({ running: true, urls: ["http://192.168.1.10:4785"], exams: [], students: [], sessions: [] }),
    saveStudent: async () => ({ running: true, urls: ["http://192.168.1.10:4785"], exams: [], students: [], sessions: [] }),
  },
};

function initials(name) {
  return String(name || "SD")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "SD";
}

function hostFromUrl(value) {
  try {
    return new URL(value).host;
  } catch {
    return value || "";
  }
}

function blankQuestion(index = 1) {
  return {
    id: `question_${Date.now()}_${index}`,
    text: "",
    type: "mcq",
    marks: 1,
    imageName: "",
    group: "",
    options: { A: "", B: "", C: "", D: "" },
    correctAnswer: "A",
    explanation: "",
  };
}

function parseStandardQuestions(input) {
  const text = String(input || "").replace(/\r/g, "").trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    const rows = Array.isArray(parsed) ? parsed : parsed.questions || parsed.items || [];
    if (Array.isArray(rows) && rows.length) {
      return rows.map((item, index) => {
        const question = blankQuestion(index + 1);
        const options = Array.isArray(item.options) ? item.options : Array.isArray(item.choices) ? item.choices : [];
        question.text = String(item.text || item.question || item.prompt || "").trim();
        question.type = item.type === "multiple_choice" ? "mcq" : item.question_type || item.type || "mcq";
        question.marks = Number(item.marks || item.points || item.score || 1);
        question.correctAnswer = String(item.correct_answer || item.answer || item.correctAnswer || "A").trim().slice(0, 1).toUpperCase() || "A";
        question.explanation = String(item.explanation || "").trim();
        options.slice(0, 4).forEach((option, optionIndex) => {
          const key = ["A", "B", "C", "D"][optionIndex];
          question.options[key] = typeof option === "string" ? option : option.text || option.label || "";
        });
        return question;
      }).filter((question) => question.text || Object.values(question.options).some(Boolean));
    }
  } catch {
    // Not JSON; continue with plain-text question import.
  }
  const blocks = text
    .split(/\n(?=\s*\d+[\).]\s*)/)
    .map((block) => block.trim())
    .filter(Boolean);
  const sourceBlocks = blocks.length ? blocks : text.split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
  return sourceBlocks.map((block, index) => {
    const question = blankQuestion(index + 1);
    const questionLines = [];
    block.split("\n").map((line) => line.trim()).filter(Boolean).forEach((line) => {
      const optionMatch = line.match(/^([A-D])[\).]\s*(.+)$/i);
      const answerMatch = line.match(/^answer\s*[:\-]\s*([A-D])\b/i);
      if (optionMatch) {
        question.options[optionMatch[1].toUpperCase()] = optionMatch[2].trim();
      } else if (answerMatch) {
        question.correctAnswer = answerMatch[1].toUpperCase();
      } else {
        questionLines.push(line.replace(/^\d+[\).]\s*/, ""));
      }
    });
    question.text = questionLines.join("\n").trim();
    return question;
  }).filter((question) => question.text || Object.values(question.options).some(Boolean));
}

function findEndOfCentralDirectory(bytes) {
  for (let index = bytes.length - 22; index >= 0; index -= 1) {
    if (bytes[index] === 0x50 && bytes[index + 1] === 0x4b && bytes[index + 2] === 0x05 && bytes[index + 3] === 0x06) {
      return index;
    }
  }
  return -1;
}

async function inflateRaw(bytes) {
  if (!("DecompressionStream" in window)) {
    throw new Error("This Windows webview cannot decompress Word documents yet.");
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function extractZipFile(bytes, wantedName) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const endOffset = findEndOfCentralDirectory(bytes);
  if (endOffset < 0) throw new Error("Invalid Word document.");
  const entryCount = view.getUint16(endOffset + 10, true);
  const directoryOffset = view.getUint32(endOffset + 16, true);
  let pointer = directoryOffset;
  const decoder = new TextDecoder();

  for (let index = 0; index < entryCount; index += 1) {
    if (view.getUint32(pointer, true) !== 0x02014b50) break;
    const method = view.getUint16(pointer + 10, true);
    const compressedSize = view.getUint32(pointer + 20, true);
    const fileNameLength = view.getUint16(pointer + 28, true);
    const extraLength = view.getUint16(pointer + 30, true);
    const commentLength = view.getUint16(pointer + 32, true);
    const localOffset = view.getUint32(pointer + 42, true);
    const name = decoder.decode(bytes.slice(pointer + 46, pointer + 46 + fileNameLength));
    if (name === wantedName) {
      const localNameLength = view.getUint16(localOffset + 26, true);
      const localExtraLength = view.getUint16(localOffset + 28, true);
      const dataStart = localOffset + 30 + localNameLength + localExtraLength;
      const compressed = bytes.slice(dataStart, dataStart + compressedSize);
      if (method === 0) return compressed;
      if (method === 8) return inflateRaw(compressed);
      throw new Error("Unsupported Word compression method.");
    }
    pointer += 46 + fileNameLength + extraLength + commentLength;
  }
  throw new Error("Could not find document text inside the Word file.");
}

function wordXmlToText(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  const paragraphs = Array.from(doc.getElementsByTagName("w:p"));
  return paragraphs
    .map((paragraph) => Array.from(paragraph.getElementsByTagName("w:t")).map((node) => node.textContent || "").join(""))
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}

async function extractDocxText(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const xmlBytes = await extractZipFile(bytes, "word/document.xml");
  return wordXmlToText(new TextDecoder("utf-8").decode(xmlBytes));
}

async function extractLegacyDocText(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const utf16 = new TextDecoder("utf-16le", { fatal: false }).decode(bytes);
  const ansi = new TextDecoder("windows-1252", { fatal: false }).decode(bytes);
  const clean = `${utf16}\n${ansi}`
    .replace(/[^\S\r\n]+/g, " ")
    .replace(/[^\x09\x0a\x0d\x20-\x7e\u00a0-\uffff]/g, "\n");
  return clean
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line.length > 2 && /[A-Za-z0-9]/.test(line))
    .join("\n");
}

function questionsToJsonText(questions) {
  return JSON.stringify(
    questions.map((question, index) => ({
      id: question.id,
      number: index + 1,
      text: question.text || `Question ${index + 1}`,
      type: question.type === "mcq" ? "multiple_choice" : question.type,
      options: ["A", "B", "C", "D"].map((key) => ({ key, text: question.options?.[key] || "" })).filter((item) => item.text),
      marks: Number(question.marks || 1),
      correct_answer: question.correctAnswer,
      explanation: question.explanation || "",
      group: question.group || "",
    })),
    null,
    2
  );
}

export default function App() {
  const bridge = api || fallbackApi;
  const [booting, setBooting] = useState(true);
  const [data, setData] = useState(null);
  const [serverUrl, setServerUrl] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [installing, setInstalling] = useState(false);
  const [activePage, setActivePage] = useState("dashboard");
  const [examBuilderStep, setExamBuilderStep] = useState("details");
  const [themePreference, setThemePreference] = useState("light");
  const [settingsForm, setSettingsForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    logo: "",
    academicYearName: "",
    academicYearStart: "",
    academicYearEnd: "",
    termName: "",
    termStart: "",
    termEnd: "",
    supportSubject: "",
    supportMessage: "",
  });
  const [lan, setLan] = useState({ running: false, urls: [], exams: [], students: [], sessions: [] });
  const [examForm, setExamForm] = useState({
    title: "Offline CBT Exam",
    subject: "",
    durationMinutes: "60",
    pin: "",
    studentsText: "",
    instructions: "Answer all questions. Submit before the timer ends.",
    questionsText: "Question 1\n\nQuestion 2",
  });
  const [questionItems, setQuestionItems] = useState([blankQuestion(1)]);
  const [studentForm, setStudentForm] = useState({
    student_id: "",
    full_name: "",
    class_name: "",
    email: "",
    is_active: true,
  });

  const loadDashboard = useCallback(
    async (options = {}) => {
      setError("");
      try {
        const payload = await bridge.bootstrap({
          serverUrl: options.serverUrl ?? serverUrl,
          schoolCode: options.schoolCode ?? schoolCode,
        });
        setData(payload);
        setServerUrl(payload.serverUrl || options.serverUrl || serverUrl);
        setSchoolCode(payload.school?.school_code || options.schoolCode || schoolCode);
        setNotice(`Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
      } catch (loadError) {
        setError(loadError.message || "Could not reach the SchoolDom server.");
      } finally {
        setBooting(false);
      }
    },
    [bridge, schoolCode, serverUrl]
  );

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const settings = await bridge.settings();
        if (!active) return;
        setServerUrl(settings.serverUrl || "");
        setSchoolCode(settings.schoolCode || "");
        await loadDashboard({ serverUrl: settings.serverUrl || "", schoolCode: settings.schoolCode || "" });
      } catch (settingsError) {
        if (!active) return;
        setError(settingsError.message || "Could not load app settings.");
        setBooting(false);
      }
    })();
    const interval = window.setInterval(() => loadDashboard().catch(() => null), 30000);
    const lanInterval = window.setInterval(() => bridge.lan?.snapshot?.().then(setLan).catch(() => null), 3000);
    bridge.lan?.start?.().then(setLan).catch(() => null);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.clearInterval(lanInterval);
    };
  }, []);

  useEffect(() => {
    if (!data) return;
    const desktop = data.desktop_settings || {};
    const profile = desktop.schoolProfile || data.school || {};
    const year = desktop.academicYear || data.academic_year || {};
    const termItem = desktop.term || data.term || {};
    setThemePreference(desktop.themePreference || "light");
    setSettingsForm((current) => ({
      ...current,
      name: profile.name || "",
      email: profile.email || "",
      phone: profile.phone || "",
      address: profile.address || "",
      logo: profile.logo || "",
      academicYearName: year.name || "",
      academicYearStart: String(year.start_date || "").slice(0, 10),
      academicYearEnd: String(year.end_date || "").slice(0, 10),
      termName: termItem.name || "",
      termStart: String(termItem.start_date || "").slice(0, 10),
      termEnd: String(termItem.end_date || "").slice(0, 10),
    }));
  }, [data]);

  const school = data?.school || {};
  const dashboard = data?.dashboard || {};
  const localData = data?.local_data || {};
  const localClasses = localData.classes || lan.classes || [];
  const localStudents = localData.students || lan.students || [];
  const localExams = localData.exams || lan.exams || [];
  const tokenSummary = localData.activation_tokens || lan.token_summary || {};
  const settings = dashboard.settings || {};
  const test = dashboard.test || {};
  const activeStudents = localStudents.filter((student) => student.is_active !== false).length;
  const inactiveStudents = Math.max(0, localStudents.length - activeStudents);
  const questionCount = questionItems.length;
  const pageTitles = {
    dashboard: "Home / Dashboard",
    room: "Offline Exam Room",
    exams: "Exams",
    students: "Students",
    school: "School Details",
    install: "Install & Settings",
  };

  const schoolDetails = useMemo(
    () => [
      ["Name", school.name || "SchoolDom"],
      ["Code", school.school_code || "-"],
      ["Phone", school.phone || "-"],
      ["Email", school.email || "-"],
      ["Address", school.address || "-"],
    ],
    [school]
  );

  const saveAndRefresh = async (event) => {
    event.preventDefault();
    setNotice("Saving settings...");
    const desktopSettings = {
      themePreference,
      schoolProfile: {
        ...(data?.school || {}),
        name: settingsForm.name.trim(),
        email: settingsForm.email.trim(),
        phone: settingsForm.phone.trim(),
        address: settingsForm.address.trim(),
        logo: settingsForm.logo.trim(),
      },
      academicYear: {
        ...(data?.academic_year || {}),
        name: settingsForm.academicYearName.trim(),
        start_date: settingsForm.academicYearStart,
        end_date: settingsForm.academicYearEnd,
      },
      term: {
        ...(data?.term || {}),
        name: settingsForm.termName.trim(),
        start_date: settingsForm.termStart,
        end_date: settingsForm.termEnd,
      },
    };
    await bridge.saveSettings({
      serverUrl,
      schoolCode,
      desktopSettings,
    });
    setData((current) => ({ ...(current || {}), desktop_settings: desktopSettings }));
    setNotice("Desktop settings saved.");
  };

  const installCbt = async () => {
    setInstalling(true);
    setNotice("Downloading the CBT app installer...");
    try {
      await bridge.openCbtInstaller({ serverUrl: data?.serverUrl || serverUrl, downloadUrl: data?.downloads?.student_cbt });
      setNotice("The real CBT installer is opening. Use it on student computers.");
    } catch (installError) {
      setError(installError.message || "Could not open the CBT installer.");
    } finally {
      setInstalling(false);
    }
  };

  const updateExamForm = (key, value) => setExamForm((current) => ({ ...current, [key]: value }));
  const updateStudentForm = (key, value) => setStudentForm((current) => ({ ...current, [key]: value }));
  const updateSettingsForm = (key, value) => setSettingsForm((current) => ({ ...current, [key]: value }));
  const updateQuestion = (id, patch) => setQuestionItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  const updateQuestionOption = (id, key, value) => setQuestionItems((current) => current.map((item) => item.id === id ? { ...item, options: { ...item.options, [key]: value } } : item));

  const addQuestion = () => {
    setQuestionItems((current) => [...current, blankQuestion(current.length + 1)]);
    setNotice("New question added.");
  };

  const removeQuestion = (id) => {
    setQuestionItems((current) => {
      const next = current.filter((item) => item.id !== id);
      return next.length ? next : [blankQuestion(1)];
    });
    setNotice("Question deleted.");
  };

  const importQuestions = () => {
    const parsed = parseStandardQuestions(examForm.questionsText);
    if (!parsed.length) {
      setError("Paste questions before importing.");
      return;
    }
    setQuestionItems(parsed);
    setNotice(`${parsed.length} question${parsed.length === 1 ? "" : "s"} imported.`);
  };

  const handleQuestionFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    if (!["txt", "csv", "json", "docx", "doc"].includes(extension)) {
      setError("Import .txt, .csv, .json, .docx, or .doc question files only.");
      event.target.value = "";
      return;
    }
    try {
      let text = "";
      if (extension === "docx") {
        text = await extractDocxText(file);
      } else if (extension === "doc") {
        text = await extractLegacyDocText(file);
      } else {
        text = await file.text();
      }
      if (text.startsWith("PK\u0003\u0004")) {
        text = await extractDocxText(file);
      }
      updateExamForm("questionsText", text);
      const parsed = parseStandardQuestions(text);
      if (parsed.length) {
        setQuestionItems(parsed);
        setNotice(`${parsed.length} question${parsed.length === 1 ? "" : "s"} imported from ${file.name}.`);
      } else {
        setError("Could not read questions from that file.");
      }
    } catch (importError) {
      setError(importError.message || "Could not import questions from that file.");
    } finally {
      event.target.value = "";
    }
  };

  const publishLanExam = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("Publishing exam to the local network...");
    try {
      const nextLan = await bridge.lan.publishExam({ ...examForm, questionsText: questionsToJsonText(questionItems) });
      setLan(nextLan);
      setNotice("Exam published. Students can connect using the LAN address.");
    } catch (publishError) {
      setError(publishError.message || "Could not publish the offline exam.");
    }
  };

  const startLan = async () => {
    setLan(await bridge.lan.start());
    setNotice("Offline exam room is online on this router.");
  };

  const stopLan = async () => {
    setLan(await bridge.lan.stop());
    setNotice("Offline exam room stopped.");
  };

  const saveStudent = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const nextLan = await bridge.lan.saveStudent(studentForm);
      setLan(nextLan);
      setStudentForm({ student_id: "", full_name: "", class_name: "", email: "", is_active: true });
      setNotice("Student saved locally.");
    } catch (studentError) {
      setError(studentError.message || "Could not save student.");
    }
  };

  const editStudent = (student) => {
    setStudentForm({
      student_id: student.student_id || "",
      full_name: student.full_name || "",
      class_name: student.class_name || "",
      email: student.email || "",
      is_active: student.is_active !== false,
    });
  };

  if (booting) {
    return (
      <main className="splash-screen">
        <div className="brand-mark">SD</div>
        <h1>SchoolDom Admin</h1>
        <p>Loading school dashboard...</p>
      </main>
    );
  }

  return (
    <main className={`admin-shell theme-${themePreference}`}>
      <header className="topbar">
        <strong>{pageTitles[activePage]}</strong>
        <span>LAN <b>{lan.running ? "On" : "Off"}</b></span>
      </header>

      <div className="admin-layout">
        <aside className="page-nav">
          <div className="nav-brand">
            <div className="school-logo compact">
              {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{initials(school.name)}</span>}
            </div>
            <strong>{school.name || "SchoolDom"}</strong>
            <small>{data?.offline ? "Offline cache" : "Admin App"}</small>
          </div>
          {[
            ["dashboard", "Dashboard"],
            ["room", "Exam Room"],
            ["exams", "Exams"],
            ["students", "Students"],
            ["school", "School"],
            ["install", "Install"],
          ].map(([key, label]) => (
            <button key={key} type="button" className={activePage === key ? "active" : ""} onClick={() => setActivePage(key)}>
              {label}
            </button>
          ))}
        </aside>

        <section className="content-stage">
          <header className="page-head">
            <div>
              <p>{data?.offline ? "Offline data available" : "SchoolDom Admin Console"}</p>
              <h1>{pageTitles[activePage]}</h1>
            </div>
            <div className={`status-pill ${lan.running ? "online" : "offline"}`}>
              <span />
              {lan.running ? "LAN room running" : "LAN room stopped"}
            </div>
          </header>

      <div className={`dashboard-grid page-${activePage}`}>
        {activePage === "dashboard" ? (
          <>
            <article className="hero-panel">
              <div>
                <p>{school.school_code || "schooldom"}</p>
                <h2>{school.name || "SchoolDom"} CBT Control Room</h2>
                <span>{data?.offline ? "Using cached school data for offline work." : "School data is synced and ready for local CBT publishing."}</span>
              </div>
              <div className="hero-metrics">
                <strong>{localStudents.length || dashboard.candidate?.total || 0}<span>Students</span></strong>
                <strong>{localExams.length || test.total || 0}<span>Exams</span></strong>
                <strong>{localClasses.length || dashboard.candidate?.class || 0}<span>Classes</span></strong>
              </div>
            </article>

            <article className="tile content-tile">
              <TileHead icon="content" title="Content" />
              <Field label="Question Content" value={dashboard.content?.total ?? 0} />
              <Field label="Fetched Classes" value={localClasses.length} />
              <Field label="Fetched Exams" value={localExams.length} />
            </article>

            <article className="tile candidate-tile">
              <TileHead icon="candidate" title="Candidate" />
              <Field label="Fetched Students" value={localStudents.length || dashboard.candidate?.total || 0} />
              <Field label="Active Students" value={tokenSummary.active_students ?? activeStudents} />
              <Field label="Inactive Students" value={tokenSummary.inactive_students ?? inactiveStudents} />
              <Field label="Classes" value={localClasses.length || dashboard.candidate?.class || 0} />
            </article>

            <article className="tile test-tile">
              <TileHead icon="test" title="Test" />
              <Field label="Fetched Exams" value={localExams.length || test.total || 0} />
              <Field label="Published" value={test.licensed ?? 0} />
              <Field label="Pending" value={test.pending ?? 0} />
              <Field label="Ongoing" value={test.ongoing ?? 0} />
              <Field label="Submitted" value={test.submitted ?? 0} />
              <Field label="Batch Count" value={test.batch_count ?? 0} />
            </article>

            <article className="tile token-tile">
              <TileHead icon="school" title="Student Tokens" />
              <Field label="Balance" value={tokenSummary.balance ?? 0} />
              <Field label="Price" value={`${tokenSummary.currency || "NGN"} ${tokenSummary.price_per_credit || "200.00"}`} />
              <Field label="Auto Assign" value={tokenSummary.auto_assign_enabled ? "On" : "Off"} />
              <Field label="Can Login" value={tokenSummary.active_students ?? activeStudents} />
            </article>

            <article className="tile lan-tile">
              <TileHead icon="content" title="Offline Exam Room" />
              <Field label="Status" value={lan.running ? "Running" : "Stopped"} />
              <Field label="Student Address" value={lan.urls?.[0] || "Start room"} />
              <Field label="Published Exams" value={lan.exams?.length || 0} />
              <Field label="Students" value={lan.students?.length || 0} />
            </article>

            <article className="tile client-tile">
              <TileHead icon="client" title="Student App" />
              <Field label="Install From" value="Admin App" />
              <Field label="Installer" value="SchoolDomCBT.exe" />
              <button className="install-button" type="button" onClick={installCbt} disabled={installing}>
                {installing ? "Opening..." : "Install CBT App"}
              </button>
            </article>
          </>
        ) : null}

        {activePage === "room" ? (
          <>
            <article className="hero-panel room-hero">
              <div>
                <p>Router exam mode</p>
                <h2>Publish once, students connect on the same Wi-Fi.</h2>
                <span>{lan.urls?.[0] || "Start the room to generate the student address."}</span>
              </div>
              <div className="hero-actions">
                <button type="button" onClick={startLan}>Start Room</button>
                <button type="button" className="secondary-button" onClick={stopLan}>Stop Room</button>
              </div>
            </article>

            <article className="tile lan-tile">
          <TileHead icon="content" title="Offline Exam Room" />
          <Field label="Status" value={lan.running ? "Running" : "Stopped"} />
          <Field label="Student Address" value={lan.urls?.[0] || "Start room"} />
          <Field label="Published Exams" value={lan.exams?.length || 0} />
          <Field label="Students" value={lan.students?.length || 0} />
          <Field label="Submissions" value={(lan.sessions || []).filter((session) => session.status === "submitted").length} />
          <div className="button-row">
            <button type="button" onClick={startLan}>Start Room</button>
            <button type="button" onClick={stopLan}>Stop Room</button>
          </div>
        </article>

        <article className="tile publish-tile">
          <TileHead icon="test" title="Publish Offline Exam" />
          <form onSubmit={publishLanExam} className="publish-form">
            <div className="form-grid">
              <label>
                Exam Title
                <input value={examForm.title} onChange={(event) => updateExamForm("title", event.target.value)} />
              </label>
              <label>
                Subject
                <input value={examForm.subject} onChange={(event) => updateExamForm("subject", event.target.value)} />
              </label>
              <label>
                Duration Minutes
                <input type="number" min="1" value={examForm.durationMinutes} onChange={(event) => updateExamForm("durationMinutes", event.target.value)} />
              </label>
              <label>
                Exam PIN
                <input type="password" value={examForm.pin} onChange={(event) => updateExamForm("pin", event.target.value)} />
              </label>
            </div>
            <label>
              Students
              <textarea value={examForm.studentsText} onChange={(event) => updateExamForm("studentsText", event.target.value)} rows="4" placeholder={"Leave blank to use fetched active students, or add one per line:\nSD001, Ada Okafor, JSS2"} />
            </label>
            <label>
              Questions
              <textarea value={examForm.questionsText} onChange={(event) => updateExamForm("questionsText", event.target.value)} rows="7" placeholder={"Separate theory questions with blank lines, or paste JSON questions."} />
            </label>
            <label>
              Instructions
              <textarea value={examForm.instructions} onChange={(event) => updateExamForm("instructions", event.target.value)} rows="3" />
            </label>
            <button type="submit" disabled={!examForm.pin.trim()}>Publish to Router</button>
          </form>
        </article>

            <article className="tile sessions-tile">
              <TileHead icon="candidate" title="Live Student Sessions" />
              <div className="session-list">
                {(lan.sessions || []).slice(0, 10).map((session) => (
                  <div key={session.id}>
                    <span>{session.student_id}</span>
                    <strong>{session.status}</strong>
                  </div>
                ))}
                {!lan.sessions?.length ? <p>No student sessions yet.</p> : null}
              </div>
            </article>
          </>
        ) : null}

        {activePage === "students" ? (
          <>
            <article className="hero-panel student-hero">
              <div>
                <p>Activation controlled login</p>
                <h2>Only activated students can enter the CBT room.</h2>
                <span>Fetched students stay available for offline exam sessions.</span>
              </div>
              <div className="hero-metrics">
                <strong>{tokenSummary.active_students ?? activeStudents}<span>Active</span></strong>
                <strong>{tokenSummary.inactive_students ?? inactiveStudents}<span>Inactive</span></strong>
              </div>
            </article>

            <article className="tile token-tile">
              <TileHead icon="school" title="Activation Tokens" />
              <Field label="Balance" value={tokenSummary.balance ?? 0} />
              <Field label="Active Students" value={tokenSummary.active_students ?? activeStudents} />
              <Field label="Inactive Students" value={tokenSummary.inactive_students ?? inactiveStudents} />
              <Field label="Auto Assign" value={tokenSummary.auto_assign_enabled ? "On" : "Off"} />
            </article>

        <article className="tile student-admin-tile">
          <TileHead icon="candidate" title="Offline Students" />
          <form onSubmit={saveStudent} className="publish-form">
            <div className="form-grid">
              <label>
                Student ID
                <input value={studentForm.student_id} onChange={(event) => updateStudentForm("student_id", event.target.value)} />
              </label>
              <label>
                Full Name
                <input value={studentForm.full_name} onChange={(event) => updateStudentForm("full_name", event.target.value)} />
              </label>
              <label>
                Class
                <input value={studentForm.class_name} onChange={(event) => updateStudentForm("class_name", event.target.value)} />
              </label>
              <label>
                Email
                <input value={studentForm.email} onChange={(event) => updateStudentForm("email", event.target.value)} />
              </label>
            </div>
            <label className="checkbox-row">
              <input type="checkbox" checked={studentForm.is_active} onChange={(event) => updateStudentForm("is_active", event.target.checked)} />
              Activated for CBT login
            </label>
            <button type="submit">Save Student</button>
          </form>
          <div className="session-list">
            {(lan.students || []).slice(0, 10).map((student) => (
              <button type="button" key={student.student_id} onClick={() => editStudent(student)}>
                <span>{student.full_name || student.student_id}</span>
                <strong>{student.is_active === false ? "Inactive" : "Active"}</strong>
              </button>
            ))}
            {!lan.students?.length ? <p>No local students yet. Refresh online to fetch school students.</p> : null}
          </div>
        </article>
          </>
        ) : null}

        {activePage === "exams" ? (
          <>
            <article className="hero-panel exam-hero">
              <div>
                <p>Offline exam publishing</p>
                <h2>Prepare questions and publish them to the local network.</h2>
                <span>Fetched web exams are visible here; offline publishing still uses a local exam PIN.</span>
              </div>
            </article>

            <article className="exam-builder-shell">
              <aside className="builder-rail">
                <div className="builder-mark">E</div>
                <strong>Exam Builder</strong>
                {[
                  ["details", "Exam Details"],
                  ["sections", "Sections"],
                  ["questions", "Questions"],
                  ["settings", "Settings"],
                  ["review", "Review"],
                ].map(([key, label]) => (
                  <button key={key} type="button" className={examBuilderStep === key ? "active" : ""} onClick={() => setExamBuilderStep(key)}>
                    {label}
                  </button>
                ))}
              </aside>

              <section className="builder-workspace">
                <header className="builder-head">
                  <div>
                    <h2>Create New Exam</h2>
                    <span>Exams / Create New Exam</span>
                  </div>
                  <div className="builder-actions">
                    <button type="button" className="secondary-button">Preview Exam</button>
                    <button type="button" onClick={publishLanExam} disabled={!examForm.pin.trim()}>Save Exam</button>
                  </div>
                </header>

                <div className="builder-card">
                  <nav className="builder-tabs">
                    {[
                      ["details", "Exam Details"],
                      ["sections", "Sections"],
                      ["questions", "Questions"],
                      ["settings", "Settings"],
                      ["review", "Review"],
                    ].map(([key, label]) => (
                      <button key={key} type="button" className={examBuilderStep === key ? "active" : ""} onClick={() => setExamBuilderStep(key)}>
                        {label}
                      </button>
                    ))}
                  </nav>

                  {examBuilderStep === "details" ? (
                    <div className="builder-pane">
                      <div className="form-grid three">
                        <label>
                          Exam Title
                          <input value={examForm.title} onChange={(event) => updateExamForm("title", event.target.value)} />
                        </label>
                        <label>
                          Exam Code
                          <input placeholder="Optional" />
                        </label>
                        <label>
                          Subject
                          <input value={examForm.subject} onChange={(event) => updateExamForm("subject", event.target.value)} placeholder="General" />
                        </label>
                      </div>
                      <label>
                        Description
                        <textarea rows="5" value={examForm.instructions} onChange={(event) => updateExamForm("instructions", event.target.value)} />
                      </label>
                      <div className="form-grid three">
                        <label>
                          Class / Course
                          <select value="" onChange={() => null}>
                            <option value="">All classes</option>
                            {localClasses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                          </select>
                        </label>
                        <label>
                          Exam Date
                          <input type="date" />
                        </label>
                        <label>
                          Duration
                          <input type="number" min="1" value={examForm.durationMinutes} onChange={(event) => updateExamForm("durationMinutes", event.target.value)} />
                        </label>
                      </div>
                    </div>
                  ) : null}

                  {examBuilderStep === "sections" ? (
                    <div className="builder-pane split-pane">
                      <article>
                        <h3>Sections</h3>
                        <p>Use sections for objective, theory, practical, or subject groups.</p>
                        <div className="builder-list">
                          <div><span>Section A</span><strong>Objective</strong></div>
                          <div><span>Section B</span><strong>Theory</strong></div>
                        </div>
                      </article>
                      <article>
                        <h3>Section Settings</h3>
                        <div className="form-grid">
                          <label>Section Name<input placeholder="Section A" /></label>
                          <label>Marks<input type="number" min="1" placeholder="40" /></label>
                        </div>
                      </article>
                    </div>
                  ) : null}

                  {examBuilderStep === "questions" ? (
                    <div className="builder-pane">
                      <div className="question-bank-panel">
                        <div>
                          <h3>CBT question bank</h3>
                          <p>Import preloaded CBT questions for this exam. Quiz questions are kept separate.</p>
                          <span>No CBT bank questions found for this subject.</span>
                        </div>
                        <div className="builder-actions vertical">
                          <button type="button" className="secondary-button">Refresh bank</button>
                          <button type="button" className="secondary-button">Add selected</button>
                        </div>
                      </div>

                      <div className="question-bank-panel">
                        <div>
                          <h3>Import standard questions</h3>
                          <p>Teachers and admins can paste or upload MCQs from common school question formats.</p>
                        </div>
                        <div className="builder-actions vertical">
                          <label className="file-button">
                            Choose file
                            <input type="file" accept=".txt,.csv,.json,.docx,.doc,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword" onChange={handleQuestionFile} />
                          </label>
                          <button type="button" className="secondary-button" onClick={importQuestions}>Import questions</button>
                        </div>
                        <textarea className="import-area" value={examForm.questionsText} onChange={(event) => updateExamForm("questionsText", event.target.value)} rows="8" placeholder={"1. What is the capital of France?\nA. Paris\nB. Lagos\nC. Rome\nD. Madrid\nAnswer: A"} />
                      </div>

                      <div className="question-toolbar">
                        <strong>{questionCount} question{questionCount === 1 ? "" : "s"}</strong>
                        <button type="button" onClick={addQuestion}>Add New Question</button>
                      </div>

                      {questionItems.map((question, index) => (
                        <div className="question-editor-card" key={question.id}>
                          <div className="question-card-head">
                            <strong>Question {index + 1}</strong>
                            <button type="button" className="secondary-button" onClick={() => removeQuestion(question.id)}>Delete Question</button>
                          </div>
                          <label>
                            Question
                            <textarea rows="4" value={question.text} onChange={(event) => updateQuestion(question.id, { text: event.target.value })} placeholder="Enter the question text here" />
                          </label>
                          <div className="form-grid question-meta">
                            <label>
                              Type
                              <select value={question.type} onChange={(event) => updateQuestion(question.id, { type: event.target.value })}>
                                <option value="mcq">Objective MCQ</option>
                                <option value="true_false">True / False</option>
                                <option value="short_answer">Short Answer</option>
                                <option value="essay">Essay</option>
                              </select>
                            </label>
                            <label>
                              Marks
                              <input type="number" min="1" value={question.marks} onChange={(event) => updateQuestion(question.id, { marks: event.target.value })} />
                            </label>
                          </div>
                          <label>
                            Question image
                            <input type="file" accept="image/*" onChange={(event) => updateQuestion(question.id, { imageName: event.target.files?.[0]?.name || "" })} />
                          </label>
                          <div className="passage-group-box">
                            <label>
                              Passage / group
                              <select value={question.group} onChange={(event) => updateQuestion(question.id, { group: event.target.value })}>
                                <option value="">Standalone question</option>
                                <option value="new">New passage group</option>
                              </select>
                            </label>
                            <button type="button" className="secondary-button" onClick={() => updateQuestion(question.id, { group: "new" })}>New passage group</button>
                          </div>
                          <div className="form-grid">
                            {["A", "B", "C", "D"].map((key) => (
                              <label key={key}>Option {key}<input value={question.options[key]} onChange={(event) => updateQuestionOption(question.id, key, event.target.value)} placeholder={`Answer option ${key}`} /></label>
                            ))}
                          </div>
                          <div className="form-grid question-meta">
                            <label>
                              Correct answer
                              <select value={question.correctAnswer} onChange={(event) => updateQuestion(question.id, { correctAnswer: event.target.value })}>
                                <option>A</option>
                                <option>B</option>
                                <option>C</option>
                                <option>D</option>
                              </select>
                            </label>
                            <label>
                              Explanation
                              <input value={question.explanation} onChange={(event) => updateQuestion(question.id, { explanation: event.target.value })} placeholder="Optional explanation" />
                            </label>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {examBuilderStep === "settings" ? (
                    <div className="builder-pane">
                      <div className="form-grid three">
                        <label>
                          Exam PIN
                          <input type="password" value={examForm.pin} onChange={(event) => updateExamForm("pin", event.target.value)} />
                        </label>
                        <label>
                          Students
                          <select>
                            <option>Fetched active students</option>
                            <option>Manual list</option>
                          </select>
                        </label>
                        <label>
                          Shuffle Questions
                          <select>
                            <option>Yes</option>
                            <option>No</option>
                          </select>
                        </label>
                      </div>
                      <label>
                        Manual Students
                        <textarea value={examForm.studentsText} onChange={(event) => updateExamForm("studentsText", event.target.value)} rows="6" placeholder={"Leave blank to use fetched active students, or add one per line:\nSD001, Ada Okafor, JSS2"} />
                      </label>
                    </div>
                  ) : null}

                  {examBuilderStep === "review" ? (
                    <div className="builder-pane split-pane">
                      <article>
                        <h3>{examForm.title || "Untitled Exam"}</h3>
                        <Field label="Subject" value={examForm.subject || "General"} />
                        <Field label="Duration" value={`${examForm.durationMinutes} minutes`} />
                        <Field label="Questions" value={questionCount} />
                        <Field label="Eligible Students" value={localStudents.length} />
                      </article>
                      <article>
                        <h3>Ready to Publish</h3>
                        <p>Saving publishes the exam to the offline router room for student CBT apps.</p>
                        <button type="button" onClick={publishLanExam} disabled={!examForm.pin.trim()}>Publish to Router</button>
                      </article>
                    </div>
                  ) : null}
                </div>
              </section>
            </article>

            <article className="tile test-tile">
              <TileHead icon="test" title="Fetched Exams" />
              <Field label="Total" value={localExams.length || test.total || 0} />
              <Field label="Published" value={test.licensed ?? 0} />
              <Field label="Ongoing" value={test.ongoing ?? 0} />
              <Field label="Submitted" value={test.submitted ?? 0} />
            </article>
            <article className="tile sessions-tile">
              <TileHead icon="test" title="Exam List" />
              <div className="session-list">
                {localExams.slice(0, 16).map((exam) => (
                  <div key={exam.id}>
                    <span>{exam.title}</span>
                    <strong>{exam.class_name || exam.subject || "Exam"}</strong>
                  </div>
                ))}
                {!localExams.length ? <p>No fetched exams yet. Refresh online to fetch exam data.</p> : null}
              </div>
            </article>
          </>
        ) : null}

        {activePage === "school" ? (
          <>
            <article className="hero-panel school-hero">
              <div>
                <p>School identity</p>
                <h2>{school.name || "SchoolDom"}</h2>
                <span>{school.address || school.email || "School profile loaded from SchoolDom."}</span>
              </div>
              <div className="school-logo hero-logo">
                {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{initials(school.name)}</span>}
              </div>
            </article>

            <article className="tile school-tile">
              <TileHead icon="school" title="School Details" />
              <div className="school-logo">
                {school.logo ? <img src={school.logo} alt={`${school.name} logo`} /> : <span>{initials(school.name)}</span>}
              </div>
              {schoolDetails.map(([label, value]) => <Field key={label} label={label} value={value} />)}
            </article>
            <article className="tile content-tile">
              <TileHead icon="content" title="Classes" />
              <div className="session-list">
                {localClasses.slice(0, 20).map((item) => (
                  <div key={item.id}>
                    <span>{item.name}</span>
                    <strong>{item.section || "Class"}</strong>
                  </div>
                ))}
                {!localClasses.length ? <p>No fetched classes yet.</p> : null}
              </div>
            </article>
          </>
        ) : null}

        {activePage === "install" ? (
          <>
            <article className="hero-panel install-hero">
              <div>
                <p>Desktop settings</p>
                <h2>Match the web settings here for the offline admin app.</h2>
                <span>These desktop settings are saved locally. Cloud school changes still happen on the website.</span>
              </div>
            </article>

            <article className="tile client-tile">
              <TileHead icon="client" title="Student CBT Installer" />
              <Field label="Install From" value="Admin App" />
              <Field label="File" value="SchoolDomCBT.exe" />
              <button className="install-button" type="button" onClick={installCbt} disabled={installing}>
                {installing ? "Opening..." : "Install CBT App"}
              </button>
            </article>

            <article className="tile settings-tile">
              <TileHead icon="gear" title="Website-style Settings" />
              <form onSubmit={saveAndRefresh} className="settings-form">
                <div className="theme-switcher">
                  <span>Interface Theme</span>
                  <div className="segmented-control">
                    <button type="button" className={themePreference === "light" ? "active" : ""} onClick={() => setThemePreference("light")}>Light</button>
                    <button type="button" className={themePreference === "dark" ? "active" : ""} onClick={() => setThemePreference("dark")}>Dark</button>
                  </div>
                </div>
                <div className="settings-logo-field">
                  <div className="school-logo">
                    {settingsForm.logo ? <img src={settingsForm.logo} alt={`${settingsForm.name || "School"} logo`} /> : <span>{initials(settingsForm.name)}</span>}
                  </div>
                  <label>
                    School Logo URL
                    <input value={settingsForm.logo} onChange={(event) => updateSettingsForm("logo", event.target.value)} placeholder="https://..." />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    School Name
                    <input value={settingsForm.name} onChange={(event) => updateSettingsForm("name", event.target.value)} />
                  </label>
                  <label>
                    School Code
                    <input value={schoolCode} onChange={(event) => setSchoolCode(event.target.value)} placeholder="Optional" />
                  </label>
                  <label>
                    Email
                    <input value={settingsForm.email} onChange={(event) => updateSettingsForm("email", event.target.value)} />
                  </label>
                  <label>
                    Phone
                    <input value={settingsForm.phone} onChange={(event) => updateSettingsForm("phone", event.target.value)} />
                  </label>
                </div>
                <label>
                  Address
                  <textarea rows="3" value={settingsForm.address} onChange={(event) => updateSettingsForm("address", event.target.value)} />
                </label>
                <div className="form-grid">
                  <label>
                    Academic Year
                    <input value={settingsForm.academicYearName} onChange={(event) => updateSettingsForm("academicYearName", event.target.value)} placeholder="2026/2027" />
                  </label>
                  <label>
                    Academic Year Start
                    <input type="date" value={settingsForm.academicYearStart} onChange={(event) => updateSettingsForm("academicYearStart", event.target.value)} />
                  </label>
                  <label>
                    Academic Year End
                    <input type="date" value={settingsForm.academicYearEnd} onChange={(event) => updateSettingsForm("academicYearEnd", event.target.value)} />
                  </label>
                  <label>
                    Active Term
                    <input value={settingsForm.termName} onChange={(event) => updateSettingsForm("termName", event.target.value)} placeholder="First Term" />
                  </label>
                  <label>
                    Term Start
                    <input type="date" value={settingsForm.termStart} onChange={(event) => updateSettingsForm("termStart", event.target.value)} />
                  </label>
                  <label>
                    Term End
                    <input type="date" value={settingsForm.termEnd} onChange={(event) => updateSettingsForm("termEnd", event.target.value)} />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    Server URL
                    <input value={serverUrl} onChange={(event) => setServerUrl(event.target.value)} />
                  </label>
                  <label>
                    Server Host
                    <input value={settings.ip_address || hostFromUrl(serverUrl)} disabled />
                  </label>
                </div>
                <div className="support-box">
                  <strong>Support Center</strong>
                  <div className="form-grid">
                    <label>
                      Subject
                      <input value={settingsForm.supportSubject} onChange={(event) => updateSettingsForm("supportSubject", event.target.value)} placeholder="What do you need help with?" />
                    </label>
                    <label>
                      Contact Email
                      <input value={settingsForm.email} onChange={(event) => updateSettingsForm("email", event.target.value)} />
                    </label>
                  </div>
                  <label>
                    Message
                    <textarea rows="3" value={settingsForm.supportMessage} onChange={(event) => updateSettingsForm("supportMessage", event.target.value)} />
                  </label>
                </div>
                <button type="submit">Save Desktop Settings</button>
              </form>
            </article>
          </>
        ) : null}
      </div>
        </section>
      </div>

      {notice || error ? (
        <div className={`toast ${error ? "error" : ""}`}>
          {error || notice}
          <button type="button" onClick={() => { setError(""); setNotice(""); }}>Dismiss</button>
        </div>
      ) : null}
    </main>
  );
}

function Field({ label, value }) {
  return (
    <div className="field-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TileHead({ icon, title }) {
  return (
    <header className="tile-head">
      <span className={`tile-icon ${icon}`} aria-hidden="true" />
      <h2>{title}</h2>
    </header>
  );
}
