export const NAIRA_SYMBOL = "₦";

export function formatMoney(value) {
  const amount = Number(value || 0);
  return `${NAIRA_SYMBOL}${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDay(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Clock-in/out timestamps show the time of day; the date is already its own column. */
export function formatClockTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export const REASON_COLORS = {
  graduated: "#0ea5e9",
  transferred: "#9333ea",
  withdrawn: "#f59e0b",
  deleted: "#dc2626",
  manual: "#6b7280",
};

export const FEE_STATUS_COLORS = {
  paid: "#16a34a",
  partial: "#f59e0b",
  pending: "#0ea5e9",
  overdue: "#dc2626",
};

export const ATTENDANCE_COLORS = {
  present: "#16a34a",
  late: "#f59e0b",
  absent: "#dc2626",
};

export function AlumniPill({ value, colorMap = {}, fallback = "#6b7280" }) {
  if (!value) return <span className="alumni-muted">-</span>;
  const color = colorMap[value] || fallback;
  return (
    <span className="alumni-pill" style={{ background: color }}>
      {String(value).replace(/_/g, " ")}
    </span>
  );
}

/** Renders "-" for anything the archive has no value for, so an empty cell is
 *  always deliberate rather than a rendering gap. */
export function Value({ children }) {
  const empty = children === null || children === undefined || children === "" || children === "-";
  if (empty) return <span className="alumni-muted">-</span>;
  return <>{children}</>;
}

export function EmptySection({ label }) {
  return <p className="alumni-empty">No {label} on record for this student.</p>;
}
