import { useEffect, useMemo, useState } from "react";
import { openPrintableDocument, requestJson, Popup } from "../../AppShared";
import { API_BASE_URL } from "../../appConstants";
import { CONDITION_COLORS, InventoryPill, formatMoney } from "./inventoryHelpers";

const CONDITION_OPTIONS = ["new", "good", "fair", "damaged", "under_repair", "lost", "disposed"];

const emptyForm = {
  name: "", description: "", category: "Furniture", brand: "", model_number: "", serial_number: "",
  supplier: "", purchase_date: "", purchase_price: "", current_value: "", quantity: "1",
  reorder_level: "1", unit_of_measurement: "unit", warranty_period_months: "", expected_lifespan_years: "",
  storage_location: "", assigned_department: "", condition: "new", next_maintenance_date: "",
  record_finance_expense: false,
};

function formStateFromItem(item) {
  return {
    name: item.name || "", description: item.description || "", category: item.category || "Other",
    brand: item.brand || "", model_number: item.model_number || "", serial_number: item.serial_number || "",
    supplier: item.supplier || "", purchase_date: item.purchase_date || "", purchase_price: item.purchase_price ?? "",
    current_value: item.current_value ?? "", quantity: String(item.quantity ?? 1), reorder_level: String(item.reorder_level ?? 1),
    unit_of_measurement: item.unit_of_measurement || "unit", warranty_period_months: item.warranty_period_months ?? "",
    expected_lifespan_years: item.expected_lifespan_years ?? "", storage_location: item.storage_location || "",
    assigned_department: item.assigned_department || "", condition: item.condition || "new",
    next_maintenance_date: item.next_maintenance_date || "", record_finance_expense: false,
  };
}

// Shared field set for both the "Add Inventory Item" form and the Edit modal, so the
// two never drift apart. showQuantity mirrors the backend's PATCH whitelist, which
// deliberately excludes quantity - stock changes have to go through the dedicated
// stock-movement endpoint instead.
function InventoryItemFields({ form, setForm, categories, showQuantity, imageFiles, setImageFiles }) {
  return (
    <>
      <div className="panel-form-grid">
        <label className="panel-field">
          Item Name
          <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
        </label>
        <label className="panel-field">
          Category
          <input list="inventory-categories" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} />
          <datalist id="inventory-categories">
            {(categories.length ? categories : ["Furniture", "ICT Equipment", "Laboratory", "Library", "Sports", "Office Supplies", "Classroom Materials", "Vehicles"]).map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>
        <label className="panel-field">
          Brand
          <input value={form.brand} onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))} />
        </label>
        <label className="panel-field">
          Model Number
          <input value={form.model_number} onChange={(e) => setForm((f) => ({ ...f, model_number: e.target.value }))} />
        </label>
        <label className="panel-field">
          Serial Number
          <input value={form.serial_number} onChange={(e) => setForm((f) => ({ ...f, serial_number: e.target.value }))} />
        </label>
        <label className="panel-field">
          Supplier
          <input value={form.supplier} onChange={(e) => setForm((f) => ({ ...f, supplier: e.target.value }))} />
        </label>
        <label className="panel-field">
          Purchase Date
          <input type="date" value={form.purchase_date} onChange={(e) => setForm((f) => ({ ...f, purchase_date: e.target.value }))} />
        </label>
        <label className="panel-field">
          Purchase Price
          <input type="number" step="0.01" value={form.purchase_price} onChange={(e) => setForm((f) => ({ ...f, purchase_price: e.target.value }))} />
        </label>
        <label className="panel-field">
          Current Value
          <input type="number" step="0.01" value={form.current_value} onChange={(e) => setForm((f) => ({ ...f, current_value: e.target.value }))} />
        </label>
        {showQuantity ? (
          <label className="panel-field">
            Quantity
            <input type="number" min="1" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} />
          </label>
        ) : null}
        <label className="panel-field">
          Reorder Level
          <input type="number" min="0" value={form.reorder_level} onChange={(e) => setForm((f) => ({ ...f, reorder_level: e.target.value }))} />
        </label>
        <label className="panel-field">
          Unit of Measurement
          <input value={form.unit_of_measurement} onChange={(e) => setForm((f) => ({ ...f, unit_of_measurement: e.target.value }))} />
        </label>
        <label className="panel-field">
          Warranty Period (months)
          <input type="number" min="0" value={form.warranty_period_months} onChange={(e) => setForm((f) => ({ ...f, warranty_period_months: e.target.value }))} />
        </label>
        <label className="panel-field">
          Expected Lifespan (years)
          <input type="number" min="0" value={form.expected_lifespan_years} onChange={(e) => setForm((f) => ({ ...f, expected_lifespan_years: e.target.value }))} />
        </label>
        <label className="panel-field">
          Storage Location
          <input value={form.storage_location} onChange={(e) => setForm((f) => ({ ...f, storage_location: e.target.value }))} />
        </label>
        <label className="panel-field">
          Assigned Department
          <input value={form.assigned_department} onChange={(e) => setForm((f) => ({ ...f, assigned_department: e.target.value }))} />
        </label>
        <label className="panel-field">
          Condition
          <select value={form.condition} onChange={(e) => setForm((f) => ({ ...f, condition: e.target.value }))}>
            {CONDITION_OPTIONS.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
            ))}
          </select>
        </label>
        <label className="panel-field">
          Next Maintenance Date
          <input type="date" value={form.next_maintenance_date} onChange={(e) => setForm((f) => ({ ...f, next_maintenance_date: e.target.value }))} />
        </label>
        <label className="panel-field">
          Images
          <input type="file" accept="image/*" multiple onChange={(e) => setImageFiles(Array.from(e.target.files || []))} />
        </label>
        <label className="panel-field checkbox-field">
          <input
            type="checkbox"
            checked={form.record_finance_expense}
            onChange={(e) => setForm((f) => ({ ...f, record_finance_expense: e.target.checked }))}
          />
          Record purchase as a Finance expense
        </label>
      </div>
      <div className="panel-form full-width">
        Description
        <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={2} />
      </div>
    </>
  );
}

