// The teacher's "today" screen: a greeting that knows what needs attention,
// live "now / next" timetable, the numbers that matter and one-tap shortcuts.
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Briefcase,
  CalendarCheck,
  CalendarClock,
  Check,
  ClipboardList,
  FileCheck,
  FilePlus2,
  FileSignature,
  Hourglass,
  Inbox,
  LayoutDashboard,
  MessageCircle,
  Pencil,
  Sparkles,
  Trophy,
} from "lucide-react";
import { CurrentTermBadge, requestJson } from "../AppShared";
import {
  Avatar,
  CountUp,
  EmptyState,
  SectionCard,
  Skeleton,
  formatLongDate,
  friendlyName,
  greetingFor,
  pluralize,
  stagger,
  timeAgo,
  toneIndex,
} from "./TeacherKit";

const NAIRA = "₦";

/* ------------------------------------------------------------- timetable */

const toMinutes = (value) => {
  const [hours, minutes] = String(value || "").split(":").map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours * 60 + minutes : null;
};

const clock = (value) => {
  const minutes = toMinutes(value);
  if (minutes === null) return "";
  const hours24 = Math.floor(minutes / 60);
  const suffix = hours24 >= 12 ? "pm" : "am";
  const hours12 = hours24 % 12 || 12;
  return `${hours12}:${String(minutes % 60).padStart(2, "0")} ${suffix}`;
};

/** Loads the teacher's timetable once and works out today's lessons, which one
 *  is running now and what comes next (re-evaluated every 30s). */
