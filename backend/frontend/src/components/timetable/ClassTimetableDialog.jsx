// "View" on a class: that class's whole week in a popup. Click a subject to edit
// it (the edit popup opens on top), or click an empty slot to add a lesson.
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Coffee, Plus, X } from "lucide-react";
import { Popup } from "../../AppShared";
import "./timetable.css";
import { DayTabs, EntryCard, useDialogFocus, useNarrow } from "./TimetableParts";
import { buildRows, cellKey, groupByCell, needsTeacher, timeRange, toMinutes, weekdayIndex } from "./timetableUtils";

function Body({ cls, entries, days, timeSlots, onClose, onEditEntry, onAddAt }) {
  const rootRef = useRef(null);
  const contentRef = useRef(null);
  const onKeyDown = useDialogFocus(rootRef, cls.id);
  const narrow = useNarrow(contentRef, 640);
  const [focusDay, setFocusDay] = useState(null);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const label = cls.label || cls.name;
  const rows = buildRows(timeSlots, entries);
  const cells = groupByCell(entries);
  const missing = entries.filter(needsTeacher).length;
  const todayValue = weekdayIndex(now);
  const minutesNow = now.getHours() * 60 + now.getMinutes();
  const dayValues = days.map((day) => Number(day.value));
  const selectedDay = focusDay !== null && dayValues.includes(focusDay) ? focusDay : dayValues.includes(todayValue) ? todayValue : dayValues[0];
  const dayName = (value) => days.find((day) => Number(day.value) === Number(value))?.label || "";
  const dayCounts = new Map();
  entries.forEach((entry) => dayCounts.set(Number(entry.day_of_week), (dayCounts.get(Number(entry.day_of_week)) || 0) + 1));

  const isNowRow = (row) => {
    const start = toMinutes(row.start_time);
    const end = toMinutes(row.end_time);
    return start !== null && end !== null && minutesNow >= start && minutesNow < end;
  };

  let firstCard = true; // the first lesson takes focus when the popup opens
  const renderCell = (dayValue, row) => {
    const list = cells.get(cellKey(dayValue, row.start_time, row.end_time)) || [];
    const context = `${dayName(dayValue)}, ${timeRange(row.start_time, row.end_time)}`;
    if (!list.length) {
      return (
        <button
          type="button"
          className="tt-add"
          aria-label={`Add a lesson for ${label} on ${context}`}
          onClick={() => onAddAt?.({ classId: cls.id, dayValue, start: row.start_time, end: row.end_time })}
        >
          <Plus size={13} aria-hidden="true" />
          <span>Add</span>
        </button>
      );
    }
    return list.map((entry) => {
      const navProps = firstCard ? { "data-autofocus": "" } : undefined;
      firstCard = false;
      return <EntryCard key={entry.id} entry={entry} context={context} onOpen={onEditEntry} navProps={navProps} detail={narrow} />;
    });
  };

  const grid = (
    <div className="tt-scroller tt-classscroller" role="region" aria-label={`${label} weekly timetable`} tabIndex={0}>
      <table className="tt-grid">
        <caption className="tt-sr">{label} weekly timetable. Choose a subject to edit it.</caption>
        <thead>
          <tr>
            <th scope="col" className="tt-corner">Time</th>
            {days.map((day) => {
              const today = Number(day.value) === todayValue;
              return (
                <th key={day.value} scope="col" className={`tt-day${today ? " is-today" : ""}`} aria-current={today ? "date" : undefined}>
                  <span className="tt-daystatic">
                    <span>{day.label}</span>
                    {today ? <em>Today</em> : null}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
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
                {days.map((day) => {
                  const today = Number(day.value) === todayValue;
                  return (
                    <td key={day.value} className={`tt-cell${today ? " is-today" : ""}${today && rowNow ? " is-now" : ""}`}>
                      {renderCell(Number(day.value), row)}
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

  const dayList = (
    <div className="tt-mobile">
      <DayTabs days={days} selected={selectedDay} todayValue={todayValue} counts={dayCounts} showWeek={false} onSelect={setFocusDay} onWeek={() => setFocusDay(null)} />
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
              <div className="tt-daycell">{renderCell(Number(selectedDay), row)}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );

  return (
    <div ref={rootRef} onKeyDown={onKeyDown} className="tt-dialog-body">
      <div className="edit-modal-head">
        <div>
          <h3 id="tt-class-title">{label} timetable</h3>
          <p>
            {entries.length} {entries.length === 1 ? "lesson" : "lessons"}
            {missing ? <> &middot; <span className="tt-badge"><AlertTriangle size={12} aria-hidden="true" /> {missing} need a teacher</span></> : null}
            {" "}&middot; Click a subject to edit it
          </p>
        </div>
        <button type="button" className="edit-modal-close" onClick={() => onClose()} aria-label="Close">
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="tt-dialog-content" ref={contentRef}>
        {rows.length === 0 ? <p className="panel-empty">No periods are set up yet. Set them up in Timetable settings first.</p> : narrow ? dayList : grid}
        <div className="panel-form-actions">
          <button type="button" className="btn-secondary" onClick={() => onClose()}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default function ClassTimetableDialog({ open, view, onClose, classes, entries, ...rest }) {
  const cls = view ? classes.find((item) => String(item.id) === String(view.id)) : null;
  const classEntries = view ? entries.filter((item) => String(item.class_id) === String(view.id)) : [];
  return (
    <Popup open={open} onClose={onClose} labelledBy="tt-class-title" extraCardClassName="tt-dialog tt-classdialog">
      {cls ? <Body key={view.nonce} cls={cls} entries={classEntries} onClose={onClose} {...rest} /> : null}
    </Popup>
  );
}