export default function InventoryItemsPanel({ session }) {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [conditionFilter, setConditionFilter] = useState("");

  // "Add Inventory Item" form - create-only.
  const [form, setForm] = useState(emptyForm);
  const [imageFiles, setImageFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");

  // Edit modal - separate state so editing an item never touches the Add form.
  const [editingId, setEditingId] = useState("");
  const [editForm, setEditForm] = useState(emptyForm);
  const [editImageFiles, setEditImageFiles] = useState([]);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const [busyId, setBusyId] = useState("");

  const load = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const result = await requestJson(session, "GET", "/api/inventory/items/");
      setItems(result.items || []);
      setCategories(result.categories || []);
    } catch (err) {
      setLoadError(err.message || "Unable to load inventory items.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return items.filter((item) => {
      if (categoryFilter && item.category !== categoryFilter) return false;
      if (conditionFilter && item.condition !== conditionFilter) return false;
      if (!term) return true;
      return (
        item.name.toLowerCase().includes(term) ||
        item.inventory_id.toLowerCase().includes(term) ||
        (item.serial_number || "").toLowerCase().includes(term) ||
        (item.storage_location || "").toLowerCase().includes(term) ||
        (item.assigned_department || "").toLowerCase().includes(term) ||
        (item.supplier || "").toLowerCase().includes(term)
      );
    });
  }, [items, searchTerm, categoryFilter, conditionFilter]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setFeedback("");
    setFormError("");
    try {
      const payload = { ...form, images: imageFiles };
      await requestJson(session, "POST", "/api/inventory/items/", payload);
      setFeedback("Item created.");
      setForm(emptyForm);
      setImageFiles([]);
      await load();
    } catch (err) {
      setFormError(err.message || "Unable to save item.");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (item) => {
    setEditForm(formStateFromItem(item));
    setEditImageFiles([]);
    setEditError("");
    setEditingId(item.id);
  };

  const closeEditModal = () => {
    setEditingId("");
  };

  const handleEditSubmit = async (event) => {
    event.preventDefault();
    setEditSaving(true);
    setEditError("");
    try {
      const payload = { ...editForm, images: editImageFiles };
      await requestJson(session, "PATCH", `/api/inventory/items/${editingId}/`, payload);
      await load();
      closeEditModal();
    } catch (err) {
      setEditError(err.message || "Unable to save item.");
    } finally {
      setEditSaving(false);
    }
  };

  const handleArchive = async (item) => {
    setBusyId(item.id);
    try {
      await requestJson(session, "DELETE", `/api/inventory/items/${item.id}/`);
      await load();
    } catch (err) {
      setLoadError(err.message || "Unable to archive item.");
    } finally {
      setBusyId("");
    }
  };

  const handleDelete = async (item) => {
    if (!window.confirm(`Permanently delete "${item.name}"? This cannot be undone.`)) return;
    setBusyId(item.id);
    try {
      await requestJson(session, "DELETE", `/api/inventory/items/${item.id}/`, { hard: true });
      await load();
    } catch (err) {
      setLoadError(err.message || "Unable to delete item.");
    } finally {
      setBusyId("");
    }
  };

  const handlePrintQr = async (item) => {
    const url = `${API_BASE_URL}/api/inventory/items/${item.id}/qr/`;
    try {
      const response = await fetch(url, { headers: { Authorization: `Bearer ${session?.access}` } });
      const blob = await response.blob();
      const dataUrl = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
      });
      const container = document.getElementById("inventory-qr-label");
      container.innerHTML = `
        <div class="inventory-qr-print">
          <img src="${dataUrl}" alt="QR code" />
          <h3>${item.name}</h3>
          <p>${item.inventory_id}</p>
        </div>`;
      openPrintableDocument("inventory-qr-label", `${item.inventory_id} - Label`);
    } catch (err) {
      setLoadError(err.message || "Unable to generate QR label.");
    }
  };

  return (
    <div className="inventory-items-stack">
      <div id="inventory-qr-label" className="inventory-qr-label" />

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Add Inventory Item</h3>
        </div>
        {formError ? <p className="form-feedback error">{formError}</p> : null}
        {feedback ? <p className="form-feedback success">{feedback}</p> : null}
        <form className="panel-form" onSubmit={handleSubmit}>
          <InventoryItemFields form={form} setForm={setForm} categories={categories} showQuantity imageFiles={imageFiles} setImageFiles={setImageFiles} />
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Saving..." : "Add Item"}
          </button>
        </form>
      </article>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Inventory Items ({filtered.length})</h3>
        </div>
        {loadError ? <p className="form-feedback error">{loadError}</p> : null}

        <input
          type="text"
          className="inventory-search-input"
          placeholder="Search by name, Inventory ID, serial number, location... (or scan a barcode here)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <div className="table-actions-inline" style={{ marginBottom: 12 }}>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={conditionFilter} onChange={(e) => setConditionFilter(e.target.value)}>
            <option value="">All conditions</option>
            {CONDITION_OPTIONS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
          </select>
        </div>

        {loading ? (
          <p>Loading items...</p>
        ) : filtered.length === 0 ? (
          <p>No inventory items match this filter.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Inventory ID</th><th>Name</th><th>Category</th><th>Condition</th>
                  <th>Available / Total</th><th>Value</th><th>Location</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td>{item.inventory_id}</td>
                    <td>
                      {item.name}
                      {item.images?.length ? (
                        <div className="inventory-item-images">
                          {item.images.slice(0, 3).map((img) => <img key={img.id} src={img.image} alt={item.name} />)}
                        </div>
                      ) : null}
                    </td>
                    <td>{item.category}</td>
                    <td><InventoryPill value={item.condition} colorMap={CONDITION_COLORS} /></td>
                    <td>{item.quantity_available} / {item.quantity} {item.unit_of_measurement}</td>
                    <td>{formatMoney(item.stock_value)}</td>
                    <td>{item.storage_location || "-"}</td>
                    <td>
                      <div className="table-actions-inline">
                        <button type="button" className="table-action" onClick={() => startEdit(item)}>Edit</button>
                        <button type="button" className="table-action" onClick={() => handlePrintQr(item)}>QR Label</button>
                        <button type="button" className="table-action" disabled={busyId === item.id} onClick={() => handleArchive(item)}>
                          {busyId === item.id ? "..." : "Archive"}
                        </button>
                        <button type="button" className="table-action danger" disabled={busyId === item.id} onClick={() => handleDelete(item)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>

      <Popup open={Boolean(editingId)} onClose={closeEditModal} labelledBy="inventory-edit-title">
        <div className="edit-modal-head">
          <div>
            <h3 id="inventory-edit-title">Edit Item</h3>
            <p>Update this inventory item's details.</p>
          </div>
          <button type="button" className="edit-modal-close" onClick={closeEditModal} disabled={editSaving} aria-label="Close">×</button>
        </div>
        {editError ? <p className="form-feedback error">{editError}</p> : null}
        <form className="panel-form" onSubmit={handleEditSubmit}>
          <InventoryItemFields
            form={editForm}
            setForm={setEditForm}
            categories={categories}
            showQuantity={false}
            imageFiles={editImageFiles}
            setImageFiles={setEditImageFiles}
          />
          <div className="panel-form-actions">
            <button type="submit" className="btn-primary" disabled={editSaving}>
              {editSaving ? "Saving..." : "Save Changes"}
            </button>
            <button type="button" className="table-action" onClick={closeEditModal} disabled={editSaving}>
              Cancel
            </button>
          </div>
        </form>
      </Popup>
    </div>
  );
}
