import { useEffect, useState } from "react";
import { formatDate, requestJson } from "../../AppShared";

export default function AuditLogPanel({ session }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError("");
      try {
        const result = await requestJson(session, "GET", "/api/inventory/audit-log/");
        if (!cancelled) setEntries(result.audit_log || []);
      } catch (err) {
        if (!cancelled) setLoadError(err.message || "Unable to load the audit log.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [session]);

  return (
    <article className="app-panel">
      <div className="expense-panel-head">
        <h3>Inventory Audit Log</h3>
      </div>
      {loadError ? <p className="form-feedback error">{loadError}</p> : null}
      {loading ? (
        <p>Loading audit log...</p>
      ) : entries.length === 0 ? (
        <p>No inventory activity recorded yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Action</th><th>Item</th><th>Details</th><th>Actor</th><th>Date</th></tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.action.replace(/_/g, " ")}</td>
                <td>{entry.item_inventory_id || "-"}</td>
                <td>{entry.description}</td>
                <td>{entry.actor_name}</td>
                <td>{formatDate(entry.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </article>
  );
}
