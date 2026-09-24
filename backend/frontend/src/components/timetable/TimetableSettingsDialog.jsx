// Timetable settings in a popup: periods a day, how long each is, when the day
// starts, which days are school days and which periods are breaks.
import { useRef, useState } from "react";
import { X } from "lucide-react";
import { Popup, Spinner } from "../../AppShared";
import "./timetable.css";
import { useDialogFocus } from "./TimetableParts";

const SCHOOL_DAYS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
];

function Body({ settings, onClose, onSave, onSaved }) {
  const [form, setForm] = useState(() => ({
    periods_per_day: String(settings?.periods_per_day ?? 8),
    period_duration_minutes: String(settings?.period_duration_minutes ?? 40),
    day_start_time: settings?.day_start_time || "08:00",
    school_days: settings?.school_days || [0, 1, 2, 3, 4],
    break_periods: settings?.break_periods || [],
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rootRef = useRef(null);
  const onKeyDown = useDialogFocus(rootRef, "open");

  const setField = (name, value) => {
    setError("");
    setForm((current) => ({ ...current, [name]: value }));
  };
  const toggle = (name, value) =>
    setForm((current) => {
      setError("");
      const has = current[name].includes(value);
      const next = has ? current[name].filter((item) => item !== value) : [...current[name], value].sort((a, b) => a - b);
      return { ...current, [name]: next };
    });

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    if (!form.school_days.length) {
      setError("Select at least one school day.");
      return;
    }
    setBusy(true);
    try {
      const periods = Number(form.periods_per_day);
      const result = await onSave?.({
        periods_per_day: periods,
        period_duration_minutes: Number(form.period_duration_minutes),
        day_start_time: form.day_start_time,
        school_days: form.school_days,
        break_periods: form.break_periods.filter((period) => period <= periods),
      });
      onSaved(result?.message || "Timetable settings saved.");
    } catch (actionError) {
      setError(actionError?.message || "Could not save timetable settings.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div ref={rootRef} onKeyDown={onKeyDown} className="tt-dialog-body">
      <div className="edit-modal-head">
        <div>
          <h3 id="tt-settings-title">Timetable settings</h3>
          <p>Periods, their length and the school days. The weekly schedule and Generate both use these.</p>
        </div>
        <button type="button" className="edit-modal-close" onClick={() => onClose()} aria-label="Close">
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="tt-dialog-content">
        <form className="tt-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid tt-settings-grid">
            <label className="panel-field">
              Periods per day
              <input type="number" min="1" max="20" value={form.periods_per_day} onChange={(event) => setField("periods_per_day", event.target.value)} disabled={busy} data-autofocus="" />
            </label>
            <label className="panel-field">
              Period length (minutes)
              <input type="number" min="5" max="240" value={form.period_duration_minutes} onChange={(event) => setField("period_duration_minutes", event.target.value)} disabled={busy} />
            </label>
            <label className="panel-field full">
              Day starts at
              <input type="time" value={form.day_start_time} onChange={(event) => setField("day_start_time", event.target.value)} disabled={busy} />
            </label>
            <fieldset className="tt-checkgroup full">
              <legend>School days</legend>
              <div>
                {SCHOOL_DAYS.map((day) => (
                  <label key={day.value} className="tt-check">
                    <input type="checkbox" checked={form.school_days.includes(day.value)} onChange={() => toggle("school_days", day.value)} disabled={busy} />
                    <span>{day.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset className="tt-checkgroup full">
              <legend>Break periods</legend>
              <div>
                {Array.from({ length: Math.max(0, Number(form.periods_per_day) || 0) }, (_, i) => i + 1).map((index) => (
                  <label key={index} className="tt-check">
                    <input type="checkbox" checked={form.break_periods.includes(index)} onChange={() => toggle("break_periods", index)} disabled={busy} />
                    <span>Period {index}</span>
                  </label>
                ))}
              </div>
              <small>Breaks are skipped by Generate and shown as &ldquo;Break&rdquo; for every class.</small>
            </fieldset>
          </div>
          {error ? <p className="tt-alert" role="alert">{error}</p> : null}
          <div className="panel-form-actions">
            <button type="button" className="btn-secondary" onClick={() => onClose()} disabled={busy}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? <><Spinner size={12} /> Saving&hellip;</> : "Save settings"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function TimetableSettingsDialog({ open, onClose, settings, onSave, onSaved }) {
  return (
    <Popup open={open} onClose={onClose} labelledBy="tt-settings-title" extraCardClassName="tt-dialog tt-settingsdialog">
      <Body settings={settings} onClose={onClose} onSave={onSave} onSaved={onSaved} />
    </Popup>
  );
}
