export const CONDITION_COLORS = {
  new: "#16a34a",
  good: "#0ea5e9",
  fair: "#f59e0b",
  damaged: "#dc2626",
  under_repair: "#9333ea",
  lost: "#6b7280",
  disposed: "#374151",
};

export const ASSIGNMENT_STATUS_COLORS = {
  borrowed: "#0ea5e9",
  returned: "#16a34a",
  overdue: "#dc2626",
  lost: "#6b7280",
};

export const MOVEMENT_TYPE_LABELS = {
  add: "Stock Added",
  remove: "Stock Removed",
  transfer: "Transferred",
  issue: "Issued",
  return: "Returned",
  dispose: "Disposed",
};

export function InventoryPill({ value, colorMap }) {
  const color = colorMap[value] || "#6b7280";
  const label = String(value || "").replace(/_/g, " ");
  return (
    <span className="inventory-pill" style={{ background: color }}>
      {label}
    </span>
  );
}

export const NAIRA_SYMBOL = "₦";

export function formatMoney(value) {
  const amount = Number(value || 0);
  return `${NAIRA_SYMBOL}${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
