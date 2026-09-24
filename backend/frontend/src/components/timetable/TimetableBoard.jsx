// The admin "Weekly schedule": one class at a time by default, one calm card per
// slot, colour per subject, click a card for details / edit / remove, click an
// empty slot to add. All-classes view collapses into compact chips, and on a
// phone it shows one day at a time.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CalendarPlus, Coffee, Eye, Info, LayoutGrid, Plus, Sparkles, Trash2 } from "lucide-react";
import { Spinner } from "../../AppShared";
import "./timetable.css";
import {
  ALL_CLASSES,
  buildRows,
  byDayThenTime,
  classTiny,
  entryLabel,
  groupByCell,
  hueStyle,
  needsTeacher,
  cellKey,
  shortDay,
  subjectShort,
  subjectTiny,
  timeRange,
  toMinutes,
  weekdayIndex,
} from "./timetableUtils";

const CLASS_STORAGE_KEY = "schooldom.admin_timetable_class";
const TABS_MAX = 8; // beyond this many classes a dropdown scales better than tabs
const CHIPS_PER_CELL = 3;

const readStored = (key) => {
  try {
    return window.localStorage.getItem(key) || "";
  } catch {
    return "";
  }
};
const writeStored = (key, value) => {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage can be blocked; the page works without it */
  }
};

// Judged by the board's own width, not the window's: with the sidebar open a
// tablet leaves the board barely wider than a phone.
function useNarrow(ref, limit) {
  const [narrow, setNarrow] = useState(false);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const measure = () => setNarrow(node.getBoundingClientRect().width < limit);
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref, limit]);
  return narrow;
}

/** "i" button with a tooltip that opens on hover AND keyboard focus. */
function InfoTip({ id, label, children }) {
  return (
    <span className="tt-info">
      <button type="button" className="tt-info-btn" aria-label={label} aria-describedby={id}>
        <Info size={14} aria-hidden="true" />
      </button>
      <span role="tooltip" id={id} className="tt-info-tip">{children}</span>
    </span>
  );
}

/* --------------------------------------------------------------- class picker */

