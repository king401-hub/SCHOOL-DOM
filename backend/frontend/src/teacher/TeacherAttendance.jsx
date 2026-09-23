// Attendance: pick a class, tap (or press) a status for each student and the
// register fills itself in. Every tap saves straight away, marked students can be
// re-opened from the register to correct them, and ID-card scanning sits below.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarCheck,
  Check,
  Clock3,
  Download,
  ScanLine,
  Search,
  ShieldCheck,
  SkipForward,
  Smartphone,
  Users,
  X,
} from "lucide-react";
import { Spinner, requestJson } from "../AppShared";
import { IdCardAttendanceScanner } from "../components/Attendance";
import {
  Avatar,
  EmptyState,
  PageHeader,
  ProgressRing,
  SectionCard,
  Skeleton,
  formatLongDate,
  pluralize,
  toneIndex,
  useHotkey,
} from "./TeacherKit";

const STATUSES = [
  { key: "present", label: "Present", hotkey: "P", icon: Check, tone: "emerald" },
  { key: "late", label: "Late", hotkey: "L", icon: Clock3, tone: "amber" },
  { key: "excused", label: "Excused", hotkey: "E", icon: ShieldCheck, tone: "sky" },
  { key: "absent", label: "Absent", hotkey: "A", icon: X, tone: "rose" },
];
const STATUS_BY_KEY = Object.fromEntries(STATUSES.map((status) => [status.key, status]));
const HOTKEYS = Object.fromEntries(STATUSES.map((status) => [status.hotkey.toLowerCase(), status.key]));

const localISODate = (date = new Date()) => {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
};

const initialsOf = (name) => String(name || "?").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();

function ScannerAppCard() {
  return (
    <a className="ts-scanner-app" href="/app/download/apk/">
      <span className="ts-scanner-app__icon" aria-hidden="true"><Smartphone size={20} /></span>
      <span className="ts-scanner-app__text">
        <strong>Prefer your phone?</strong>
        <small>Get the SchoolDom Scanner app to scan ID cards at the gate or in class.</small>
      </span>
      <span className="ts-scanner-app__cta"><Download size={15} aria-hidden="true" /> Android app</span>
    </a>
  );
}

/** ID-card scanner wrapped as a section of the page. */
function ScanSection({ session }) {
  return (
    <SectionCard
      className="ts-scan"
      icon={ScanLine}
      title="Scan ID cards"
      subtitle="Point a camera at the QR code on a student's ID card to clock them in or out."
    >
      <IdCardAttendanceScanner session={session} title="Scanner" subtitle="" />
    </SectionCard>
  );
}

export function TeacherAttendanceInfo({ session }) {
  return (
    <div className="ts-att">
      <PageHeader
        eyebrow="Classroom"
        title="Attendance"
        subtitle="Here's how student attendance works at your school."
        icon={CalendarCheck}
        tone="emerald"
      />
      <SectionCard title="Two easy ways to record attendance" subtitle="Students and teachers can both do it">
        <ol className="ts-steps">
          <li>
            <span className="ts-steps__n">1</span>
            <div>
              <strong>Students scan in themselves</strong>
              <p>Students mark attendance from their own Attendance page using the student QR scanner.</p>
            </div>
          </li>
          <li>
            <span className="ts-steps__n">2</span>
            <div>
              <strong>You scan their ID card</strong>
              <p>Scan the QR code on the back of a student's SchoolDom ID card to confirm who they are and mark them present.</p>
            </div>
          </li>
        </ol>
      </SectionCard>
      <ScanSection session={session} />
      <ScannerAppCard />
    </div>
  );
}

