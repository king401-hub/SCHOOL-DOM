// "My timetable": the whole teaching week as a colour-coded grid (with today and
// the lesson in session lit up), or one day at a time on a phone.
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, CalendarDays, Check, Coffee, Flame, LayoutGrid, Rows3, School } from "lucide-react";
import { requestJson } from "../AppShared";
import {
  EmptyState,
  PageHeader,
  SectionCard,
  Skeleton,
  clock,
  pluralize,
  stagger,
  toMinutes,
  toneIndex,
} from "./TeacherKit";

const FALLBACK_DAYS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
];

const shortDay = (label) => String(label || "").slice(0, 3);

/** Date (this week) of a weekday index where Monday = 0. */
function dateOfWeekday(index, from = new Date()) {
  const monday = new Date(from);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  monday.setDate(monday.getDate() + Number(index));
  return monday;
}

function statusOf(entry, minutesNow, isToday) {
  if (!isToday) return "later";
  const start = toMinutes(entry.start_time);
  const end = toMinutes(entry.end_time);
  if (start === null || end === null) return "later";
  if (minutesNow >= end) return "done";
  if (minutesNow >= start) return "now";
  return "later";
}

function useTimetable(session) {
  const [state, setState] = useState({ loading: true, error: "", entries: [], days: FALLBACK_DAYS, slots: [], activities: [] });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const result = await requestJson(session, "GET", "/api/app/timetables/");
      setState({
        loading: false,
        error: "",
        entries: result?.entries || [],
        days: result?.days?.length ? result.days : FALLBACK_DAYS,
        slots: result?.time_slots || [],
        activities: result?.school_activities || [],
      });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: error.message || "We couldn't load your timetable." }));
    }
  }, [session]);

  useEffect(() => {
    if (session) load();
  }, [load, session]);

  return { ...state, reload: load };
}

function LessonChip({ entry, status, compact = false }) {
  return (
    <div className={`ts-tt__lesson is-${status}${compact ? " is-compact" : ""}`} data-tone={toneIndex(entry.subject_name || entry.display_label)}>
      <strong>{entry.display_label || entry.subject_name || "Lesson"}</strong>
      <span>{[entry.class_name, entry.room].filter(Boolean).join(" · ")}</span>
      {status === "now" ? <em className="ts-tt__now"><i aria-hidden="true" /> Now</em> : null}
    </div>
  );
}

