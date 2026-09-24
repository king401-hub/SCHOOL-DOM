// One dialog for everything you do to a slot: see it, edit it, remove it (with a
// confirmation), add to an empty one, or pick from the classes sharing a cell.
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, Clock3, DoorOpen, Pencil, Trash2, UserRound, Users, X } from "lucide-react";
import { Popup, Spinner } from "../../AppShared";
import { entryLabel, hueStyle, initialsOf, needsTeacher, timeRange } from "./timetableUtils";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

function blankForm({ entry, prefill, days }) {
  if (entry) {
    return {
      class_id: String(entry.class_id || ""),
      subject_id: String(entry.subject_id || ""),
      title: entry.title || "",
      teacher_id: entry.teacher_id || "",
      day_of_week: String(entry.day_of_week),
      start_time: entry.start_time || "",
      end_time: entry.end_time || "",
      room: entry.room || "",
    };
  }
  return {
    class_id: prefill?.classId ? String(prefill.classId) : "",
    subject_id: "",
    title: "",
    teacher_id: "",
    day_of_week: String(prefill?.dayValue ?? days[0]?.value ?? 0),
    start_time: prefill?.start || "",
    end_time: prefill?.end || "",
    room: "",
  };
}

function DialogBody({
  dialog,
  onClose,
  onSaved,
  classes,
  subjects,
  teachers,
  days,
  timeSlots = [],
  onCreate,
  onUpdate,
  onDelete,
  confirm,
}) {
  const [mode, setMode] = useState(dialog.mode);
  const [entry, setEntry] = useState(dialog.entry || null);
  const [from, setFrom] = useState(dialog.mode === "view" && dialog.entries?.length ? "cell" : "");
  const [form, setForm] = useState(() => blankForm({ entry: dialog.mode === "form" ? dialog.entry : null, prefill: dialog.prefill, days }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [customTime, setCustomTime] = useState(
    () => Boolean(form.start_time && form.end_time && !timeSlots.some((slot) => slot.start_time === form.start_time && slot.end_time === form.end_time))
  );
  // The "class, day or period" section starts open only when the slot isn't known yet
  // (a blank add). It is state, not derived, so picking a period doesn't collapse it.
  const [timeOpen, setTimeOpen] = useState(() => dialog.mode === "form" && !dialog.entry && !(dialog.prefill?.classId && dialog.prefill?.start && dialog.prefill?.end));
  const rootRef = useRef(null);

  const dayLabel = (value) => days.find((day) => String(day.value) === String(value))?.label || "";
  const className = (id) => {
    const found = classes.find((item) => String(item.id) === String(id));
    return found ? found.label || found.name : "";
  };

  // focus in, and hand focus back to whatever opened the dialog
  useEffect(() => {
    const previous = document.activeElement;
    return () => {
      if (previous && document.contains(previous)) previous.focus?.();
    };
  }, []);
  useEffect(() => {
    const target = rootRef.current?.querySelector("[data-autofocus]") || rootRef.current?.querySelector(FOCUSABLE);
    target?.focus?.();
  }, [mode, entry]);

  const onKeyDown = (event) => {
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
  };

  const selectedClass = classes.find((item) => String(item.id) === String(form.class_id));
  const subjectGroups = useMemo(() => {
    const classSubjectIds = new Set((selectedClass?.subjects || []).map((item) => String(item.id)));
    if (!classSubjectIds.size) return { primary: subjects, others: [] };
    return {
      primary: subjects.filter((item) => classSubjectIds.has(String(item.id))),
      others: subjects.filter((item) => !classSubjectIds.has(String(item.id))),
    };
  }, [selectedClass, subjects]);

  const setField = (name, value) => {
    setError("");
    setForm((current) => ({ ...current, [name]: value }));
  };

  // Pick a period instead of typing two times; "Custom time" keeps the old free entry.
  const matchedSlot = timeSlots.find((slot) => slot.start_time === form.start_time && slot.end_time === form.end_time);
  const periodValue = customTime ? "custom" : matchedSlot ? `${matchedSlot.start_time}|${matchedSlot.end_time}` : "";
  const choosePeriod = (value) => {
    setError("");
    if (value === "custom") {
      setCustomTime(true);
      return;
    }
    setCustomTime(false);
    if (!value) {
      setForm((current) => ({ ...current, start_time: "", end_time: "" }));
      return;
    }
    const [start, end] = value.split("|");
    setForm((current) => ({ ...current, start_time: start, end_time: end }));
  };

  const startEdit = (target) => {
    setEntry(target);
    setForm(blankForm({ entry: target, days }));
    setError("");
    setMode("form");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    if (!form.class_id) return setError("Choose a class.");
    if (!form.subject_id && !form.title.trim()) return setError("Choose a subject, or type a title such as Assembly.");
    if (!form.start_time || !form.end_time) return setError(customTime ? "Enter a start and end time." : "Choose a period.");
    setBusy(true);
    try {
      const payload = {
        class_id: form.class_id,
        subject_id: form.subject_id || null,
        title: form.title.trim(),
        teacher_id: form.teacher_id || null,
        day_of_week: Number(form.day_of_week),
        start_time: form.start_time,
        end_time: form.end_time,
        room: form.room.trim(),
      };
      const editing = mode === "form" && entry;
      if (editing) await onUpdate?.(entry.id, payload);
      else await onCreate?.(payload);
      const what = payload.title || subjects.find((item) => String(item.id) === String(payload.subject_id))?.name || "the lesson";
      const where = `${className(payload.class_id)}, ${dayLabel(payload.day_of_week)} ${timeRange(payload.start_time, payload.end_time)}`;
      onSaved(editing ? `Saved changes to ${what} (${where}).` : `Added ${what} to ${where}.`, payload.class_id);
    } catch (actionError) {
      setError(actionError?.message || "Could not save this lesson.");
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    if (!entry) return;
    const ok = await confirm?.({
      title: "Delete this lesson?",
      message: `${entryLabel(entry)} for ${entry.class_name}, ${dayLabel(entry.day_of_week)} ${timeRange(entry.start_time, entry.end_time)}. This can't be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setError("");
    setBusy(true);
    try {
      await onDelete?.(entry.id);
      onSaved(`Deleted ${entryLabel(entry)} from ${entry.class_name}, ${dayLabel(entry.day_of_week)} ${timeRange(entry.start_time, entry.end_time)}.`, entry.class_id);
    } catch (actionError) {
      setError(actionError?.message || "Could not delete this lesson.");
    } finally {
      setBusy(false);
    }
  };

  /* ------------------------------------------------------------------ views */

  let title = "";
  let subtitle = "";
  let content = null;

  if (mode === "cell") {
    title = `${dayLabel(dialog.cell?.dayValue)} · ${timeRange(dialog.cell?.start, dialog.cell?.end)}`;
    subtitle = `${dialog.entries.length} classes have a lesson at this time`;
    content = (
      <>
        <ul className="tt-celllist">
          {dialog.entries.map((item, index) => (
            <li key={item.id}>
              <button
                type="button"
                data-autofocus={index === 0 ? "" : undefined}
                onClick={() => {
                  setEntry(item);
                  setFrom("cell");
                  setMode("view");
                }}
              >
                <span className={`tt-dot${hueStyle(item) ? "" : " is-neutral"}`} style={hueStyle(item)} aria-hidden="true" />
                <span className="tt-celllist-main">
                  <strong>{entryLabel(item)}</strong>
                  <small>{item.class_name}</small>
                </span>
                <span className="tt-celllist-side">
                  {item.teacher_name ? item.teacher_name : needsTeacher(item) ? <span className="tt-badge"><AlertTriangle size={12} aria-hidden="true" /> No teacher yet</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="panel-form-actions">
          <button type="button" className="btn-secondary" onClick={() => onClose()}>Close</button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setEntry(null);
              setForm(blankForm({ entry: null, prefill: { classId: "", dayValue: dialog.cell.dayValue, start: dialog.cell.start, end: dialog.cell.end }, days }));
              setTimeOpen(true);
              setMode("form");
            }}
          >
            Add another class
          </button>
        </div>
      </>
    );
  } else if (mode === "view" && entry) {
    const unassigned = needsTeacher(entry);
    title = entryLabel(entry);
    subtitle = entry.class_name;
    content = (
      <>
        <div className={`tt-detail${hueStyle(entry) ? "" : " is-neutral"}`} style={hueStyle(entry)}>
          <span className={`tt-swatch${hueStyle(entry) ? "" : " is-neutral"}`} aria-hidden="true">{initialsOf(entryLabel(entry))}</span>
          <dl>
            <div>
              <dt><Clock3 size={14} aria-hidden="true" /> When</dt>
              <dd>{dayLabel(entry.day_of_week)} &middot; {timeRange(entry.start_time, entry.end_time)}</dd>
            </div>
            <div>
              <dt><UserRound size={14} aria-hidden="true" /> Teacher</dt>
              <dd>
                {entry.teacher_name ? entry.teacher_name : unassigned ? (
                  <span className="tt-badge"><AlertTriangle size={12} aria-hidden="true" /> No teacher yet</span>
                ) : (
                  <span className="tt-muted">Not needed</span>
                )}
              </dd>
            </div>
            <div>
              <dt><Users size={14} aria-hidden="true" /> Class</dt>
              <dd>{entry.class_name}</dd>
            </div>
            {entry.room ? (
              <div>
                <dt><DoorOpen size={14} aria-hidden="true" /> Room</dt>
                <dd>{entry.room}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        {unassigned ? <p className="tt-tip">Tip: choose Edit and pick a teacher so this lesson shows on their timetable too.</p> : null}
        {error ? <p className="tt-alert" role="alert">{error}</p> : null}
        <div className="panel-form-actions tt-actions-split">
          <button type="button" className="btn-danger" onClick={handleRemove} disabled={busy}>
            {busy ? <Spinner size={12} /> : <Trash2 size={14} aria-hidden="true" />} Delete
          </button>
          <span className="tt-spacer" />
          {from === "cell" ? (
            <button type="button" className="btn-secondary" onClick={() => { setEntry(null); setMode("cell"); }}>
              <ArrowLeft size={14} aria-hidden="true" /> Back
            </button>
          ) : null}
          <button type="button" className="btn-primary" data-autofocus="" onClick={() => startEdit(entry)}>
            <Pencil size={14} aria-hidden="true" /> Edit
          </button>
        </div>
      </>
    );
  } else {
    const editing = Boolean(entry);
    const slotKnown = Boolean(form.class_id && form.start_time && form.end_time);
    title = editing ? "Edit lesson" : "Add a lesson";
    subtitle = slotKnown ? `${className(form.class_id)} · ${dayLabel(form.day_of_week)} · ${timeRange(form.start_time, form.end_time)}` : "Choose the class, day and period, then the subject.";
    content = (
      <form className="tt-form" onSubmit={handleSubmit}>
        <div className="panel-form-grid">
          <label className="panel-field">
            Subject
            <select value={form.subject_id} onChange={(event) => setField("subject_id", event.target.value)} disabled={busy} data-autofocus="">
              <option value="">No subject</option>
              {subjectGroups.others.length ? (
                <>
                  <optgroup label="This class's subjects">
                    {subjectGroups.primary.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </optgroup>
                  <optgroup label="Other subjects">
                    {subjectGroups.others.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </optgroup>
                </>
              ) : (
                subjectGroups.primary.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)
              )}
            </select>
          </label>
          <label className="panel-field">
            Teacher
            <select value={form.teacher_id} onChange={(event) => setField("teacher_id", event.target.value)} disabled={busy}>
              <option value="">No teacher yet</option>
              {teachers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="panel-field">
            <span>Title <span className="tt-optional">(for breaks, assembly)</span></span>
            <input value={form.title} onChange={(event) => setField("title", event.target.value)} placeholder="e.g. Assembly, Lunch" disabled={busy} />
          </label>
          <label className="panel-field">
            <span>Room <span className="tt-optional">(optional)</span></span>
            <input value={form.room} onChange={(event) => setField("room", event.target.value)} placeholder="e.g. Block A, Room 3" disabled={busy} />
          </label>
        </div>

        <details className="tt-timefields" open={timeOpen} onToggle={(event) => setTimeOpen(event.currentTarget.open)}>
          <summary>Change class, day or period</summary>
          <div className="panel-form-grid">
            <label className="panel-field">
              Class
              <select value={form.class_id} onChange={(event) => setField("class_id", event.target.value)} disabled={busy}>
                <option value="">Choose a class</option>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.label || item.name}</option>)}
              </select>
            </label>
            <label className="panel-field">
              Day
              <select value={form.day_of_week} onChange={(event) => setField("day_of_week", event.target.value)} disabled={busy}>
                {days.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="panel-field full">
              Period
              <select value={periodValue} onChange={(event) => choosePeriod(event.target.value)} disabled={busy}>
                <option value="">Choose a period</option>
                {timeSlots.map((slot) => (
                  <option key={`${slot.start_time}|${slot.end_time}`} value={`${slot.start_time}|${slot.end_time}`}>
                    {slot.label || "Period"} &middot; {timeRange(slot.start_time, slot.end_time)}{slot.is_break ? " (break)" : ""}
                  </option>
                ))}
                <option value="custom">Custom time&hellip;</option>
              </select>
            </label>
            {customTime ? (
              <>
                <label className="panel-field">
                  Starts
                  <input type="time" value={form.start_time} onChange={(event) => setField("start_time", event.target.value)} disabled={busy} />
                </label>
                <label className="panel-field">
                  Ends
                  <input type="time" value={form.end_time} onChange={(event) => setField("end_time", event.target.value)} disabled={busy} />
                </label>
              </>
            ) : null}
          </div>
        </details>

        {error ? <p className="tt-alert" role="alert">{error}</p> : null}
        <div className="panel-form-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              if (editing) {
                setMode("view");
              } else if (dialog.entries?.length) {
                setMode("cell");
              } else {
                onClose();
              }
              setError("");
            }}
            disabled={busy}
          >
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? <><Spinner size={12} /> Saving&hellip;</> : editing ? "Save changes" : "Add lesson"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <div ref={rootRef} onKeyDown={onKeyDown} className="tt-dialog-body">
      <div className="edit-modal-head">
        <div>
          <h3 id="tt-dialog-title">{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        <button type="button" className="edit-modal-close" onClick={() => onClose()} aria-label="Close">
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="tt-dialog-content">{content}</div>
    </div>
  );
}

export default function TimetableEntryDialog({ open, dialog, onClose, ...rest }) {
  return (
    <Popup open={open} onClose={onClose} labelledBy="tt-dialog-title" extraCardClassName="tt-dialog">
      {dialog ? <DialogBody key={dialog.nonce} dialog={dialog} onClose={onClose} {...rest} /> : null}
    </Popup>
  );
}
