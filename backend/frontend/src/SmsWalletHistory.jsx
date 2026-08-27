import { useCallback, useEffect, useState } from "react";
import { requestJson, resolveSchoolBrand, resolveDocumentTheme, themeToCssVars, formatDate, openPrintableDocument } from "./AppShared";
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

function smsNaira(value) {
  return `₦${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// The transaction id (already sent to every client) doubles as a receipt
// number - the raw Paystack reference is deliberately stripped from every
// user-facing transaction payload server-side (see
// _sms_wallet_transaction_list_payload) and kept server-side only for
// reconciliation, so it must never be the thing printed on a receipt.
function smsReceiptNumber(tx) {
  return `SMS-${String(tx?.id || "").replace(/-/g, "").slice(0, 10).toUpperCase() || "RECEIPT"}`;
}

/** One document that covers both cases the school actually needs a paper
 * trail for: a completed purchase gets a payment receipt, anything that
 * didn't complete (or isn't a purchase at all - a debit/refund/admin
 * credit/adjustment) gets a plain transaction record/bill instead. */
export function SmsWalletReceiptDocument({ id, school, theme, transaction }) {
  const brand = resolveSchoolBrand(school);
  const docTheme = theme || resolveDocumentTheme(school);
  const tx = transaction || {};
  const isPurchase = tx.tx_type === "purchase";
  const isPaid = tx.status === "successful";
  const title = isPurchase ? (isPaid ? "PAYMENT RECEIPT" : "TRANSACTION BILL") : "TRANSACTION RECORD";
  const amount = Number(tx.amount || 0);
  const dateIso = tx.created_at ? new Date(tx.created_at).toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);

  return (
    <article id={id} className="official-document invoice-document" style={themeToCssVars(docTheme)}>
      <header className="invoice-doc-header">
        <div className="invoice-doc-brand">
          <div className="invoice-doc-logo">
            {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
          </div>
          <div>
            <strong>{brand.name}</strong>
            {brand.address ? <span>{brand.address}</span> : null}
            {brand.phone ? <span>{brand.phone}</span> : null}
            {brand.email ? <span>{brand.email}</span> : null}
          </div>
        </div>
        <div className="invoice-doc-title-block">
          <h2>{title}</h2>
          <table className="invoice-doc-meta-table">
            <tbody>
              <tr><td>Receipt No.</td><td>{smsReceiptNumber(tx)}</td></tr>
              <tr><td>Date</td><td>{formatDate(dateIso)}</td></tr>
              <tr><td>Payment Method</td><td style={{ textTransform: "capitalize" }}>{tx.provider || "Paystack"}</td></tr>
            </tbody>
          </table>
        </div>
      </header>

      <section className="invoice-doc-cards">
        <div className="invoice-doc-card">
          <div className="invoice-doc-card-head">Transaction Details</div>
          <div className="invoice-doc-card-body">
            <div><label>Description</label><strong>{tx.narration || "SMS wallet transaction"}</strong></div>
            <div><label>Type</label><strong style={{ textTransform: "capitalize" }}>{tx.tx_type || "-"}</strong></div>
            <div><label>Credits</label><strong>{tx.credits > 0 ? `+${tx.credits}` : tx.credits}</strong></div>
            <div><label>Balance After</label><strong>{tx.balance_after ?? "—"}</strong></div>
            <div><label>Status</label><strong style={{ textTransform: "capitalize" }}>{tx.status || "-"}</strong></div>
          </div>
        </div>
        <div className="invoice-doc-card summary">
          <div className="invoice-doc-card-head accent">{isPaid ? "Amount Paid" : "Amount"}</div>
          <div className="invoice-doc-card-body">
            <div className="invoice-doc-summary-total"><span>{isPaid ? "Amount Paid" : isPurchase ? "Amount Due" : "Amount"}</span><strong>{smsNaira(amount)}</strong></div>
          </div>
        </div>
      </section>

      <p className="invoice-doc-thanks">
        {isPurchase ? (isPaid ? "Thank you for your payment." : "This purchase was not completed.") : "This is a record of a wallet balance adjustment."}
      </p>
    </article>
  );
}

/** Shared by both places a transaction table shows up (the SMS Wallet page's
 * own Recent Transactions panel and the "View More" history modal) so the
 * print flow - render off-screen, wait a tick for it to paint, hand the
 * element to openPrintableDocument - only exists once. */
export function useSmsWalletReceipt(school) {
  const [printing, setPrinting] = useState(null);
  const [receiptError, setReceiptError] = useState("");
  const docTheme = resolveDocumentTheme(school);

  useEffect(() => {
    if (!printing) return undefined;
    const timer = setTimeout(() => {
      const title = `${printing.tx_type === "purchase" ? "Receipt" : "Transaction Record"} - ${smsReceiptNumber(printing)}`;
      Promise.resolve(openPrintableDocument("sms-receipt-print-doc", title, docTheme))
        .catch((err) => setReceiptError(err.message || "Could not open the printable receipt."))
        .finally(() => setPrinting(null));
    }, 60);
    return () => clearTimeout(timer);
  }, [printing]);

  const printReceipt = (transaction) => {
    setReceiptError("");
    setPrinting(transaction);
  };

  const receiptNode = printing ? (
    <div style={{ position: "fixed", top: 0, left: "-9999px", zIndex: -1 }}>
      <SmsWalletReceiptDocument id="sms-receipt-print-doc" school={school} theme={docTheme} transaction={printing} />
    </div>
  ) : null;

  return { printReceipt, receiptNode, receiptError };
}

export function SmsTransactionHistoryModal({ session, school, onClose }) {
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;
  const { printReceipt, receiptNode, receiptError } = useSmsWalletReceipt(school);

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
        {receiptError ? <p className="form-feedback error">{receiptError}</p> : null}

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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7}>Loading...</td>
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
                    <td>
                      <button type="button" className="table-action sms-receipt-btn" onClick={() => printReceipt(tx)}>
                        {tx.tx_type === "purchase" && tx.status === "successful" ? "Receipt" : "Record"}
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>No transactions found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {receiptNode}

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
