import { useEffect, useState } from "react";
import { formatDate, requestJson } from "../../AppShared";
import { MOVEMENT_TYPE_LABELS } from "./inventoryHelpers";

const ACTIONS = [
  { value: "add", label: "Add Stock" },
  { value: "remove", label: "Remove Stock" },
  { value: "transfer", label: "Transfer" },
  { value: "dispose", label: "Dispose" },
];

export default function StockMovementsPanel({ session }) {
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [form, setForm] = useState({ item: "", action: "add", quantity: "1", to_location: "", reason: "" });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");

  const load = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [itemsResult, movementsResult] = await Promise.all([
        requestJson(session, "GET", "/api/inventory/items/"),
        requestJson(session, "GET", "/api/inventory/movements/"),
      ]);
      setItems(itemsResult.items || []);
      setMovements(movementsResult.movements || []);
    } catch (err) {
      setLoadError(err.message || "Unable to load stock data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.item) {
      setFormError("Select an item first.");
      return;
    }
    setSaving(true);
    setFeedback("");
    setFormError("");
    try {
      await requestJson(session, "POST", `/api/inventory/items/${form.item}/stock/`, {
        action: form.action,
        quantity: form.quantity,
        to_location: form.to_location,
        reason: form.reason,
      });
      setFeedback("Stock updated.");
      setForm((f) => ({ ...f, quantity: "1", to_location: "", reason: "" }));
      await load();
    } catch (err) {
      setFormError(err.message || "Unable to update stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="expense-workspace">
      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Update Stock</h3>
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
                  <option key={item.id} value={item.id}>{item.inventory_id} - {item.name} ({item.quantity} in stock)</option>
                ))}
              </select>
            </label>
            <label className="panel-field">
              Action
              <select value={form.action} onChange={(e) => setForm((f) => ({ ...f, action: e.target.value }))}>
                {ACTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </label>
            <label className="panel-field">
              Quantity
              <input type="number" min="1" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} />
            </label>
            {form.action === "transfer" ? (
              <label className="panel-field">
                New Location / Department
                <input value={form.to_location} onChange={(e) => setForm((f) => ({ ...f, to_location: e.target.value }))} />
              </label>
            ) : null}
            <label className="panel-field">
              Reason / Note
              <input value={form.reason} onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} />
            </label>
          </div>
          <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Saving..." : "Apply"}</button>
        </form>
      </article>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Stock Movement History</h3>
        </div>
        {loadError ? <p className="form-feedback error">{loadError}</p> : null}
        {loading ? (
          <p>Loading movement history...</p>
        ) : movements.length === 0 ? (
          <p>No stock movements recorded yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Item</th><th>Type</th><th>Change</th><th>Resulting Qty</th><th>Location</th><th>By</th><th>Date</th></tr>
            </thead>
            <tbody>
              {movements.map((m) => (
                <tr key={m.id}>
                  <td>{m.item_inventory_id} - {m.item_name}</td>
                  <td>{MOVEMENT_TYPE_LABELS[m.movement_type] || m.movement_type}</td>
                  <td>{m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}</td>
                  <td>{m.resulting_quantity}</td>
                  <td>{m.to_location || m.from_location || "-"}</td>
                  <td>{m.performed_by_name || "-"}</td>
                  <td>{formatDate(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </article>
    </div>
  );
}