export default function TeacherTimetable({ session }) {
  const { loading, error, entries, days, slots: configuredSlots, activities, reload } = useTimetable(session);
  const [now, setNow] = useState(() => new Date());
  const [view, setView] = useState(() => (typeof window !== "undefined" && window.innerWidth < 820 ? "day" : "week"));
  const [pickedDay, setPickedDay] = useState(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const todayIndex = (now.getDay() + 6) % 7;
  const minutesNow = now.getHours() * 60 + now.getMinutes();

  const slots = useMemo(() => {
    if (configuredSlots.length) return configuredSlots;
    const seen = new Map();
    entries.forEach((entry) => {
      const key = `${entry.start_time}|${entry.end_time}`;
      if (!seen.has(key)) seen.set(key, { start_time: entry.start_time, end_time: entry.end_time });
    });
    return Array.from(seen.values()).sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
  }, [configuredSlots, entries]);

  const byCell = useMemo(() => {
    const map = new Map();
    entries.forEach((entry) => {
      const key = `${entry.day_of_week}|${entry.start_time}|${entry.end_time}`;
      map.set(key, [...(map.get(key) || []), entry]);
    });
    return map;
  }, [entries]);
  const lessonsIn = (dayValue, slot) => byCell.get(`${dayValue}|${slot.start_time}|${slot.end_time}`) || [];

  const stats = useMemo(() => {
    const perDay = new Map();
    entries.forEach((entry) => perDay.set(entry.day_of_week, (perDay.get(entry.day_of_week) || 0) + 1));
    let busiest = null;
    perDay.forEach((count, value) => {
      if (!busiest || count > busiest.count) busiest = { value, count };
    });
    return {
      lessons: entries.length,
      classes: new Set(entries.map((entry) => entry.class_name).filter(Boolean)).size,
      perDay,
      busiest: busiest ? { ...busiest, label: days.find((day) => Number(day.value) === Number(busiest.value))?.label } : null,
    };
  }, [entries, days]);

  const selectedDay = pickedDay ?? (days.some((day) => Number(day.value) === todayIndex) ? todayIndex : days[0]?.value ?? 0);
  const hasTimetable = entries.length > 0 && slots.length > 0;

  const header = (
    <PageHeader
      eyebrow="Your week"
      title="My timetable"
      subtitle={
        hasTimetable
          ? `${pluralize(stats.lessons, "lesson")} a week across ${pluralize(stats.classes, "class", "classes")}.`
          : "Your weekly teaching schedule, laid out at a glance."
      }
      icon={CalendarClock}
      tone="sky"
      actions={
        hasTimetable ? (
          <div className="segmented-control ts-tt__toggle" role="group" aria-label="Timetable view">
            <button type="button" className={view === "week" ? "active" : ""} aria-pressed={view === "week"} onClick={() => setView("week")}>
              <LayoutGrid size={14} aria-hidden="true" /> Week
            </button>
            <button type="button" className={view === "day" ? "active" : ""} aria-pressed={view === "day"} onClick={() => setView("day")}>
              <Rows3 size={14} aria-hidden="true" /> Day
            </button>
          </div>
        ) : null
      }
      meta={
        hasTimetable && stats.busiest ? (
          <>
            <span className="ts-chip is-plain"><Flame size={13} aria-hidden="true" /> Busiest: {stats.busiest.label} · {pluralize(stats.busiest.count, "lesson")}</span>
            {stats.perDay.get(todayIndex) ? <span className="ts-chip is-plain"><CalendarDays size={13} aria-hidden="true" /> Today: {pluralize(stats.perDay.get(todayIndex), "lesson")}</span> : null}
          </>
        ) : null
      }
    />
  );

  if (loading && !entries.length) {
    return (
      <div className="ts-tt-page">
        {header}
        <SectionCard className="ts-tt-card">
          <div className="ts-tt__skeleton" aria-hidden="true">
            {[0, 1, 2, 3, 4].map((row) => <Skeleton key={row} width="100%" height={54} radius={14} />)}
          </div>
        </SectionCard>
      </div>
    );
  }

  if (error && !entries.length) {
    return (
      <div className="ts-tt-page">
        {header}
        <SectionCard className="ts-tt-card">
          <EmptyState
            art="calendar"
            title="We couldn't load your timetable"
            message={error}
            action={<button type="button" className="ts-btn ts-btn--primary" onClick={reload}>Try again</button>}
          />
        </SectionCard>
      </div>
    );
  }

  if (!hasTimetable) {
    return (
      <div className="ts-tt-page">
        {header}
        <SectionCard className="ts-tt-card">
          <EmptyState
            art="calendar"
            title="Your timetable is empty for now"
            message="When your school puts you on the timetable, your whole week will build itself right here."
          />
        </SectionCard>
        <Activities activities={activities} />
      </div>
    );
  }

  return (
    <div className="ts-tt-page">
      {header}

      {view === "week" ? (
        <SectionCard className="ts-tt-card">
          <div className="ts-tt__scroll">
            <div className="ts-tt__grid" role="table" aria-label="Weekly timetable" style={{ "--ts-days": days.length }}>
              <div className="ts-tt__row ts-tt__row--head" role="row">
                <div className="ts-tt__corner" role="columnheader">Time</div>
                {days.map((day) => {
                  const date = dateOfWeekday(day.value, now);
                  const isToday = Number(day.value) === todayIndex;
                  return (
                    <div key={day.value} className={`ts-tt__day${isToday ? " is-today" : ""}`} role="columnheader" aria-current={isToday ? "date" : undefined}>
                      <span>{shortDay(day.label)}</span>
                      <b>{date.getDate()}</b>
                      {isToday ? <em>Today</em> : null}
                    </div>
                  );
                })}
              </div>

              {slots.map((slot, slotIndex) =>
                slot.is_break ? (
                  <div key={`${slot.start_time}-${slot.end_time}`} className="ts-tt__row ts-tt__row--break" role="row">
                    <div className="ts-tt__break" role="cell">
                      <Coffee size={14} aria-hidden="true" />
                      <span>Break</span>
                      <small>{clock(slot.start_time)} – {clock(slot.end_time)}</small>
                    </div>
                  </div>
                ) : (
                  <div key={`${slot.start_time}-${slot.end_time}`} className="ts-tt__row ts-reveal" role="row" style={stagger(slotIndex, 40)}>
                    <div className="ts-tt__time" role="rowheader">
                      <strong>{clock(slot.start_time)}</strong>
                      <span>{clock(slot.end_time)}</span>
                    </div>
                    {days.map((day) => {
                      const isToday = Number(day.value) === todayIndex;
                      const here = lessonsIn(day.value, slot);
                      return (
                        <div key={day.value} className={`ts-tt__cell${isToday ? " is-today" : ""}`} role="cell">
                          {here.length ? (
                            here.map((entry) => <LessonChip key={entry.id} entry={entry} status={statusOf(entry, minutesNow, isToday)} />)
                          ) : (
                            <span className="ts-tt__free" aria-label="Free">·</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )
              )}
            </div>
          </div>
        </SectionCard>
      ) : (
        <SectionCard className="ts-tt-card">
          <div className="ts-daybar" role="tablist" aria-label="Choose a day">
            {days.map((day) => {
              const count = stats.perDay.get(day.value) || 0;
              const isToday = Number(day.value) === todayIndex;
              const active = Number(day.value) === Number(selectedDay);
              return (
                <button
                  key={day.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className={`ts-daybar__item${active ? " is-active" : ""}${isToday ? " is-today" : ""}`}
                  onClick={() => setPickedDay(day.value)}
                >
                  <span>{shortDay(day.label)}</span>
                  <b>{dateOfWeekday(day.value, now).getDate()}</b>
                  <i>{count ? count : ""}</i>
                </button>
              );
            })}
          </div>

          <ol className="ts-timeline ts-tt__day-list" key={selectedDay}>
            {slots.map((slot, slotIndex) => {
              if (slot.is_break) {
                return (
                  <li key={`${slot.start_time}-${slot.end_time}`} className="ts-tt__break-line ts-reveal" style={stagger(slotIndex, 35)}>
                    <Coffee size={14} aria-hidden="true" /> Break <small>{clock(slot.start_time)} – {clock(slot.end_time)}</small>
                  </li>
                );
              }
              const isToday = Number(selectedDay) === todayIndex;
              const here = lessonsIn(selectedDay, slot);
              if (!here.length) {
                return (
                  <li key={`${slot.start_time}-${slot.end_time}`} className="ts-lesson ts-lesson--free ts-reveal" style={stagger(slotIndex, 35)}>
                    <div className="ts-lesson__time"><strong>{clock(slot.start_time)}</strong><span>{clock(slot.end_time)}</span></div>
                    <div className="ts-lesson__card"><div className="ts-lesson__body"><span>Free period</span></div></div>
                  </li>
                );
              }
              return here.map((entry) => {
                const status = statusOf(entry, minutesNow, isToday);
                const start = toMinutes(entry.start_time);
                const end = toMinutes(entry.end_time);
                const progress = status === "now" && end > start ? Math.round(((minutesNow - start) / (end - start)) * 100) : 0;
                return (
                  <li key={entry.id} className={`ts-lesson is-${status} ts-reveal`} data-tone={toneIndex(entry.subject_name || entry.display_label)} style={stagger(slotIndex, 35)}>
                    <div className="ts-lesson__time"><strong>{clock(entry.start_time)}</strong><span>{clock(entry.end_time)}</span></div>
                    <div className="ts-lesson__card">
                      <span className="ts-lesson__bar" aria-hidden="true" />
                      <div className="ts-lesson__body">
                        <strong>{entry.display_label || entry.subject_name || "Lesson"}</strong>
                        <span>{[entry.class_name, entry.room].filter(Boolean).join(" · ") || "—"}</span>
                      </div>
                      {status === "now" ? (
                        <span className="ts-lesson__pill is-now"><i aria-hidden="true" /> Now</span>
                      ) : status === "done" ? (
                        <span className="ts-lesson__pill is-done"><Check size={13} aria-hidden="true" /> Done</span>
                      ) : null}
                      {status === "now" ? <span className="ts-lesson__progress" aria-hidden="true"><i style={{ width: `${progress}%` }} /></span> : null}
                    </div>
                  </li>
                );
              });
            })}
          </ol>
        </SectionCard>
      )}

      <Activities activities={activities} />
    </div>
  );
}

function Activities({ activities }) {
  if (!activities?.length) return null;
  const formatDay = (value) => new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return (
    <SectionCard icon={School} title="On the school calendar" subtitle="Events and activities set by your administrator" className="ts-tt-events">
      <ul className="ts-events">
        {activities.map((event) => {
          const when = event.activity_date
            ? event.end_date && event.end_date !== event.activity_date
              ? `${formatDay(event.activity_date)} – ${formatDay(event.end_date)}`
              : formatDay(event.activity_date)
            : "";
          return (
            <li key={event.id} style={{ "--event": event.color || "var(--ts-accent)" }}>
              <strong>{event.title}{when ? <small> · {when}</small> : null}</strong>
              <span>{event.description || ""}</span>
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
}
