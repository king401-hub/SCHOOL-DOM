// The admin "Weekly schedule": one class at a time by default, one calm card per
// slot, colour per subject, click a subject to edit it, click an empty slot to add.
// All-classes view collapses into compact chips, phones work one day at a time, and
// under the grid sits the list of class timetables (view / delete each one).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CalendarPlus, Coffee, Eye, Info, Plus, Sparkles, Trash2 } from "lucide-react";
import { Spinner } from "../../AppShared";
import "./timetable.css";
import { DayTabs, EntryCard, useNarrow } from "./TimetableParts";
import {
  ALL_CLASSES,
  buildRows,
  cellKey,
  classTiny,
  entryLabel,
  groupByCell,
  hueStyle,
  needsTeacher,
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

/* --------------------------------------------------------------------- cards */

function EntryChip({ entry, context, onOpen, navProps }) {
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
      <b>{subjectTiny(entry)}</b>
      <span>{classTiny(entry.class_name)}</span>
      {unassigned ? <i className="tt-chip-dot" aria-hidden="true" /> : null}
    </button>
  );
}

/* ----------------------------------------------------------------- the board */

export default function TimetableBoard({
  entries = [],
  classes = [],
  days = [],
  timeSlots = [],
  notice = null,
  jumpTo = null,
  onOpenEntry,
  onOpenCell,
  onAddAt,
  onAddBlank,
  onViewClass,
  onDeleteClass,
  onGenerate,
  onOpenSettings,
}) {
  const [classChoice, setClassChoice] = useState(() => readStored(CLASS_STORAGE_KEY));
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [focusDay, setFocusDay] = useState(null); // null = the whole week
  const [deletingClassId, setDeletingClassId] = useState(null);
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
  const dayCounts = useMemo(() => {
    const counts = new Map();
    visible.forEach((entry) => counts.set(Number(entry.day_of_week), (counts.get(Number(entry.day_of_week)) || 0) + 1));
    return counts;
  }, [visible]);
  // One row per class that has a timetable (counted over ALL entries, not the filtered view).
  const classRows = useMemo(() => {
    const byClass = new Map();
    entries.forEach((entry) => {
      const key = String(entry.class_id);
      const row = byClass.get(key) || { count: 0, missing: 0, ids: [] };
      row.count += 1;
      if (needsTeacher(entry)) row.missing += 1;
      row.ids.push(entry.id);
      byClass.set(key, row);
    });
    return classes.filter((item) => byClass.has(String(item.id))).map((item) => ({ cls: item, ...byClass.get(String(item.id)) }));
  }, [entries, classes]);

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

  const deleteClass = async (row) => {
    setDeletingClassId(row.cls.id);
    try {
      await onDeleteClass?.({ classId: row.cls.id, label: row.cls.label || row.cls.name, entryIds: row.ids, count: row.count });
    } finally {
      setDeletingClassId(null);
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
        <EntryCard key={entry.id} entry={entry} context={context} onOpen={onOpenEntry} navProps={index === 0 ? navProps : undefined} detail={options.detail} />
      ));
    }

    // Up to three chips as they are; more than that collapses to two chips and a
    // "+N more" button, so every cell stays the same height.
    const shown = list.length <= CHIPS_PER_CELL ? list : list.slice(0, CHIPS_PER_CELL - 1);
    const hidden = list.length - shown.length;
    return (
      <div className="tt-chips">
        {shown.map((entry, index) => (
          <EntryChip key={entry.id} entry={entry} context={context} onOpen={onOpenEntry} navProps={index === 0 ? navProps : undefined} />
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

  const classListSection = noClasses ? null : (
    <section className="tt-classes" aria-label="Class timetables">
      <header className="tt-listhead">
        <h4>Class timetables</h4>
        <span className="tt-count">{classRows.length}</span>
        <small>Every class that has a timetable</small>
      </header>
      {classRows.length ? (
        <ul className="tt-classlist">
          {classRows.map((row) => {
            const label = row.cls.label || row.cls.name;
            const onGrid = single && String(activeClass.id) === String(row.cls.id);
            return (
              <li key={row.cls.id} className={`tt-classrow${onGrid ? " is-active" : ""}`}>
                <div className="tt-classrow-main">
                  <strong>{label}</strong>
                  <span>{row.count} {row.count === 1 ? "lesson" : "lessons"}</span>
                  {row.missing ? (
                    <span className="tt-badge"><AlertTriangle size={12} aria-hidden="true" /> {row.missing} need a teacher</span>
                  ) : (
                    <span className="tt-okbadge">Every lesson has a teacher</span>
                  )}
                </div>
                <div className="tt-classrow-actions">
                  <button type="button" className="tt-rowbtn" aria-label={`View the ${label} timetable`} onClick={() => onViewClass?.(row.cls.id)}>
                    <Eye size={13} aria-hidden="true" /> View
                  </button>
                  <button
                    type="button"
                    className="tt-rowbtn is-danger"
                    aria-label={`Delete the ${label} timetable`}
                    disabled={deletingClassId === row.cls.id}
                    onClick={() => deleteClass(row)}
                  >
                    {deletingClassId === row.cls.id ? <Spinner size={12} /> : <Trash2 size={13} aria-hidden="true" />} Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="panel-empty">No class has a timetable yet. Use Generate, or click a + Add slot above.</p>
      )}
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

      {classListSection}
    </section>
  );
}