function useTodaySchedule(session) {
  const [state, setState] = useState({ loading: true, entries: [], activities: [], error: "" });
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!session) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const result = await requestJson(session, "GET", "/api/app/timetables/");
        if (!cancelled) {
          setState({ loading: false, entries: result?.entries || [], activities: result?.school_activities || [], error: "" });
        }
      } catch (error) {
        if (!cancelled) setState({ loading: false, entries: [], activities: [], error: error.message || "" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  return useMemo(() => {
    const dayIndex = (now.getDay() + 6) % 7; // Monday = 0, as the API numbers days
    const minutesNow = now.getHours() * 60 + now.getMinutes();
    const lessons = state.entries
      .filter((entry) => entry.day_of_week === dayIndex)
      .sort((a, b) => (toMinutes(a.start_time) ?? 0) - (toMinutes(b.start_time) ?? 0))
      .map((entry) => {
        const start = toMinutes(entry.start_time);
        const end = toMinutes(entry.end_time);
        let status = "later";
        if (start !== null && end !== null) {
          if (minutesNow >= end) status = "done";
          else if (minutesNow >= start) status = "now";
        }
        const progress = status === "now" && end > start ? Math.round(((minutesNow - start) / (end - start)) * 100) : 0;
        return { ...entry, status, progress };
      });
    const current = lessons.find((lesson) => lesson.status === "now") || null;
    const next = lessons.find((lesson) => lesson.status === "later") || null;
    return {
      loading: state.loading,
      error: state.error,
      hasTimetable: state.entries.length > 0,
      lessons,
      current,
      next,
      activities: state.activities,
    };
  }, [state, now]);
}

/* -------------------------------------------------------------- helpers */

function normaliseSubjects(profile, subjectOptions) {
  if (Array.isArray(profile.subjects) && profile.subjects.length) {
    return profile.subjects.map((subject, index) =>
      typeof subject === "string" ? { id: `s-${index}`, name: subject } : subject
    );
  }
  if (Array.isArray(profile.subjects_taught) && profile.subjects_taught.length) {
    const wanted = profile.subjects_taught.map((name) => String(name || "").trim().toLowerCase()).filter(Boolean);
    const matched = subjectOptions.filter((subject) => wanted.includes(String(subject.name || "").trim().toLowerCase()));
    return matched.length ? matched : wanted.map((name, index) => ({ id: `s-${index}`, name }));
  }
  if (typeof profile.subjects === "string" && profile.subjects.trim()) {
    return profile.subjects
      .split(/[,;]/)
      .map((name, index) => ({ id: `s-${index}`, name: name.trim() }))
      .filter((item) => item.name);
  }
  return [];
}

function dayParts(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfThat = new Date(date);
  startOfThat.setHours(0, 0, 0, 0);
  const days = Math.round((startOfThat - startOfToday) / 86400000);
  return {
    day: date.getDate(),
    month: date.toLocaleDateString(undefined, { month: "short" }),
    relative: days === 0 ? "Today" : days === 1 ? "Tomorrow" : days > 1 && days < 31 ? `In ${days} days` : days < 0 ? "Started" : date.toLocaleDateString(undefined, { day: "numeric", month: "short" }),
  };
}

const money = (value) => `${NAIRA}${Number(value || 0).toLocaleString()}`;

/** The API sends placeholders like "Not specified" for empty profile fields; show nothing instead. */
const clean = (value) => {
  const text = String(value ?? "").trim();
  return /^(not specified|n\/a|none|null|-|—)$/i.test(text) ? "" : text;
};

const cleanSubject = (value) => String(value ?? "").trim();

/** One sentence about what's on today's plate. */
function focusSentence({ pending, upcoming, unread, lessonsToday, loadingSchedule }) {
  const parts = [];
  if (!loadingSchedule && lessonsToday > 0) parts.push(`${pluralize(lessonsToday, "class", "classes")} today`);
  if (pending > 0) parts.push(`${pluralize(pending, "written answer")} to mark`);
  if (upcoming > 0) parts.push(`${pluralize(upcoming, "exam")} coming up`);
  if (unread > 0) parts.push(`${pluralize(unread, "unread message")}`);
  if (!parts.length) return "You're all caught up. A good moment to plan ahead.";
  const last = parts.pop();
  return parts.length ? `${parts.join(", ")} and ${last}.` : `${last[0].toUpperCase()}${last.slice(1)}.`;
}

/* ---------------------------------------------------------------- pieces */

function StatTile({ index, tone, icon: Icon, label, value, foot, onClick, attention = false, decimals = 0, suffix = "" }) {
  return (
    <button
      type="button"
      className={`ts-stat ts-reveal${attention ? " has-attention" : ""}`}
      data-tone={tone}
      style={stagger(index)}
      onClick={onClick}
    >
      <span className="ts-stat__icon" aria-hidden="true"><Icon size={19} strokeWidth={1.9} /></span>
      <span className="ts-stat__label">{label}</span>
      <strong className="ts-stat__value"><CountUp value={value} decimals={decimals} suffix={suffix} delay={index * 60} /></strong>
      <span className="ts-stat__foot">{foot}</span>
      <ArrowRight className="ts-stat__go" size={16} aria-hidden="true" />
    </button>
  );
}

function TodayCard({ schedule, onOpenTimetable }) {
  const { loading, lessons, hasTimetable, error } = schedule;
  return (
    <SectionCard
      className="ts-today"
      icon={CalendarClock}
      title="Today's classes"
      subtitle={formatLongDate()}
      action={<button type="button" className="ts-link" onClick={onOpenTimetable}>Full timetable <ArrowRight size={14} aria-hidden="true" /></button>}
    >
      {loading ? (
        <div className="ts-today__skeleton" aria-hidden="true">
          {[0, 1, 2].map((row) => (
            <div key={row} className="ts-today__skeleton-row">
              <Skeleton width={54} height={14} />
              <Skeleton width="100%" height={46} radius={12} />
            </div>
          ))}
        </div>
      ) : error && !hasTimetable ? (
        <EmptyState compact art="calendar" title="Couldn't load your timetable" message="Check your connection and reopen this page." />
      ) : !hasTimetable ? (
        <EmptyState
          compact
          art="calendar"
          title="No timetable yet"
          message="Once your school assigns you to periods, today's classes will line up here."
        />
      ) : lessons.length === 0 ? (
        <EmptyState compact art="check" title="No classes today" message="Nothing on your timetable for today. Use the time to plan or catch up on marking." />
      ) : (
        <ol className="ts-timeline">
          {lessons.map((lesson) => (
            <li key={lesson.id} className={`ts-lesson is-${lesson.status}`} data-tone={toneIndex(lesson.subject_name || lesson.display_label)}>
              <div className="ts-lesson__time">
                <strong>{clock(lesson.start_time)}</strong>
                <span>{clock(lesson.end_time)}</span>
              </div>
              <div className="ts-lesson__card">
                <span className="ts-lesson__bar" aria-hidden="true" />
                <div className="ts-lesson__body">
                  <strong>{lesson.display_label || lesson.subject_name || "Lesson"}</strong>
                  <span>{[lesson.class_name, lesson.room].filter(Boolean).join(" · ") || "—"}</span>
                </div>
                {lesson.status === "now" ? (
                  <span className="ts-lesson__pill is-now"><i aria-hidden="true" /> Now</span>
                ) : lesson.status === "done" ? (
                  <span className="ts-lesson__pill is-done"><Check size={13} aria-hidden="true" /> Done</span>
                ) : (
                  <span className="ts-lesson__pill">Up next</span>
                )}
                {lesson.status === "now" ? (
                  <span className="ts-lesson__progress" aria-hidden="true"><i style={{ width: `${lesson.progress}%` }} /></span>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}

function UpcomingExams({ exams, onOpen }) {
  return (
    <SectionCard
      icon={FileCheck}
      title="Coming up"
      subtitle="Exams and assessments you've scheduled"
      action={<button type="button" className="ts-link" onClick={onOpen}>All exams <ArrowRight size={14} aria-hidden="true" /></button>}
    >
      {exams.length === 0 ? (
        <EmptyState compact art="clipboard" title="Nothing scheduled" message="Build an exam and set its date. It will show up here." />
      ) : (
        <ul className="ts-exams">
          {exams.slice(0, 5).map((exam) => {
            const when = dayParts(exam.start_date);
            return (
              <li key={exam.id} className="ts-exam" data-tone={toneIndex(exam.subject || exam.title)}>
                <span className="ts-exam__date" aria-hidden="true">
                  <strong>{when?.day ?? "—"}</strong>
                  <small>{when?.month ?? ""}</small>
                </span>
                <span className="ts-exam__body">
                  <strong>{exam.title || "Untitled exam"}</strong>
                  <span>{exam.class_name || "All classes"}</span>
                </span>
                {when ? <span className="ts-exam__when">{when.relative}</span> : null}
              </li>
            );
          })}
        </ul>
      )}
    </SectionCard>
  );
}

const QUICK_ACTIONS = [
  { key: "attendance", icon: CalendarCheck, title: "Take attendance", text: "Tap through your class register", tone: "emerald", tab: (nonK12) => (nonK12 ? "attendance-info" : "attendance") },
  { key: "exam", icon: FilePlus2, title: "Build an exam", text: "Objective, theory or both", tone: "indigo", tab: () => "exam-builder" },
  { key: "grading", icon: FileSignature, title: "Mark written answers", text: "Score theory papers", tone: "amber", tab: () => "theory-grading" },
  { key: "results", icon: Trophy, title: "Enter scores", text: "Record marks and see rankings", tone: "violet", tab: () => "results" },
  { key: "plan", icon: BookOpen, title: "Plan a lesson", text: "Scheme of work and notes", tone: "sky", tab: () => "planning" },
  { key: "message", icon: MessageCircle, title: "Message a class", text: "Reach students in one go", tone: "rose", tab: () => "class-messages" },
];

/* ------------------------------------------------------------------ page */

export default function TeacherHome({ session, data = {}, isRefreshing, onTabChange, onEditProfile, nonK12 = false }) {
  const metrics = data.metrics || {};
  const profile = data.profile || data.teacher || data.user || {};
  const name = profile.name || profile.full_name || session?.user?.full_name || profile.email || "Teacher";
  const exams = data.upcoming_assessments || [];
  const inbox = (data.inbox || []).filter((item) => item && item.direction !== "outgoing");
  const unread = Number(metrics.unread_inbox ?? inbox.filter((item) => !item.is_read).length) || 0;
  const subjects = normaliseSubjects(profile, data.options?.subjects || []);
  const classes = data.options?.classes || data.classes || [];
  const schedule = useTodaySchedule(session);

  const upcoming = Number(metrics.upcoming_assessments ?? exams.length ?? 0);
  const cbtResults = data.cbt_results || data.submitted_results || [];
  // "pending_submissions" counts attempts still being written; what a teacher
  // actually has to act on is submitted papers with unmarked written answers.
  const pending = cbtResults.filter((result) => result?.needs_theory_grading).length;
  const cbtAverage =
    metrics.average_cbt_score ??
    (cbtResults.length
      ? Math.round(cbtResults.reduce((sum, item) => sum + Number(item.percentage || 0), 0) / cbtResults.length)
      : 0);
  const nextExam = exams[0];
  const nextExamWhen = nextExam ? dayParts(nextExam.start_date) : null;

  const showMoney = profile.monthly_salary != null && Number(profile.monthly_salary) > 0;
  const showAdvances = Number(profile.advances_received || 0) > 0 || Number(metrics.pending_advances || 0) > 0;

  const primaryCta = pending > 0
    ? { label: `Mark ${pluralize(pending, "answer")}`, icon: FileSignature, tab: "theory-grading" }
    : { label: "Build an exam", icon: FilePlus2, tab: "exam-builder" };
  const PrimaryIcon = primaryCta.icon;

  return (
    <div className="ts-home">
      <header className="ts-hero ts-reveal" style={stagger(0)}>
        <span className="ts-hero__orb ts-hero__orb--a" aria-hidden="true" />
        <span className="ts-hero__orb ts-hero__orb--b" aria-hidden="true" />
        <div className="ts-hero__text">
          <div className="ts-hero__meta">
            <span className="ts-hero__date">{formatLongDate()}</span>
            <CurrentTermBadge session={session} className="ts-hero__term" />
          </div>
          <h1 className="ts-hero__title">
            {greetingFor()}, <span>{friendlyName(name)}</span>
          </h1>
          <p className="ts-hero__lede">
            {focusSentence({ pending, upcoming, unread, lessonsToday: schedule.lessons.length, loadingSchedule: schedule.loading })}
          </p>
          {schedule.current ? (
            <p className="ts-hero__now">
              <i aria-hidden="true" />
              In session: <strong>{schedule.current.display_label || schedule.current.subject_name}</strong>
              {schedule.current.class_name ? ` with ${schedule.current.class_name}` : ""} until {clock(schedule.current.end_time)}
            </p>
          ) : schedule.next ? (
            <p className="ts-hero__now is-next">
              <Hourglass size={14} aria-hidden="true" />
              Next: <strong>{schedule.next.display_label || schedule.next.subject_name}</strong>
              {schedule.next.class_name ? ` with ${schedule.next.class_name}` : ""} at {clock(schedule.next.start_time)}
            </p>
          ) : null}
          <div className="ts-hero__actions">
            <button type="button" className="ts-btn ts-btn--primary" onClick={() => onTabChange?.(primaryCta.tab)}>
              <PrimaryIcon size={17} aria-hidden="true" />
              {primaryCta.label}
            </button>
            <button type="button" className="ts-btn ts-btn--ghost" onClick={() => onTabChange?.(nonK12 ? "attendance-info" : "attendance")}>
              <CalendarCheck size={17} aria-hidden="true" />
              Take attendance
            </button>
          </div>
        </div>
        <button type="button" className="ts-hero__me" onClick={onEditProfile} aria-label="Edit my profile">
          <Avatar name={name} src={profile.profile_picture} size={92} />
          <span className="ts-hero__edit" aria-hidden="true"><Pencil size={13} strokeWidth={2.4} /></span>
          <strong>{clean(profile.specialization) || "Teacher"}</strong>
          <small>{subjects.length ? pluralize(subjects.length, "subject") : "Edit profile"}</small>
        </button>
      </header>

      <div className="ts-stat-grid">
        <StatTile index={1} tone="indigo" icon={ClipboardList} label="Assessments" value={metrics.total_assessments ?? 0}
          foot={`${metrics.published_assessments ?? 0} published`} onClick={() => onTabChange?.("past-exams")} />
        <StatTile index={2} tone="sky" icon={CalendarClock} label="Coming up" value={upcoming}
          foot={nextExam ? `Next: ${nextExam.title || "exam"}${nextExamWhen ? ` · ${nextExamWhen.relative.toLowerCase()}` : ""}` : "Nothing scheduled"}
          onClick={() => onTabChange?.("past-exams")} />
        <StatTile index={3} tone="amber" icon={FileSignature} label="To mark" value={pending} attention={pending > 0}
          foot={pending > 0 ? "Written answers waiting" : "All marked"} onClick={() => onTabChange?.("theory-grading")} />
        <StatTile index={4} tone="emerald" icon={Trophy} label="CBT results" value={metrics.submitted_results ?? cbtResults.length}
          foot={`${cbtAverage}% class average`} onClick={() => onTabChange?.("results")} />
      </div>

      <div className="ts-cols">
        <div className="ts-col">
          <TodayCard schedule={schedule} onOpenTimetable={() => onTabChange?.("timetable")} />

          <SectionCard className="ts-quick-card" icon={Sparkles} title="Jump back in" subtitle="The things teachers do most">
            <div className="ts-quick">
              {QUICK_ACTIONS.map((action, index) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.key}
                    type="button"
                    className="ts-quick__item ts-reveal"
                    data-tone={action.tone}
                    style={stagger(index + 3, 35)}
                    onClick={() => onTabChange?.(action.tab(nonK12))}
                  >
                    <span className="ts-quick__icon" aria-hidden="true"><Icon size={19} strokeWidth={1.9} /></span>
                    <span className="ts-quick__text">
                      <strong>{action.title}</strong>
                      <small>{action.text}</small>
                    </span>
                    <ArrowRight className="ts-quick__go" size={16} aria-hidden="true" />
                  </button>
                );
              })}
            </div>
          </SectionCard>

          <SectionCard
            icon={Inbox}
            title="Messages"
            subtitle={unread ? `${pluralize(unread, "unread message")}` : "You're up to date"}
            action={<button type="button" className="ts-link" onClick={() => onTabChange?.("class-messages")}>Open inbox <ArrowRight size={14} aria-hidden="true" /></button>}
          >
            {inbox.length === 0 ? (
              <EmptyState compact art="inbox" title="Inbox is empty" message="Notes from your admin and replies from parents will land here." />
            ) : (
              <ul className="ts-msgs">
                {inbox.slice(0, 4).map((message) => (
                  <li key={message.id} className={message.is_read ? "" : "is-unread"}>
                    <Avatar name={message.from_name || message.from || "?"} size={34} />
                    <button type="button" onClick={() => onTabChange?.("class-messages")}>
                      <strong>{message.from_name || message.from || "Someone"}</strong>
                      <span>{cleanSubject(message.subject) || (message.body ? String(message.body).slice(0, 60) : "(no subject)")}</span>
                    </button>
                    <time>{timeAgo(message.created_at || message.sent_at)}</time>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        <div className="ts-col">
          <UpcomingExams exams={exams} onOpen={() => onTabChange?.("past-exams")} />

          <SectionCard icon={LayoutDashboard} title="What you teach" subtitle="Subjects and classes assigned to you">
            {subjects.length === 0 && classes.length === 0 ? (
              <EmptyState compact art="books" title="Nothing assigned yet" message="Your admin assigns subjects and classes. They'll appear here." />
            ) : (
              <div className="ts-teach">
                {subjects.length ? (
                  <div>
                    <p className="ts-mini-label">Subjects</p>
                    <div className="ts-chips">
                      {subjects.map((subject) => (
                        <span key={subject.id} className="ts-chip" data-tone={toneIndex(subject.name)}>
                          {subject.name}{subject.code ? <small>{subject.code}</small> : null}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {classes.length ? (
                  <div>
                    <p className="ts-mini-label">Classes</p>
                    <div className="ts-chips">
                      {classes.map((item) => (
                        <span key={item.id} className="ts-chip is-plain">{item.label || item.name}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </SectionCard>

          {showMoney || showAdvances ? (
            <SectionCard
              icon={Briefcase}
              title="My pay & requests"
              subtitle="A quick look at your HR record"
              action={<button type="button" className="ts-link" onClick={() => onTabChange?.("requests")}>Open HR <ArrowRight size={14} aria-hidden="true" /></button>}
            >
              <dl className="ts-facts">
                {showMoney ? (<div><dt>Monthly salary</dt><dd>{money(profile.monthly_salary)}</dd></div>) : null}
                {profile.salary_balance != null ? (<div><dt>Balance</dt><dd>{money(profile.salary_balance)}</dd></div>) : null}
                {Number(profile.advances_received || 0) > 0 ? (<div><dt>Advances received</dt><dd>{money(profile.advances_received)}</dd></div>) : null}
                <div><dt>Advances awaiting approval</dt><dd>{Number(metrics.pending_advances || 0)}</dd></div>
              </dl>
            </SectionCard>
          ) : null}

          {schedule.activities.length ? (
            <SectionCard icon={CalendarClock} title="On the school calendar" subtitle="Events set by your administrator">
              <ul className="ts-events">
                {schedule.activities.slice(0, 4).map((event) => (
                  <li key={event.id} style={{ "--event": event.color || "var(--ts-accent)" }}>
                    <strong>{event.title}</strong>
                    <span>{event.description || ""}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
        </div>
      </div>

      {isRefreshing ? <p className="ts-refreshing" role="status">Refreshing your dashboard…</p> : null}
    </div>
  );
}
