import { useEffect, useMemo, useState } from "react";

/* The full history behind any Finance record table, in the same popup shape the
   SMS wallet already uses: search, date range, an optional status filter, and
   Prev/Next paging.

   Filtering happens on rows the screen already loaded rather than over the
   network - the finance overview ships these records with the page, so a
   round-trip per keystroke would buy nothing. Row markup is passed in by the
   caller as `renderRow`, the same function its preview table uses, so the two
   can never drift apart. */
const PAGE_SIZE = 20;

function toTime(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
}

export function FinanceHistoryModal({
  title,
  description,
  columns,
  rows,
  renderRow,
  searchText,
  dateOf,
  statusOf,
  classOf,
  methodOf,
  onClose,
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, classFilter, methodFilter, startDate, endDate]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  // Offered only when the data actually carries a status, and built from the
  // values present rather than a hardcoded list, so no table gets a filter that
  // matches nothing.
  const statusOptions = useMemo(() => {
    if (!statusOf) return [];
    const seen = new Set();
    rows.forEach((row) => {
      const value = statusOf(row);
      if (value) seen.add(String(value));
    });
    return Array.from(seen).sort();
  }, [rows, statusOf]);

  // Same "built from the values present" approach as statusOptions, so a
  // school with only three classes never sees the other four hundred that
  // exist elsewhere on the platform.
  const classOptions = useMemo(() => {
    if (!classOf) return [];
    const seen = new Set();
    rows.forEach((row) => {
      const value = classOf(row);
      if (value) seen.add(String(value));
    });
    return Array.from(seen).sort();
  }, [rows, classOf]);

  // Same approach again for payment method - only offers Cash/Bank Transfer/
  // POS/etc. once a payment of that kind actually exists in this table.
  const methodOptions = useMemo(() => {
    if (!methodOf) return [];
    const seen = new Set();
    rows.forEach((row) => {
      const value = methodOf(row);
      if (value) seen.add(String(value));
    });
    return Array.from(seen).sort();
  }, [rows, methodOf]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const from = startDate ? toTime(`${startDate}T00:00:00`) : null;
    const to = endDate ? toTime(`${endDate}T23:59:59`) : null;

    return rows.filter((row) => {
      if (needle && searchText) {
        const haystack = (searchText(row) || [])
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      if (statusFilter && statusOf && String(statusOf(row) || "") !== statusFilter) return false;
      if (classFilter && classOf && String(classOf(row) || "") !== classFilter) return false;
      if (methodFilter && methodOf && String(methodOf(row) || "") !== methodFilter) return false;
      if ((from || to) && dateOf) {
        const stamp = toTime(dateOf(row));
        if (stamp === null) return false;
        if (from && stamp < from) return false;
        if (to && stamp > to) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter, classFilter, methodFilter, startDate, endDate, searchText, statusOf, classOf, methodOf, dateOf]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const hasFilters = Boolean(searchText || dateOf || statusOptions.length || classOptions.length || methodOptions.length);

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="finance-history-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <article className="app-panel edit-modal-card finance-history-modal" style={{ maxWidth: "72rem" }}>
        <div className="edit-modal-head">
          <div>
            <h3 id="finance-history-title">{title}</h3>
            <p>{description || "Complete history, newest first."}</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {hasFilters ? (
          <div className="panel-form-grid">
            {searchText ? (
              <label className="panel-field">
                Search
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search records..." />
              </label>
            ) : null}
            {statusOptions.length ? (
              <label className="panel-field">
                Status
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="">All statuses</option>
                  {statusOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {classOptions.length ? (
              <label className="panel-field">
                Class
                <select value={classFilter} onChange={(event) => setClassFilter(event.target.value)}>
                  <option value="">All classes</option>
                  {classOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {methodOptions.length ? (
              <label className="panel-field">
                Payment Method
                <select value={methodFilter} onChange={(event) => setMethodFilter(event.target.value)}>
                  <option value="">All methods</option>
                  {methodOptions.map((option) => (
                    <option key={option} value={option}>{option.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {dateOf ? (
              <>
                <label className="panel-field">
                  Start Date
                  <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                </label>
                <label className="panel-field">
                  End Date
                  <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
                </label>
              </>
            ) : null}
          </div>
        ) : null}

        <div style={{ overflowX: "auto", marginTop: "1rem" }}>
          <table className="data-table">
            <thead>
              <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
            </thead>
            <tbody>
              {pageRows.length
                ? pageRows.map(renderRow)
                : <tr><td colSpan={columns.length}>No records match those filters.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="panel-form-actions" style={{ justifyContent: "space-between", marginTop: "0.75rem" }}>
          <button type="button" className="btn-secondary" disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Prev
          </button>
          <span>
            Page {safePage} of {totalPages} &bull; {filtered.length} record{filtered.length === 1 ? "" : "s"}
          </span>
          <button type="button" className="btn-secondary" disabled={safePage >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
            Next
          </button>
        </div>
      </article>
    </div>
  );
}