export default function TeacherAttendance({ session, classOptions = [] }) {
  const [classId, setClassId] = useState("");
  const [students, setStudents] = useState([]);
  const [history, setHistory] = useState([]);
  const [date, setDate] = useState(() => localISODate());
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [focusId, setFocusId] = useState("");
  const [skipped, setSkipped] = useState([]);
  const [saving, setSaving] = useState("");
  const [bulk, setBulk] = useState({ state: "idle", done: 0, total: 0 });
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const toastTimer = useRef(null);
  const confirmTimer = useRef(null);
  const stageRef = useRef(null);

  useEffect(() => {
    if (!classId && classOptions.length) setClassId(String(classOptions[0].id));
  }, [classId, classOptions]);

  useEffect(() => () => {
    window.clearTimeout(toastTimer.current);
    window.clearTimeout(confirmTimer.current);
  }, []);

  const selectedClass = classOptions.find((item) => String(item.id) === String(classId));
  const className = selectedClass ? selectedClass.label || selectedClass.name : "";

  const load = useCallback(async () => {
    setError("");
    if (!classId) {
      setStudents([]);
      setHistory([]);
      return;
    }
    setLoading(true);
    // never leave the previous class's students tappable while the next loads
    setStudents([]);
    setHistory([]);
    try {
      const params = new URLSearchParams({ class_id: classId, date });
      const result = await requestJson(session, "GET", `/api/app/attendance/class-students/?${params.toString()}`);
      setStudents(result.students || []);
      setHistory(result.attendance_records || []);
      setFocusId("");
      setSkipped([]);
    } catch (loadError) {
      setError(loadError.message || "We couldn't load this class. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [classId, date, session]);

  useEffect(() => {
    if (session) load();
  }, [load, session]);

  const statusById = useMemo(() => new Map(history.map((item) => [item.student_id, item.status])), [history]);
  const pending = useMemo(() => students.filter((student) => !statusById.has(student.student_id)), [students, statusById]);
  const queue = useMemo(() => {
    const skippedSet = new Set(skipped);
    return [...pending.filter((s) => !skippedSet.has(s.student_id)), ...pending.filter((s) => skippedSet.has(s.student_id))];
  }, [pending, skipped]);

  const focused = focusId ? students.find((student) => student.student_id === focusId) : null;
  const active = focused || queue[0] || null;
  const activeStatus = active ? statusById.get(active.student_id) : null;
  const markedCount = students.length - pending.length;
  const counts = useMemo(() => {
    const tally = { present: 0, late: 0, excused: 0, absent: 0 };
    history.forEach((item) => {
      if (tally[item.status] !== undefined) tally[item.status] += 1;
    });
    return tally;
  }, [history]);
  const complete = students.length > 0 && pending.length === 0;
  const percent = students.length ? Math.round((markedCount / students.length) * 100) : 0;

  const flash = (message) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  };

  const save = useCallback(
    async (student, status) => {
      const result = await requestJson(session, "POST", "/api/app/attendance/teacher-mark/", {
        student_id: student.student_id,
        class_id: classId,
        status,
        date,
      });
      const record = result.attendance || { id: `local-${student.student_id}`, student_id: student.student_id, student_name: student.name, status, date };
      setHistory((previous) => [record, ...previous.filter((item) => item.student_id !== student.student_id)]);
      return result;
    },
    [classId, date, session]
  );

  const mark = useCallback(
    async (status) => {
      if (!active || saving || bulk.state === "running") return;
      setError("");
      setSaving(status);
      const student = active;
      try {
        await save(student, status);
        flash(`${student.name} · ${STATUS_BY_KEY[status].label}`);
        setFocusId("");
      } catch (markError) {
        setError(markError.message || "That didn't save. Please try again.");
      } finally {
        setSaving("");
      }
    },
    [active, bulk.state, save, saving]
  );

  const skip = () => {
    if (!active || pending.length < 2) return;
    setSkipped((previous) => [...previous.filter((id) => id !== active.student_id), active.student_id]);
    setFocusId("");
  };

  const runBulk = async () => {
    const targets = queue.slice();
    if (!targets.length) return;
    setError("");
    setBulk({ state: "running", done: 0, total: targets.length });
    try {
      for (let index = 0; index < targets.length; index += 1) {
        // eslint-disable-next-line no-await-in-loop
        await save(targets[index], "present");
        setBulk({ state: "running", done: index + 1, total: targets.length });
      }
      flash(`${pluralize(targets.length, "student")} marked present`);
      setFocusId("");
    } catch (bulkError) {
      setError(bulkError.message || "We couldn't finish. The students already saved are kept.");
    } finally {
      setBulk({ state: "idle", done: 0, total: 0 });
    }
  };

  const askBulk = () => {
    if (bulk.state === "confirm") {
      window.clearTimeout(confirmTimer.current);
      setBulk({ state: "idle", done: 0, total: 0 });
      runBulk();
      return;
    }
    setBulk({ state: "confirm", done: 0, total: 0 });
    window.clearTimeout(confirmTimer.current);
    confirmTimer.current = window.setTimeout(() => setBulk({ state: "idle", done: 0, total: 0 }), 4500);
  };

  // P / L / E / A while nobody is typing
  const keyMatcher = useCallback(
    (event) => !event.ctrlKey && !event.metaKey && !event.altKey && Boolean(HOTKEYS[String(event.key || "").toLowerCase()]),
    []
  );
  useHotkey(keyMatcher, (event) => {
    event.preventDefault();
    mark(HOTKEYS[event.key.toLowerCase()]);
  }, { enabled: Boolean(active) });

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return students.filter((student) => {
      const status = statusById.get(student.student_id);
      if (filter === "todo" && status) return false;
      if (filter === "marked" && !status) return false;
      if (!query) return true;
      return [student.name, student.student_id, student.email].filter(Boolean).join(" ").toLowerCase().includes(query);
    });
  }, [students, statusById, search, filter]);

  const isToday = date === localISODate();
  const dateLabel = useMemo(() => {
    const parsed = new Date(`${date}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? date : formatLongDate(parsed);
  }, [date]);

  const header = (
    <PageHeader
      eyebrow="Classroom"
      title="Attendance"
      subtitle="Pick a class and tap a status for each student. Every tap saves instantly."
      icon={CalendarCheck}
      tone="emerald"
    />
  );

  if (!classOptions.length) {
    return (
      <div className="ts-att">
        {header}
        <SectionCard>
          <EmptyState
            art="clipboard"
            title="You haven't been given a class yet"
            message="Once your school admin assigns you to a class, its register will appear here, ready to tap through."
          />
        </SectionCard>
        <ScanSection session={session} />
        <ScannerAppCard />
      </div>
    );
  }

  return (
    <div className="ts-att">
      {header}

      <SectionCard className="ts-att-controls">
        <div className="ts-att-controls__row">
          <div className="ts-att-controls__pick">
            <p className="ts-mini-label" id="att-class-label">Class</p>
            <div className="ts-classes" role="group" aria-labelledby="att-class-label">
              {classOptions.map((item) => {
                const label = item.label || item.name;
                const on = String(item.id) === String(classId);
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`ts-classes__item${on ? " is-on" : ""}`}
                    data-tone={toneIndex(label)}
                    aria-pressed={on}
                    onClick={() => setClassId(String(item.id))}
                  >
                    <i aria-hidden="true" />
                    {label}
                  </button>
                );
              })}
            </div>
            <label className="ts-att-date">
              <span className="ts-mini-label">Date</span>
              <span className="ts-att-date__field">
                <input type="date" value={date} max={localISODate()} onChange={(event) => event.target.value && setDate(event.target.value)} />
                {!isToday ? <button type="button" className="ts-link" onClick={() => setDate(localISODate())}>Back to today</button> : null}
              </span>
            </label>
          </div>

          <div className="ts-att-progress" aria-live="polite">
            <ProgressRing value={percent} size={92} stroke={9} label={`${markedCount}/${students.length}`} sublabel="marked" tone={complete ? "emerald" : "indigo"} />
            <div className="ts-att-counts">
              {STATUSES.map((status) => (
                <span key={status.key} className="ts-att-count" data-tone={status.tone}>
                  <i aria-hidden="true" />
                  <b>{counts[status.key]}</b> {status.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </SectionCard>

      {error ? <p className="form-feedback error" role="alert">{error}</p> : null}

      {loading && !students.length ? (
        <div className="ts-att-main">
          <SectionCard><Skeleton width="100%" height={340} radius={18} /></SectionCard>
          <SectionCard><Skeleton width="100%" height={340} radius={18} /></SectionCard>
        </div>
      ) : students.length === 0 ? (
        <SectionCard>
          <EmptyState
            art="clipboard"
            title="No students in this class yet"
            message={`${className || "This class"} doesn't have any students on its roll. Once they're added, they'll appear here.`}
          />
        </SectionCard>
      ) : (
        <div className="ts-att-main">
          <section className={`ts-stage${complete && !focused ? " is-complete" : ""}`} aria-label="Mark attendance" ref={stageRef}>
            {complete && !focused ? (
              <div className="ts-stage__done">
                <EmptyState
                  art="check"
                  title="Register complete"
                  message={`Everyone in ${className || "this class"} is marked for ${isToday ? "today" : dateLabel}. Tap a student in the register to correct a mark.`}
                />
                <div className="ts-stage__summary">
                  {STATUSES.map((status) => (
                    <span key={status.key} data-tone={status.tone}><b>{counts[status.key]}</b>{status.label}</span>
                  ))}
                </div>
              </div>
            ) : active ? (
              <>
                <div className="ts-stage__top">
                  <span className="ts-stage__count">
                    {focused && activeStatus ? "Correcting a mark" : `Student ${markedCount + 1} of ${students.length}`}
                  </span>
                  {focused ? (
                    <button type="button" className="ts-link" onClick={() => setFocusId("")}>Back to the queue</button>
                  ) : pending.length > 1 ? (
                    <button type="button" className="ts-link" onClick={skip}><SkipForward size={14} aria-hidden="true" /> Skip for now</button>
                  ) : null}
                </div>

                <div className="ts-stage__who" key={active.student_id} data-tone={toneIndex(active.name)}>
                  <Avatar name={active.name || "Student"} src={active.profile_picture || active.photo || ""} size={104} />
                  <h2>{active.name || "Student"}</h2>
                  <p>
                    {active.student_id ? <span className="ts-stage__id">{active.student_id}</span> : null}
                    {active.class_name || className ? <span>{active.class_name || className}</span> : null}
                  </p>
                  {activeStatus ? (
                    <span className={`ts-stage__current status-${activeStatus}`}>Marked {STATUS_BY_KEY[activeStatus]?.label.toLowerCase() || activeStatus}</span>
                  ) : null}
                </div>

                <div className="ts-stage__actions">
                  {STATUSES.map((status) => {
                    const Icon = status.icon;
                    return (
                      <button
                        key={status.key}
                        type="button"
                        className={`ts-mark${activeStatus === status.key ? " is-current" : ""}`}
                        data-tone={status.tone}
                        onClick={() => mark(status.key)}
                        disabled={Boolean(saving) || bulk.state === "running"}
                      >
                        <span className="ts-mark__icon" aria-hidden="true">
                          {saving === status.key ? <Spinner size={16} /> : <Icon size={20} strokeWidth={2.2} />}
                        </span>
                        <span className="ts-mark__label">{status.label}</span>
                        <kbd className="ts-kbd">{status.hotkey}</kbd>
                      </button>
                    );
                  })}
                </div>

                <p className="ts-stage__hint">
                  Tap a status
                  <span className="ts-stage__keys"> or press <kbd className="ts-kbd">P</kbd> <kbd className="ts-kbd">L</kbd> <kbd className="ts-kbd">E</kbd> <kbd className="ts-kbd">A</kbd></span>
                  . Marked students leave the queue.
                </p>
              </>
            ) : null}

            <p className="ts-stage__toast" role="status" aria-live="polite">{toast ? <><Check size={14} aria-hidden="true" /> {toast}</> : ""}</p>

            {pending.length > 1 && !complete ? (
              <div className="ts-stage__bulk">
                <button
                  type="button"
                  className={`ts-btn ${bulk.state === "confirm" ? "ts-btn--primary" : "ts-btn--ghost"}`}
                  onClick={askBulk}
                  disabled={bulk.state === "running"}
                >
                  {bulk.state === "running" ? (
                    <><Spinner size={13} /> Saving {bulk.done}/{bulk.total}…</>
                  ) : bulk.state === "confirm" ? (
                    <>Tap again to mark {pluralize(queue.length, "student")} present</>
                  ) : (
                    <><Users size={15} aria-hidden="true" /> Mark everyone left as present</>
                  )}
                </button>
              </div>
            ) : null}
          </section>

          <SectionCard
            className="ts-register"
            title="Register"
            subtitle={`${className}${className ? " · " : ""}${dateLabel}`}
            action={<span className="pill">{pluralize(students.length, "student")}</span>}
          >
            <div className="ts-register__tools">
              <label className="ts-search">
                <Search size={15} aria-hidden="true" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Find a student"
                  aria-label="Find a student in this class"
                />
              </label>
              <div className="segmented-control" role="group" aria-label="Filter the register">
                {[["all", "All"], ["todo", `To mark · ${pending.length}`], ["marked", `Marked · ${markedCount}`]].map(([key, label]) => (
                  <button key={key} type="button" className={filter === key ? "active" : ""} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>
                ))}
              </div>
            </div>

            {rows.length === 0 ? (
              <p className="panel-empty">{search ? "No student matches that search." : filter === "todo" ? "Nobody left to mark." : "Nobody's been marked yet."}</p>
            ) : (
              <ul className="ts-roll">
                {rows.map((student) => {
                  const status = statusById.get(student.student_id);
                  const isActive = active && active.student_id === student.student_id;
                  return (
                    <li key={student.id || student.student_id}>
                      <button
                        type="button"
                        className={`ts-roll__row${isActive ? " is-active" : ""}`}
                        data-tone={toneIndex(student.name)}
                        aria-current={isActive ? "true" : undefined}
                        onClick={() => {
                          setFocusId(student.student_id);
                          stageRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
                        }}
                      >
                        <span className="ts-roll__avatar" aria-hidden="true">{initialsOf(student.name)}</span>
                        <span className="ts-roll__name">
                          <strong>{student.name || "Student"}</strong>
                          <small>{student.student_id}</small>
                        </span>
                        {status ? (
                          <span className={`ts-roll__status status-${status}`}>{STATUS_BY_KEY[status]?.label || status}</span>
                        ) : (
                          <span className="ts-roll__status is-todo">To mark</span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </SectionCard>
        </div>
      )}

      <ScanSection session={session} />
      <ScannerAppCard />
    </div>
  );
}