function ClassPicker({ classes, value, onChange }) {
  const tabsRef = useRef(null);
  const items = [...classes.map((item) => ({ id: String(item.id), label: item.label || item.name })), { id: ALL_CLASSES, label: "All classes" }];

  if (classes.length > TABS_MAX) {
    return (
      <label className="tt-classselect">
        <span>Class</span>
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          {items.map((item) => (
            <option key={item.id} value={item.id}>{item.id === ALL_CLASSES ? "All classes (compact)" : item.label}</option>
          ))}
        </select>
      </label>
    );
  }

  const onKeyDown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = items.findIndex((item) => item.id === value);
    let next = index;
    if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = items.length - 1;
    onChange(items[next].id);
    window.requestAnimationFrame(() => tabsRef.current?.querySelector('[aria-selected="true"]')?.focus());
  };

  return (
    <div className="tt-tabs" role="tablist" aria-label="Class" ref={tabsRef} onKeyDown={onKeyDown}>
      {items.map((item) => {
        const active = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            className={`tt-tab${active ? " is-active" : ""}${item.id === ALL_CLASSES ? " is-all" : ""}`}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------- day switcher */

// Clicking a weekday (grid header, or these tabs) switches the board to that day.
function DayTabs({ days, selected, todayValue, counts, showWeek, onSelect, onWeek }) {
  const tabsRef = useRef(null);
  const onKeyDown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = days.findIndex((day) => Number(day.value) === Number(selected));
    let next = index;
    if (event.key === "ArrowLeft") next = (index - 1 + days.length) % days.length;
    if (event.key === "ArrowRight") next = (index + 1) % days.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = days.length - 1;
    onSelect(Number(days[next].value));
    window.requestAnimationFrame(() => tabsRef.current?.querySelector('[aria-selected="true"]')?.focus());
  };
  return (
    <div className="tt-dayswitch">
      {showWeek ? (
        <button type="button" className="tt-weekbtn" onClick={onWeek}>
          <LayoutGrid size={14} aria-hidden="true" /> Whole week
        </button>
      ) : null}
      <div className="tt-daytabs" role="tablist" aria-label="Day" ref={tabsRef} onKeyDown={onKeyDown}>
        {days.map((day) => {
          const active = Number(day.value) === Number(selected);
          const today = Number(day.value) === todayValue;
          const count = counts.get(Number(day.value)) || 0;
          return (
            <button
              key={day.value}
              type="button"
              role="tab"
              aria-selected={active}
              tabIndex={active ? 0 : -1}
              aria-label={`${day.label}${today ? " (today)" : ""}, ${count} ${count === 1 ? "lesson" : "lessons"}`}
              className={`tt-daytab${active ? " is-active" : ""}${today ? " is-today" : ""}`}
              onClick={() => onSelect(Number(day.value))}
            >
              <span>{shortDay(day.label)}</span>
              <i aria-hidden="true">{count}</i>
              {today ? <em>Today</em> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------- cards */

function EntryCard({ entry, subjectsById, context, onOpen, navProps, detail = false }) {
  const unassigned = needsTeacher(entry);
  const full = entryLabel(entry);
  const hue = hueStyle(entry);
  const teacher = entry.teacher_name;
  const aria = `${full}, ${entry.class_name}. ${teacher ? `Teacher ${teacher}` : unassigned ? "No teacher assigned" : "No teacher needed"}${entry.room ? `. Room ${entry.room}` : ""}. ${context}. Open details`;
  return (
    <button
      type="button"
      className={`tt-card${unassigned ? " is-unassigned" : ""}${hue ? "" : " is-neutral"}`}
      style={hue}
      title={`${full} — ${entry.class_name}${teacher ? ` — ${teacher}` : unassigned ? " — no teacher yet" : ""}${entry.room ? ` — ${entry.room}` : ""}`}
      aria-label={aria}
      onClick={() => onOpen(entry)}
      {...navProps}
    >
      <span className="tt-card-name">{subjectShort(full)}</span>
      {teacher ? <span className="tt-card-sub">{teacher}</span> : null}
      {detail && entry.room ? <span className="tt-card-room">{entry.room}</span> : null}
      {unassigned ? (
        <span className="tt-warn" aria-hidden="true">
          <AlertTriangle size={12} />
        </span>
      ) : null}
    </button>
  );
}

function EntryChip({ entry, subjectsById, context, onOpen, navProps }) {
  const unassigned = needsTeacher(entry);
  const full = entryLabel(entry);
  const hue = hueStyle(entry);
  return (
    <button
      type="button"
      className={`tt-chip${unassigned ? " is-unassigned" : ""}${hue ? "" : " is-neutral"}`}
      style={hue}
      title={`${full} — ${entry.class_name}${entry.teacher_name ? ` — ${entry.teacher_name}` : unassigned ? " — no teacher yet" : ""}`}
      aria-label={`${full}, ${entry.class_name}. ${entry.teacher_name ? `Teacher ${entry.teacher_name}` : unassigned ? "No teacher assigned" : ""}. ${context}. Open details`}
      onClick={() => onOpen(entry)}
      {...navProps}
    >
      <b>{subjectTiny(entry, subjectsById)}</b>
      <span>{classTiny(entry.class_name)}</span>
      {unassigned ? <i className="tt-chip-dot" aria-hidden="true" /> : null}
    </button>
  );
}

/* ----------------------------------------------------------------- the board */

export default function TimetableBoard({
  entries = [],
  classes = [],
  subjects = [],
  days = [],
  timeSlots = [],
  notice = null,
  jumpTo = null,
  onOpenEntry,
  onOpenCell,
  onAddAt,
  onAddBlank,
  onDeleteEntry,
  onGenerate,
  onOpenSettings,
}) {
  const [classChoice, setClassChoice] = useState(() => readStored(CLASS_STORAGE_KEY));
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [focusDay, setFocusDay] = useState(null); // null = the whole week
  const [deletingId, setDeletingId] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const [generating, setGenerating] = useState(false);
  const [generateNote, setGenerateNote] = useState(null);
  const rootRef = useRef(null);
  const isNarrow = useNarrow(rootRef, 700);
  const bodyRef = useRef(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const subjectsById = useMemo(() => new Map(subjects.map((item) => [String(item.id), item])), [subjects]);

  // First class by default; "All classes" only when asked for (or no classes yet).
  const activeClass = useMemo(() => {
    if (classChoice === ALL_CLASSES) return null;
    return classes.find((item) => String(item.id) === String(classChoice)) || classes[0] || null;
  }, [classChoice, classes]);
  const pickerValue = activeClass ? String(activeClass.id) : ALL_CLASSES;
  const single = Boolean(activeClass);

  const chooseClass = useCallback((value) => {
    setClassChoice(value);
    writeStored(CLASS_STORAGE_KEY, value);
  }, []);

  // After adding a lesson to a class other than the one on screen, follow it so
  // the new lesson is visible (the all-classes view already shows every class).
  useEffect(() => {
    if (!jumpTo?.classId) return;
    if (classChoice === ALL_CLASSES) return;
    if (activeClass && String(activeClass.id) === String(jumpTo.classId)) return;
    if (classes.some((item) => String(item.id) === String(jumpTo.classId))) chooseClass(String(jumpTo.classId));
    // only react to a new jump request, not to every change of the current class
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpTo?.nonce]);

  const scoped = useMemo(
    () => (single ? entries.filter((item) => String(item.class_id) === String(activeClass.id)) : entries),
    [entries, single, activeClass]
  );
  const unassignedCount = useMemo(() => scoped.filter(needsTeacher).length, [scoped]);
  const visible = useMemo(() => (unassignedOnly ? scoped.filter(needsTeacher) : scoped), [scoped, unassignedOnly]);
  const cells = useMemo(() => groupByCell(visible), [visible]);
  const rows = useMemo(() => buildRows(timeSlots, scoped), [timeSlots, scoped]);
  const listEntries = useMemo(() => [...visible].sort(byDayThenTime), [visible]);
  const dayCounts = useMemo(() => {
    const counts = new Map();
    visible.forEach((entry) => counts.set(Number(entry.day_of_week), (counts.get(Number(entry.day_of_week)) || 0) + 1));
    return counts;
  }, [visible]);
  const listGroups = useMemo(() => {
    const groups = [];
    listEntries.forEach((entry) => {
      const last = groups[groups.length - 1];
      if (last && last.day === Number(entry.day_of_week)) last.entries.push(entry);
      else groups.push({ day: Number(entry.day_of_week), entries: [entry] });
    });
    return groups;
  }, [listEntries]);

  // If the filter was on and the last unassigned lesson got a teacher, drop it
  // so the board doesn't sit empty.
  useEffect(() => {
    if (unassignedOnly && unassignedCount === 0) setUnassignedOnly(false);
  }, [unassignedOnly, unassignedCount]);

  const todayValue = weekdayIndex(now);
  const minutesNow = now.getHours() * 60 + now.getMinutes();
  const dayValues = useMemo(() => days.map((day) => Number(day.value)), [days]);
  const validFocus = focusDay !== null && dayValues.includes(focusDay) ? focusDay : null;
  const dayMode = isNarrow || validFocus !== null; // a phone always works one day at a time
  const selectedDay = validFocus ?? (dayValues.includes(todayValue) ? todayValue : dayValues[0]);

  const isNowRow = (row) => {
    const start = toMinutes(row.start_time);
    const end = toMinutes(row.end_time);
    return start !== null && end !== null && minutesNow >= start && minutesNow < end;
  };

  const className = activeClass ? activeClass.label || activeClass.name : "";
  const dayName = (value) => days.find((day) => Number(day.value) === Number(value))?.label || "";

  const deleteFromList = async (entry) => {
    setDeletingId(entry.id);
    try {
      await onDeleteEntry?.(entry);
    } finally {
      setDeletingId(null);
    }
  };

  const runGenerate = async () => {
    setGenerating(true);
    setGenerateNote(null);
    try {
      const result = await onGenerate?.(single ? { class_ids: [activeClass.id] } : {});
      setGenerateNote({ id: Date.now(), tone: "success", text: result?.message || "Timetable generated." });
    } catch (error) {
      setGenerateNote({ id: Date.now(), tone: "error", text: error?.message || "Could not generate the timetable." });
    } finally {
      setGenerating(false);
    }
  };

  /* ------------------------------------------------------------ cell content */

  const addLabel = (dayValue, row) =>
    `Add a lesson${className ? ` for ${className}` : ""} on ${dayName(dayValue)}, ${timeRange(row.start_time, row.end_time)}`;

  const renderCell = (dayValue, row, navProps, options = {}) => {
    const list = cells.get(cellKey(dayValue, row.start_time, row.end_time)) || [];
    const context = `${dayName(dayValue)}, ${timeRange(row.start_time, row.end_time)}`;

    if (!list.length) {
      if (unassignedOnly) return <span className="tt-blank" aria-hidden="true" />;
      return (
        <button
          type="button"
          className={`tt-add${single ? "" : " is-compact"}`}
          aria-label={addLabel(dayValue, row)}
          title={addLabel(dayValue, row)}
          onClick={() => onAddAt?.({ classId: activeClass ? activeClass.id : "", dayValue, start: row.start_time, end: row.end_time })}
          {...navProps}
        >
          <Plus size={13} aria-hidden="true" />
          {single ? <span>Add</span> : null}
        </button>
      );
    }

    if (single) {
      return list.map((entry, index) => (
        <EntryCard key={entry.id} entry={entry} subjectsById={subjectsById} context={context} onOpen={onOpenEntry} navProps={index === 0 ? navProps : undefined} detail={options.detail} />
      ));
    }

    // Up to three chips as they are; more than that collapses to two chips and a
    // "+N more" button, so every cell stays the same height.
    const shown = list.length <= CHIPS_PER_CELL ? list : list.slice(0, CHIPS_PER_CELL - 1);
    const hidden = list.length - shown.length;
    return (
      <div className="tt-chips">
        {shown.map((entry, index) => (
          <EntryChip key={entry.id} entry={entry} subjectsById={subjectsById} context={context} onOpen={onOpenEntry} navProps={index === 0 ? navProps : undefined} />
        ))}
        {hidden > 0 ? (
          <button
            type="button"
            className="tt-more"
            aria-label={`${list.length} classes at ${context}. Show all`}
            onClick={() => onOpenCell?.({ entries: list, dayValue, start: row.start_time, end: row.end_time })}
          >
            +{hidden} more
          </button>
        ) : list.length < CHIPS_PER_CELL ? (
          <button
            type="button"
            className="tt-more is-add"
            aria-label={`Add another class at ${context}`}
            title="Add another class"
            onClick={() => onAddAt?.({ classId: "", dayValue, start: row.start_time, end: row.end_time })}
          >
            <Plus size={12} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    );
  };

  /* --------------------------------------------------------------- keyboard */

  const onGridKeyDown = (event) => {
    const target = event.target.closest?.("[data-tt-nav]");
    if (!target || !["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
    const row = Number(target.dataset.r);
    const col = Number(target.dataset.c);
    const step = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[event.key];
    const root = bodyRef.current;
    if (!root) return;
    let r = row + step[0];
    let c = col + step[1];
    // skip break rows / gaps so the arrows never dead-end on a strip
    for (let guard = 0; guard < 40; guard += 1) {
      const next = root.querySelector(`[data-tt-nav][data-r="${r}"][data-c="${c}"]`);
      if (next) {
        event.preventDefault();
        next.focus();
        return;
      }
      if (r < -1 || r > 60 || c < -1 || c > 12) return;
      r += step[0];
      c += step[1];
    }
  };

  /* ------------------------------------------------------------------ pieces */

  const noClasses = classes.length === 0;
  const noPeriods = rows.length === 0;
  const emptyForClass = scoped.length === 0;

  const desktopGrid = (
    <div className="tt-scroller" role="region" aria-label={`Weekly timetable${className ? ` for ${className}` : ""}`} tabIndex={0} ref={bodyRef} onKeyDown={onGridKeyDown}>
      <table className={`tt-grid${single ? "" : " is-compact"}`}>
        <caption className="tt-sr">
          {single ? `${className} weekly timetable.` : "All classes weekly timetable."} Use the arrow keys to move between slots.
        </caption>
        <thead>
          <tr>
            <th scope="col" className="tt-corner">Time</th>
            {days.map((day) => {
              const today = Number(day.value) === todayValue;
              return (
                <th key={day.value} scope="col" className={`tt-day${today ? " is-today" : ""}`} aria-current={today ? "date" : undefined}>
                  <button
                    type="button"
                    className="tt-daybtn"
                    onClick={() => setFocusDay(Number(day.value))}
                    aria-label={`Show ${day.label} only`}
                    title={`Show ${day.label} only`}
                  >
                    <span>{day.label}</span>
                    {today ? <em>Today</em> : null}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => {
            const rowNow = isNowRow(row);
            const anyEntry = days.some((day) => (cells.get(cellKey(day.value, row.start_time, row.end_time)) || []).length > 0);
            const timeHead = (
              <th scope="row" className={`tt-time${rowNow ? " is-now" : ""}`}>
                <strong>{row.start_time}</strong>
                <span>{row.end_time}</span>
                {row.custom ? <small>Custom</small> : null}
                {rowNow ? <em>Now</em> : null}
              </th>
            );
            if (row.is_break && !anyEntry) {
              return (
                <tr key={`${row.start_time}-${row.end_time}`} className="tt-break">
                  {timeHead}
                  <td colSpan={days.length}>
                    <span className="tt-breaklabel"><Coffee size={14} aria-hidden="true" /> Break</span>
                  </td>
                </tr>
              );
            }
            return (
              <tr key={`${row.start_time}-${row.end_time}`}>
                {timeHead}
                {days.map((day, colIndex) => {
                  const today = Number(day.value) === todayValue;
                  return (
                    <td key={day.value} className={`tt-cell${today ? " is-today" : ""}${today && rowNow ? " is-now" : ""}`}>
                      {renderCell(Number(day.value), row, { "data-tt-nav": "", "data-r": rowIndex, "data-c": colIndex })}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  const dayView = (
    <div className={`tt-mobile${isNarrow ? "" : " is-wide"}`}>
      <DayTabs
        days={days}
        selected={selectedDay}
        todayValue={todayValue}
        counts={dayCounts}
        showWeek={!isNarrow}
        onSelect={setFocusDay}
        onWeek={() => setFocusDay(null)}
      />
      <ol className="tt-daylist">
        {rows.map((row) => {
          const list = cells.get(cellKey(selectedDay, row.start_time, row.end_time)) || [];
          const rowNow = Number(selectedDay) === todayValue && isNowRow(row);
          if (row.is_break && !list.length) {
            return (
              <li key={`${row.start_time}-${row.end_time}`} className="tt-daybreak">
                <Coffee size={14} aria-hidden="true" /> Break <small>{timeRange(row.start_time, row.end_time)}</small>
              </li>
            );
          }
          return (
            <li key={`${row.start_time}-${row.end_time}`} className={`tt-dayrow${rowNow ? " is-now" : ""}`}>
              <div className="tt-daytime">
                <strong>{row.start_time}</strong>
                <span>{row.end_time}</span>
                {rowNow ? <em>Now</em> : null}
              </div>
              <div className="tt-daycell">{renderCell(Number(selectedDay), row, undefined, { detail: true })}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );

  // View opens the details dialog (which has Edit and Delete); Delete asks first.
  const rowActions = (entry) => {
    const what = `${entryLabel(entry)} for ${entry.class_name}, ${dayName(entry.day_of_week)} ${timeRange(entry.start_time, entry.end_time)}`;
    return (
      <>
        <button type="button" className="tt-rowbtn" aria-label={`View ${what}`} onClick={() => onOpenEntry?.(entry)}>
          <Eye size={13} aria-hidden="true" /> View
        </button>
        <button
          type="button"
          className="tt-rowbtn is-danger"
          aria-label={`Delete ${what}`}
          disabled={deletingId === entry.id}
          onClick={() => deleteFromList(entry)}
        >
          {deletingId === entry.id ? <Spinner size={12} /> : <Trash2 size={13} aria-hidden="true" />} Delete
        </button>
      </>
    );
  };

  const teacherCell = (entry) =>
    entry.teacher_name ? (
      entry.teacher_name
    ) : needsTeacher(entry) ? (
      <span className="tt-badge"><AlertTriangle size={12} aria-hidden="true" /> No teacher yet</span>
    ) : (
      <span className="tt-muted">&mdash;</span>
    );

  const listBody = isNarrow ? (
    <div className="tt-listcards">
      {listGroups.map((group) => (
        <section key={group.day} className={`tt-listgroup${validFocus === group.day ? " is-focus" : ""}`} aria-label={`${dayName(group.day)} lessons`}>
          <h5 className="tt-listday">
            {dayName(group.day)} <small>{group.entries.length}</small>
            {group.day === todayValue ? <em>Today</em> : null}
          </h5>
          <ul>
            {group.entries.map((entry) => {
              const hue = hueStyle(entry);
              return (
                <li key={entry.id} className="tt-listcard">
                  <span className={`tt-dot${hue ? "" : " is-neutral"}`} style={hue} aria-hidden="true" />
                  <div className="tt-listcard-main">
                    <strong title={entryLabel(entry)}>{entryLabel(entry)}</strong>
                    <span>{timeRange(entry.start_time, entry.end_time)}{!single ? ` \u00b7 ${classTiny(entry.class_name)}` : ""}</span>
                    <span>{teacherCell(entry)}{entry.room ? ` \u00b7 ${entry.room}` : ""}</span>
                  </div>
                  <div className="tt-listcard-actions">{rowActions(entry)}</div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  ) : (
    <div className="tt-listwrap">
      <table className="tt-list">
        <thead>
          <tr>
            <th scope="col">Time</th>
            {!single ? <th scope="col">Class</th> : null}
            <th scope="col">Subject</th>
            <th scope="col">Teacher</th>
            <th scope="col">Room</th>
            <th scope="col"><span className="tt-sr">Actions</span></th>
          </tr>
        </thead>
        {listGroups.map((group) => (
          <tbody key={group.day} className={validFocus === group.day ? "is-focus" : undefined}>
            <tr className="tt-listday-row">
              <th scope="colgroup" colSpan={single ? 5 : 6}>
                <span className="tt-listday">{dayName(group.day)} <small>{group.entries.length} {group.entries.length === 1 ? "lesson" : "lessons"}</small></span>
                {group.day === todayValue ? <em>Today</em> : null}
              </th>
            </tr>
            {group.entries.map((entry) => {
              const hue = hueStyle(entry);
              return (
                <tr key={entry.id}>
                  <td className="tt-list-time">{timeRange(entry.start_time, entry.end_time)}</td>
                  {!single ? <td>{entry.class_name}</td> : null}
                  <td>
                    <span className={`tt-dot${hue ? "" : " is-neutral"}`} style={hue} aria-hidden="true" />
                    <span title={entryLabel(entry)}>{entryLabel(entry)}</span>
                  </td>
                  <td>{teacherCell(entry)}</td>
                  <td>{entry.room || <span className="tt-muted">&mdash;</span>}</td>
                  <td className="tt-list-actions">{rowActions(entry)}</td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );

  const listSection =
    noClasses || (!listEntries.length && !unassignedOnly) ? null : (
      <section className="tt-listsection" aria-label="All lessons in this timetable">
        <header className="tt-listhead">
          <h4>{single ? `Lessons for ${className}` : "Lessons for all classes"}</h4>
          <span className="tt-count">{listEntries.length}</span>
          <small>{unassignedOnly ? "Only lessons that still need a teacher" : "Everything in the timetable, day by day"}</small>
        </header>
        {listEntries.length ? listBody : <p className="panel-empty">Every lesson here has a teacher.</p>}
      </section>
    );

  return (
    <section className="tt-board" aria-label="Weekly schedule" ref={rootRef}>
      <header className="tt-head">
        <div className="tt-headtext">
          <h3>Weekly schedule</h3>
          <p>
            Generate fills empty slots only. Changes save automatically.
            <InfoTip id="tt-help-tip" label="More about Generate and saving">
              Generate only fills empty slots for the periods and school days in Timetable settings. It never changes or removes an
              entry that already exists, whether it was generated earlier or added by hand. Every change is saved the moment you make
              it &mdash; there is no separate save step.
            </InfoTip>
          </p>
        </div>
        <div className="tt-headactions">
          <button type="button" className="btn-secondary" onClick={() => onAddBlank?.({ classId: activeClass ? activeClass.id : "" })}>
            <CalendarPlus size={15} aria-hidden="true" /> Add lesson
          </button>
          <button type="button" className="btn-primary" onClick={runGenerate} disabled={generating || noClasses}>
            {generating ? <><Spinner size={12} /> Generating&hellip;</> : <><Sparkles size={15} aria-hidden="true" /> {single ? "Generate for this class" : "Generate all classes"}</>}
          </button>
        </div>
      </header>

      {noClasses ? null : <ClassPicker classes={classes} value={pickerValue} onChange={chooseClass} />}

      <div className="tt-toolbar">
        <label className={`tt-switch${unassignedOnly ? " is-on" : ""}`}>
          <input
            type="checkbox"
            role="switch"
            checked={unassignedOnly}
            disabled={unassignedCount === 0 && !unassignedOnly}
            onChange={(event) => setUnassignedOnly(event.target.checked)}
          />
          <span className="tt-switch-track" aria-hidden="true" />
          <span>Show unassigned only</span>
          <b className={unassignedCount ? "has-count" : ""}>{unassignedCount}</b>
        </label>

        <ul className="tt-legend" aria-label="Legend">
          <li><i className="tt-key tt-key-unassigned" aria-hidden="true" /> Needs a teacher</li>
          <li><i className="tt-key tt-key-today" aria-hidden="true" /> Today</li>
          <li><i className="tt-key tt-key-now" aria-hidden="true" /> Now</li>
        </ul>
      </div>

      {/* The app renders .form-feedback as a self-fading toast (bottom right), so this
          wrapper takes no space; the key restarts the fade for every new message. */}
      <div className="tt-status" role="status" aria-live="polite">
        {generateNote ? (
          <p key={`g${generateNote.id}`} className={`form-feedback ${generateNote.tone}`}>{generateNote.text}</p>
        ) : notice ? (
          <p key={`n${notice.id}`} className={`form-feedback ${notice.tone || "success"}`}>{notice.text}</p>
        ) : null}
      </div>

      {noClasses ? (
        <p className="panel-empty">Add classes first (Academics &rsaquo; Classes), then build their timetables here.</p>
      ) : noPeriods ? (
        <div className="tt-empty">
          <p>No periods are set up yet, so there is nothing to place lessons in.</p>
          <button type="button" className="btn-primary" onClick={onOpenSettings}>Set up periods</button>
        </div>
      ) : (
        <>
          {emptyForClass && !unassignedOnly ? (
            <p className="tt-hint">
              <Sparkles size={14} aria-hidden="true" /> {single ? `${className} has no lessons yet.` : "No lessons yet."} Click any <b>+ Add</b> slot, or use <b>Generate</b> to fill the week.
            </p>
          ) : null}
          {dayMode ? dayView : desktopGrid}
        </>
      )}

      {listSection}
    </section>
  );
}
