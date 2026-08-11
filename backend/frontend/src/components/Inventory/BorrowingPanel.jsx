import { useEffect, useMemo, useState } from "react";
import { formatDate, requestJson, Spinner } from "../../AppShared";
import { ASSIGNMENT_STATUS_COLORS, InventoryPill } from "./inventoryHelpers";

const CONDITION_OPTIONS = ["new", "good", "fair", "damaged", "under_repair"];

export default function BorrowingPanel({ session }) {
  const [items, setItems] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [form, setForm] = useState({
    item: "", quantity_assigned: "1", borrower_label: "", expected_return_date: "", condition_before: "good",
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [returnBusyId, setReturnBusyId] = useState("");
  const [returnCondition, setReturnCondition] = useState({});

  const load = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [itemsResult, assignmentsResult] = await Promise.all([
        requestJson(session, "GET", "/api/inventory/items/"),
        requestJson(session, "GET", "/api/inventory/assignments/"),
      ]);
      setItems(itemsResult.items || []);
      setAssignments(assignmentsResult.assignments || []);
    } catch (err) {
      setLoadError(err.message || "Unable to load borrowing data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredAssignments = useMemo(
    () => (statusFilter ? assignments.filter((a) => a.status === statusFilter) : assignments),
    [assignments, statusFilter]
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.item || !form.borrower_label.trim()) {
      setFormError("Select an item and enter who/where it's being issued to.");
      return;
    }
    setSaving(true);
    setFeedback("");
    setFormError("");
    try {
      await requestJson(session, "POST", "/api/inventory/assignments/", form);
      setFeedback("Item issued.");
      setForm({ item: "", quantity_assigned: "1", borrower_label: "", expected_return_date: "", condition_before: "good" });
      await load();
    } catch (err) {
      setFormError(err.message || "Unable to issue item.");
    } finally {
      setSaving(false);
    }
  };

  const handleReturn = async (assignment) => {
    setReturnBusyId(assignment.id);
    try {
      await requestJson(session, "POST", `/api/inventory/assignments/${assignment.id}/return/`, {
        condition_after: returnCondition[assignment.id] || assignment.condition_before,
      });
      await load();
    } catch (err) {
      setLoadError(err.message || "Unable to record return.");
    } finally {
      setReturnBusyId("");
    }
  };

  return (
    <div className="expense-workspace">
      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Issue Item</h3>
        </div>
        {formError ? <p className="form-feedback error">{formError}</p> : null}
        {feedback ? <p className="form-feedback success">{feedback}</p> : null}
        <form className="panel-form" onSubmit={handleSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Item
              <select value={form.item} onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))} required>
                <option value="">Select item</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>{item.inventory_id} - {item.name} ({item.quantity_available} available)</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Quantity
              <input type="number" min="1" value={form.quantity_assigned} onChange={(e) => setForm((f) => ({ ...f, quantity_assigned: e.target.value }))} />
            </label>
            <label className="panel-field">
              Borrower / Department / Classroom
              <input
                value={form.borrower_label}
                onChange={(e) => setForm((f) => ({ ...f, borrower_label: e.target.value }))}
                placeholder="e.g. Mrs. Adeyemi (Physics Teacher) or Classroom 3B"
                required
              />
            </label>
            <label className="panel-field">
              Expected Return Date
              <input type="date" value={form.expected_return_date} onChange={(e) => setForm((f) => ({ ...f, expected_return_date: e.target.value }))} />
            </label>
            <label className="panel-field">
              Condition Before Issue
              <select value={form.condition_before} onChange={(e) => setForm((f) => ({ ...f, condition_before: e.target.value }))}>
                {CONDITION_OPTIONS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
            </label>
          </div>
          <button type="submit" className="btn-primary" disabled={saving}>{saving ? <><Spinner size={14} /> Issuing...</> : "Issue Item"}</button>
        </form>
      </article>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Borrowed Items ({filteredAssignments.length})</h3>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="borrowed">Borrowed</option>
            <option value="overdue">Overdue</option>
            <option value="returned">Returned</option>
            <option value="lost">Lost</option>
          </select>
        </div>
        {loadError ? <p className="form-feedback error">{loadError}</p> : null}
        {loading ? (
          <p>Loading borrowing records...</p>
        ) : filteredAssignments.length === 0 ? (
          <p>No borrowing records match this filter.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Item</th><th>Borrower</th><th>Qty</th><th>Issued</th><th>Expected Return</th>
                <th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssignments.map((a) => (
                <tr key={a.id}>
                  <td>{a.item_inventory_id} - {a.item_name}</td>
                  <td>{a.borrower_name}</td>
                  <td>{a.quantity_assigned}</td>
                  <td>{formatDate(a.date_issued)}</td>
                  <td>{a.expected_return_date ? formatDate(a.expected_return_date) : "-"}</td>
                  <td><InventoryPill value={a.status} colorMap={ASSIGNMENT_STATUS_COLORS} /></td>
                  <td>
                    {a.status === "borrowed" || a.status === "overdue" ? (
                      <div className="table-actions-inline">
                        <select
                          value={returnCondition[a.id] || a.condition_before}
                          onChange={(e) => setReturnCondition((c) => ({ ...c, [a.id]: e.target.value }))}
                        >
                          {CONDITION_OPTIONS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                        </select>
                        <button type="button" className="table-action" disabled={returnBusyId === a.id} onClick={() => handleReturn(a)}>
                          {returnBusyId === a.id ? <><Spinner size={12} /> Returning...</> : "Return"}
                        </button>
                      </div>
                    ) : (
                      <span>{a.actual_return_date ? `Returned ${formatDate(a.actual_return_date)}` : "-"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </article>
    </div>
  );
}
