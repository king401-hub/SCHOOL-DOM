// Small pieces shared by the timetable board and the popups around it.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { AlertTriangle, LayoutGrid } from "lucide-react";
import { entryLabel, hueStyle, needsTeacher, shortDay, subjectShort } from "./timetableUtils";

/** Judged by an element's own width, not the window's: with the sidebar open a
 *  tablet leaves the board barely wider than a phone. */
export function useNarrow(ref, limit) {
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

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

/** Focus moves into a dialog, Tab stays inside it, and focus goes back to whatever
 *  opened it. `refocusKey` re-runs the "move focus in" step when the content changes.
 *  Returns the onKeyDown to put on the dialog's root element. */
export function useDialogFocus(rootRef, refocusKey) {
  useEffect(() => {
    const previous = document.activeElement;
    return () => {
      if (previous && document.contains(previous)) previous.focus?.();
    };
  }, []);
  useEffect(() => {
    const root = rootRef.current;
    const target = root?.querySelector("[data-autofocus]") || root?.querySelector(FOCUSABLE);
    target?.focus?.();
  }, [rootRef, refocusKey]);
  return useCallback(
    (event) => {
      if (event.key !== "Tab") return;
      const nodes = [...(rootRef.current?.querySelectorAll(FOCUSABLE) || [])].filter((node) => node.offsetParent !== null);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [rootRef]
  );
}

/** Clicking a weekday (grid header, or these tabs) switches to that day. */
export function DayTabs({ days, selected, todayValue, counts, showWeek, onSelect, onWeek }) {
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

/** One lesson: the short subject name, the teacher only if there is one, and a
 *  dashed outline + warning mark (never colour alone) when a teacher is missing.
 *  Clicking it opens the edit popup. */
export function EntryCard({ entry, context, onOpen, navProps, detail = false }) {
  const unassigned = needsTeacher(entry);
  const full = entryLabel(entry);
  const hue = hueStyle(entry);
  const teacher = entry.teacher_name;
  const aria = `${full}, ${entry.class_name}. ${teacher ? `Teacher ${teacher}` : unassigned ? "No teacher assigned" : "No teacher needed"}${entry.room ? `. Room ${entry.room}` : ""}. ${context}. Edit`;
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
