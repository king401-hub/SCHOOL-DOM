import { useCallback, useEffect, useState } from "react";
import { requestJson } from "./AppShared";
import { CbtStatusPill } from "./AdminScreens";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "successful", label: "Successful" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "pending", label: "Pending" },
];

const TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "purchase", label: "Purchase" },
  { value: "debit", label: "Debit" },
  { value: "refund", label: "Refund" },
  { value: "admin_credit", label: "Admin Credit" },
  { value: "adjustment", label: "Adjustment" },
];

export function smsWalletStatusTone(statusValue) {
  if (statusValue === "successful") return "success";
  if (statusValue === "failed") return "danger";
  if (statusValue === "cancelled") return "warning";
  return "info";
}

export function smsWalletStatusLabel(statusValue) {
  const found = STATUS_OPTIONS.find((option) => option.value === statusValue);
  return found ? found.label : statusValue || "-";
}

export function SmsWalletStatusPill({ status: statusValue }) {
  return <CbtStatusPill tone={smsWalletStatusTone(statusValue)}>{smsWalletStatusLabel(statusValue)}</CbtStatusPill>;
}

export function SmsTransactionHistoryModal({ session, onClose }) {
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setPage(1);
  }, [statusFilter, typeFilter, search, startDate, endDate]);

  const fetchHistory = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (typeFilter) params.set("tx_type", typeFilter);
      if (search) params.set("search", search);
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      params.set("page", String(page));
      params.set("limit", String(limit));
      const res = await requestJson(session, "GET", `/api/finance/admin/sms-wallet/transactions/?${params.toString()}`);
      setResult(res);
    } catch (fetchError) {
      setError(fetchError.message || "Could not load transaction history.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [session, statusFilter, typeFilter, search, startDate, endDate, page]);

  useEffect(() => {
    const timer = window.setTimeout(fetchHistory, 300);
    return () => window.clearTimeout(timer);
  }, [fetchHistory]);

  const rows = result?.results || [];
  const totalPages = result ? Math.max(1, Math.ceil((result.count || 0) / limit)) : 1;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sms-history-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <article className="app-panel edit-modal-card" style={{ maxWidth: "56rem" }}>
        <div className="edit-modal-head">
          <div>
            <h3 id="sms-history-title">SMS Wallet Transaction History</h3>
            <p>Complete wallet activity, newest first.</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="panel-form-grid">
          <label className="panel-field">
            Search
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search narration..." />
          </label>
          <label className="panel-field">
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            Type
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
              {TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            Start Date
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="panel-field">
            End Date
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </div>

        {error ? <p className="form-feedback error">{error}</p> : null}

        <div style={{ overflowX: "auto", marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Narration</th>
                <th>Status</th>
                <th>Credits</th>
                <th>Balance After</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6}>Loading...</td>
                </tr>
              ) : rows.length ? (
                rows.map((tx) => (
                  <tr key={tx.id}>
                    <td>{tx.created_at ? new Date(tx.created_at).toLocaleString() : ""}</td>
                    <td style={{ textTransform: "capitalize" }}>{tx.tx_type}</td>
                    <td>{tx.narration || "-"}</td>
                    <td>
                      <SmsWalletStatusPill status={tx.status} />
                    </td>
                    <td>{tx.credits > 0 ? `+${tx.credits}` : tx.credits}</td>
                    <td>{tx.balance_after ?? "—"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>No transactions found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {result ? (
          <div className="panel-form-actions" style={{ justifyContent: "space-between", marginTop: "0.75rem" }}>
            <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Prev
            </button>
            <span>
              Page {page} of {totalPages} &bull; {result.count} record{result.count === 1 ? "" : "s"}
            </span>
            <button type="button" className="btn-secondary" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
              Next
            </button>
          </div>
        ) : null}
      </article>
    </div>
  );
}
