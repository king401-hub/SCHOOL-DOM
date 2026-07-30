import { Fragment, useMemo, useState } from "react";
import { ScreenState, formatDate } from "./AppShared";

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "retrying", label: "Retrying" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "expired", label: "Expired" },
];

const NON_TERMINAL_STATUSES = new Set(["pending", "queued", "processing", "retrying"]);

export default function RequestQueueScreen({ data, loading, error, onRetry, onManualRetry, onCancelRequest }) {
  const requests = data?.requests || [];
  const stats = data?.stats || {};
  const [activeFilter, setActiveFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedId, setExpandedId] = useState("");
  const [actionBusyId, setActionBusyId] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionFeedback, setActionFeedback] = useState("");

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return requests.filter((item) => {
      if (activeFilter !== "all" && item.status !== activeFilter) return false;
      if (!term) return true;
      return (
        item.id.toLowerCase().includes(term) ||
        item.request_type.toLowerCase().includes(term) ||
        (item.requester || "").toLowerCase().includes(term) ||
        (item.requester_email || "").toLowerCase().includes(term)
      );
    });
  }, [requests, activeFilter, searchTerm]);

  const runAction = async (action, requestId, successMessage) => {
    setActionBusyId(requestId);
    setActionError("");
    setActionFeedback("");
    try {
      await action(requestId);
      setActionFeedback(successMessage);
      await onRetry?.();
    } catch (err) {
      setActionError(err?.message || "Action failed.");
    } finally {
      setActionBusyId("");
    }
  };

  return (
    <section className="expense-tracker screen-grid request-queue-screen">
      <div className="screen-hero">
        <div>
          <h2>Request Queue</h2>
          <p>Every async/approval request, with automatic background retries and full processing history.</p>
        </div>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      {data ? (
        <>
          <div className="request-queue-stats">
            <div className="request-queue-stat-card">
              <div className="stat-value">{stats.active_count ?? 0}</div>
              <div className="stat-label">Active (in flight)</div>
            </div>
            <div className="request-queue-stat-card">
              <div className="stat-value">{stats.by_status?.retrying ?? 0}</div>
              <div className="stat-label">Retrying now</div>
            </div>
            <div className="request-queue-stat-card">
              <div className="stat-value">{stats.by_status?.failed ?? 0}</div>
              <div className="stat-label">Failed</div>
            </div>
            <div className="request-queue-stat-card">
              <div className="stat-value">{stats.avg_retry_count ?? 0}</div>
              <div className="stat-label">Avg retry count (retrying)</div>
            </div>
            <div className="request-queue-stat-card">
              <div className="stat-value">
                {stats.oldest_active_age_seconds ? `${Math.round(stats.oldest_active_age_seconds / 60)}m` : "-"}
              </div>
              <div className="stat-label">Oldest active request</div>
            </div>
          </div>

          {actionFeedback ? <p className="form-feedback success">{actionFeedback}</p> : null}
          {actionError ? <p className="form-feedback error">{actionError}</p> : null}

          <div className="table-actions-inline" style={{ flexWrap: "wrap", gap: "8px", marginBottom: "12px" }}>
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                className={`table-action${activeFilter === tab.value ? " active" : ""}`}
                onClick={() => setActiveFilter(tab.value)}
              >
                {tab.label}
                {tab.value !== "all" ? ` (${stats.by_status?.[tab.value] ?? 0})` : ""}
              </button>
            ))}
          </div>

          <input
            type="text"
            className="expense-search-input"
            placeholder="Search by requester, type, or request ID..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            style={{ maxWidth: "420px" }}
          />

          <table className="data-table expense-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Requester</th>
                <th>Retries</th>
                <th>Last Attempt</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7}>No requests match this filter.</td>
                </tr>
              ) : (
                filtered.map((item) => (
                  <Fragment key={item.id}>
                    <tr>
                      <td>
                        {item.request_type}
                        {item.is_duplicate ? <span className="finance-status status-cancelled" style={{ marginLeft: 6 }}>duplicate</span> : null}
                      </td>
                      <td>
                        <span className={`finance-status status-${item.status}`}>{item.status}</span>
                      </td>
                      <td>
                        {item.requester}
                        <br />
                        <small>{item.requester_email}</small>
                      </td>
                      <td>{item.retry_count}/{item.max_retries}</td>
                      <td>{formatDate(item.last_attempt_at)}</td>
                      <td>{formatDate(item.created_at)}</td>
                      <td>
                        <div className="table-actions-inline">
                          <button
                            type="button"
                            className="table-action"
                            onClick={() => setExpandedId(expandedId === item.id ? "" : item.id)}
                          >
                            {expandedId === item.id ? "Hide history" : "History"}
                          </button>
                          {item.status === "failed" ? (
                            <button
                              type="button"
                              className="table-action"
                              disabled={actionBusyId === item.id}
                              onClick={() => runAction(onManualRetry, item.id, "Request re-queued for processing.")}
                            >
                              {actionBusyId === item.id ? "Retrying..." : "Retry"}
                            </button>
                          ) : null}
                          {NON_TERMINAL_STATUSES.has(item.status) ? (
                            <button
                              type="button"
                              className="table-action danger"
                              disabled={actionBusyId === item.id}
                              onClick={() => runAction(onCancelRequest, item.id, "Request cancelled.")}
                            >
                              {actionBusyId === item.id ? "Cancelling..." : "Cancel"}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    {expandedId === item.id ? (
                      <tr>
                        <td colSpan={7}>
                          <div className="request-queue-history">
                            {item.error_message ? (
                              <p style={{ color: "#991b1b", marginTop: 0 }}>Last error: {item.error_message}</p>
                            ) : null}
                            {(item.history || []).length === 0 ? (
                              <p>No processing history yet.</p>
                            ) : (
                              item.history.map((event) => (
                                <div className="request-queue-history-row" key={event.id}>
                                  <span className="event-type">{event.event_type.replace(/_/g, " ")}</span>
                                  <span>{event.description}</span>
                                  <span className="event-meta">{event.actor} &middot; {formatDate(event.created_at)}</span>
                                </div>
                              ))
                            )}
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
