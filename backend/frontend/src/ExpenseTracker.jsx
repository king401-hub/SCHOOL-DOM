import { useMemo, useState } from "react";
import { DashboardIcon, ScreenState, formatDate } from "./AppShared";

const NAIRA_SYMBOL = "\u20A6";

const EXPENSE_TAGS = [
  { label: "Operations", color: "#14b8a6" },
  { label: "Utilities", color: "#f59e0b" },
  { label: "Supplies", color: "#6366f1" },
  { label: "Payroll", color: "#ec4899" },
  { label: "Maintenance", color: "#22c55e" },
  { label: "Transport", color: "#ef4444" },
];

export default function ExpenseTracker({ data, loading, error, onRetry, onCreate, onDelete, onClassFeeSave, onClassFeeDelete }) {
  const items = data?.records || [];
  const classFees = data?.class_fee_rows || [];
  const classOptions = data?.class_options || [];
  const salaryPaymentSummary = data?.salary_payment_summary || {};
  const [form, setForm] = useState({
    title: "",
    vendor: "",
    amount: "",
    type: "expense",
    category: EXPENSE_TAGS[0].label,
    color: EXPENSE_TAGS[0].color,
    status: "pending",
    date: new Date().toISOString().slice(0, 10),
    note: "",
    receiptNumber: "",
  });
  const [activeFilter, setActiveFilter] = useState("all");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");
  const [classFeeForm, setClassFeeForm] = useState({
    school_class: "",
    title: "",
    amount: "",
    due_date: "",
  });
  const [editingClassFeeId, setEditingClassFeeId] = useState("");
  const [classFeeFeedback, setClassFeeFeedback] = useState("");
  const [classFeeError, setClassFeeError] = useState("");
  const [savingClassFee, setSavingClassFee] = useState(false);
  const [deletingClassFeeId, setDeletingClassFeeId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState("");

  const formatExpenseAmount = (value) =>
    `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  const totals = useMemo(() => {
    const expenses = items.filter((item) => item.type === "expense");
    const bills = items.filter((item) => item.type === "bill");
    const receipts = items.filter((item) => item.type === "receipt");
    const paid = items.filter((item) => item.status === "paid");
    const due = items.filter((item) => item.status !== "paid");
    return {
      expenses: expenses.reduce((sum, item) => sum + Number(item.amount || 0), 0),
      bills: bills.reduce((sum, item) => sum + Number(item.amount || 0), 0),
      receipts: receipts.reduce((sum, item) => sum + Number(item.amount || 0), 0),
      paid: paid.reduce((sum, item) => sum + Number(item.amount || 0), 0),
      due: due.reduce((sum, item) => sum + Number(item.amount || 0), 0),
    };
  }, [items]);

  const schoolFeeStats = useMemo(() => {
    const expected = classFees.reduce((sum, fee) => sum + Number(fee.expected_amount ?? fee.amount ?? 0), 0);
    const received = classFees.reduce((sum, fee) => sum + Number(fee.amount_received || 0), 0);
    const outstanding = classFees.reduce((sum, fee) => sum + Number(fee.outstanding_amount || 0), 0);
    const students = classFees.reduce((sum, fee) => sum + Number(fee.student_count || 0), 0);
    return { expected, received, outstanding, students };
  }, [classFees]);
  const latestClassFees = classFees.slice(0, 4);

  const categoryRows = useMemo(() => {
    const rows = new Map();
    items.forEach((item) => {
      const current = rows.get(item.category) || { label: item.category, color: item.color, total: 0 };
      current.total += Number(item.amount || 0);
      current.color = item.color || current.color;
      rows.set(item.category, current);
    });
    return Array.from(rows.values()).sort((a, b) => b.total - a.total);
  }, [items]);

  const maxCategoryTotal = Math.max(...categoryRows.map((item) => item.total), 1);
  const filteredItems = activeFilter === "all" ? items : items.filter((item) => item.type === activeFilter);

  const resetClassFeeForm = () => {
    setEditingClassFeeId("");
    setClassFeeForm({ school_class: "", title: "", amount: "", due_date: "" });
  };

  const handleClassFeeSubmit = async (event) => {
    event.preventDefault();
    setClassFeeFeedback("");
    setClassFeeError("");
    const amount = Number(classFeeForm.amount);
    if (!classFeeForm.school_class || !classFeeForm.title.trim() || !amount || amount <= 0 || !classFeeForm.due_date) {
      setClassFeeError("Select a class, title, amount, and due date.");
      return;
    }
    setSavingClassFee(true);
    try {
      await onClassFeeSave?.({
        id: editingClassFeeId,
        ...classFeeForm,
        title: classFeeForm.title.trim(),
        amount,
      });
      setClassFeeFeedback(editingClassFeeId ? "School-fee bill updated." : "School-fee bill created.");
      resetClassFeeForm();
    } catch (err) {
      setClassFeeError(err.message || "Could not save school-fee bill.");
    } finally {
      setSavingClassFee(false);
    }
  };

  const startEditClassFee = (fee) => {
    setClassFeeFeedback("");
    setClassFeeError("");
    setEditingClassFeeId(fee.id);
    setClassFeeForm({
      school_class: fee.school_class || "",
      title: fee.title || "",
      amount: fee.amount || "",
      due_date: fee.due_date || "",
    });
  };

  const handleDeleteClassFee = async (feeId) => {
    setClassFeeFeedback("");
    setClassFeeError("");
    setDeletingClassFeeId(feeId);
    try {
      await onClassFeeDelete?.(feeId);
      setClassFeeFeedback("School-fee bill deactivated.");
      if (editingClassFeeId === feeId) {
        resetClassFeeForm();
      }
    } catch (err) {
      setClassFeeError(err.message || "Could not deactivate school-fee bill.");
    } finally {
      setDeletingClassFeeId("");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFeedback("");
    setFormError("");
    const amount = Number(form.amount);
    if (!form.title.trim() || !amount || amount <= 0) {
      setFormError("Add an expense name and a valid amount.");
      return;
    }
    setIsSaving(true);
    try {
      await onCreate({
        ...form,
        title: form.title.trim(),
        vendor: form.vendor.trim() || "Unassigned",
        amount,
        note: form.note.trim(),
        receiptNumber: form.receiptNumber.trim(),
      });
      setForm((current) => ({
        ...current,
        title: "",
        vendor: "",
        amount: "",
        note: "",
        receiptNumber: "",
        date: new Date().toISOString().slice(0, 10),
      }));
      setFeedback(`${form.type === "bill" ? "Bill" : form.type === "receipt" ? "Receipt" : "Expense"} saved.`);
    } catch (err) {
      setFormError(err.message || "Could not save record.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTagChange = (label) => {
    const tag = EXPENSE_TAGS.find((item) => item.label === label) || EXPENSE_TAGS[0];
    setForm((current) => ({ ...current, category: tag.label, color: tag.color }));
  };

  const handleDelete = async (itemId) => {
    setFeedback("");
    setFormError("");
    setDeletingId(itemId);
    try {
      await onDelete(itemId);
      setFeedback("Record deleted.");
    } catch (err) {
      setFormError(err.message || "Could not delete record.");
    } finally {
      setDeletingId("");
    }
  };

  return (
    <section className="expense-tracker screen-grid">
      <div className="expense-hero">
        <div>
          <p>Expense control</p>
          <h2>Bills and Expenses</h2>
          <span>Track school spending, bills, receipts, color-coded tags, and category totals at a glance.</span>
        </div>
        <div className="expense-total-card">
          <small>Total Outflow</small>
          <strong>{formatExpenseAmount(totals.expenses + totals.bills + totals.receipts)}</strong>
        </div>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <div className="expense-summary-grid">
        <article className="finance-summary-card tone-expected">
          <div className="finance-summary-icon" aria-hidden="true">
            <DashboardIcon name="currency-naira" className="inline-icon" />
          </div>
          <div>
            <p>Expenses</p>
            <strong>{formatExpenseAmount(totals.expenses)}</strong>
          </div>
        </article>
        <article className="finance-summary-card tone-pending">
          <div className="finance-summary-icon" aria-hidden="true">
            <DashboardIcon name="pending" className="inline-icon" />
          </div>
          <div>
            <p>Bills</p>
            <strong>{formatExpenseAmount(totals.bills)}</strong>
          </div>
        </article>
        <article className="finance-summary-card tone-received">
          <div className="finance-summary-icon" aria-hidden="true">
            <DashboardIcon name="check" className="inline-icon" />
          </div>
          <div>
            <p>Receipts</p>
            <strong>{formatExpenseAmount(totals.receipts)}</strong>
          </div>
        </article>
        <article className="finance-summary-card tone-outstanding">
          <div className="finance-summary-icon" aria-hidden="true">
            <DashboardIcon name="pending" className="inline-icon" />
          </div>
          <div>
            <p>Open Balance</p>
            <strong>{formatExpenseAmount(totals.due)}</strong>
          </div>
        </article>
      </div>

      <article className="app-panel expense-chart-panel">
        <div className="expense-panel-head">
          <h3>Spending Graph</h3>
          <span>{categoryRows.length} tags</span>
        </div>
        <div className="expense-chart-layout">
          <div>
            <div className="expense-donut" style={{ "--paid": `${Math.round(((totals.paid || 0) / Math.max(totals.expenses + totals.bills + totals.receipts, 1)) * 100)}%` }}>
              <strong>{Math.round(((totals.paid || 0) / Math.max(totals.expenses + totals.bills + totals.receipts, 1)) * 100)}%</strong>
              <span>paid</span>
            </div>
            <div className="expense-bar-chart" aria-label="Expenses by color tag">
              {categoryRows.map((row) => (
                <div key={row.label} className="expense-chart-row">
                  <span>{row.label}</span>
                  <div>
                    <i style={{ width: `${Math.max(8, Math.round((row.total / maxCategoryTotal) * 100))}%`, background: row.color }} />
                  </div>
                  <strong>{formatExpenseAmount(row.total)}</strong>
                </div>
              ))}
            </div>
          </div>
          <div className="expense-stat-board">
            <div>
              <span>School-fee bills</span>
              <strong>{classFees.length}</strong>
            </div>
            <div>
              <span>Students billed</span>
              <strong>{schoolFeeStats.students}</strong>
            </div>
            <div>
              <span>Expected fees</span>
              <strong>{formatExpenseAmount(schoolFeeStats.expected)}</strong>
            </div>
            <div>
              <span>Received fees</span>
              <strong>{formatExpenseAmount(schoolFeeStats.received)}</strong>
            </div>
            <div>
              <span>Open fees</span>
              <strong>{formatExpenseAmount(schoolFeeStats.outstanding)}</strong>
            </div>
            <div>
              <span>Unsettled payments</span>
              <strong>{formatExpenseAmount(salaryPaymentSummary.unsettled_amount)}</strong>
            </div>
          </div>
        </div>
      </article>

      <div className="expense-workspace">
        <article className="app-panel expense-create-panel">
          <h3>{editingClassFeeId ? "Edit School Fee Bill" : "Create School Fee Bill"}</h3>
          <form className="panel-form" onSubmit={handleClassFeeSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">
                Class
                <select
                  value={classFeeForm.school_class}
                  onChange={(event) => setClassFeeForm((current) => ({ ...current, school_class: event.target.value }))}
                  required
                >
                  <option value="">Select class</option>
                  {classOptions.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="panel-field">
                Bill title
                <input
                  value={classFeeForm.title}
                  onChange={(event) => setClassFeeForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Term school fees"
                  required
                />
              </label>
              <label className="panel-field">
                Amount
                <input
                  type="number"
                  min="1"
                  step="0.01"
                  value={classFeeForm.amount}
                  onChange={(event) => setClassFeeForm((current) => ({ ...current, amount: event.target.value }))}
                  required
                />
              </label>
              <label className="panel-field">
                Due date
                <input
                  type="date"
                  value={classFeeForm.due_date}
                  onChange={(event) => setClassFeeForm((current) => ({ ...current, due_date: event.target.value }))}
                  required
                />
              </label>
            </div>
            {classFeeFeedback ? <p className="form-feedback success">{classFeeFeedback}</p> : null}
            {classFeeError ? <p className="form-feedback error">{classFeeError}</p> : null}
            <div className="panel-form-actions">
              <button type="submit" disabled={savingClassFee || !onClassFeeSave}>
                {savingClassFee ? "Saving..." : editingClassFeeId ? "Update bill" : "Create bill"}
              </button>
              {editingClassFeeId ? <button type="button" onClick={resetClassFeeForm}>Cancel</button> : null}
            </div>
          </form>
          <div className="expense-mini-board">
            <div className="expense-panel-head">
              <h3>Recent Bills</h3>
              <span>{classFees.length} active</span>
            </div>
            {latestClassFees.length ? (
              latestClassFees.map((fee) => (
                <button key={fee.id} type="button" className="expense-mini-row" onClick={() => startEditClassFee(fee)}>
                  <span>
                    {fee.title}
                    <small>{fee.class_label}</small>
                  </span>
                  <strong>{formatExpenseAmount(fee.amount)}</strong>
                </button>
              ))
            ) : (
              <p className="panel-empty">Created school-fee bills will appear here.</p>
            )}
          </div>
        </article>

        <article className="app-panel expense-create-panel">
          <h3>Create Expense, Bill, or Receipt</h3>
          <form className="panel-form" onSubmit={handleSubmit}>
            <div className="panel-form-grid">
              <label className="panel-field">
                Name
                <input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Example: Lab supplies" required />
              </label>
              <label className="panel-field">
                Amount
                <input type="number" min="1" step="0.01" value={form.amount} onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))} required />
              </label>
              <label className="panel-field">
                Vendor
                <input value={form.vendor} onChange={(event) => setForm((current) => ({ ...current, vendor: event.target.value }))} placeholder="Vendor or staff member" />
              </label>
              <label className="panel-field">
                Date
                <input type="date" value={form.date} onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))} />
              </label>
              <label className="panel-field">
                Type
                <select value={form.type} onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}>
                  <option value="expense">Expense</option>
                  <option value="bill">Bill</option>
                  <option value="receipt">Receipt</option>
                </select>
              </label>
              <label className="panel-field">
                Status
                <select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}>
                  <option value="pending">Pending</option>
                  <option value="due">Due</option>
                  <option value="paid">Paid</option>
                </select>
              </label>
              <label className="panel-field full">
                Color tag
                <select value={form.category} onChange={(event) => handleTagChange(event.target.value)}>
                  {EXPENSE_TAGS.map((tag) => (
                    <option key={tag.label} value={tag.label}>{tag.label}</option>
                  ))}
                </select>
              </label>
              <label className="panel-field">
                Receipt no.
                <input value={form.receiptNumber} onChange={(event) => setForm((current) => ({ ...current, receiptNumber: event.target.value }))} placeholder="Example: RC-2048" />
              </label>
              <div className="expense-color-tags">
                {EXPENSE_TAGS.map((tag) => (
                  <button
                    key={tag.label}
                    type="button"
                    className={form.category === tag.label ? "active" : ""}
                    onClick={() => handleTagChange(tag.label)}
                    style={{ "--tag-color": tag.color }}
                  >
                    <span aria-hidden="true" />
                    {tag.label}
                  </button>
                ))}
              </div>
              <label className="panel-field full">
                Note
                <textarea value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} rows="3" placeholder="Optional details" />
              </label>
            </div>
            {feedback ? <p className="form-feedback success">{feedback}</p> : null}
            {formError ? <p className="form-feedback error">{formError}</p> : null}
            <div className="panel-form-actions">
              <button type="submit" disabled={isSaving}>{isSaving ? "Saving..." : "Save Record"}</button>
            </div>
          </form>
        </article>

      </div>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>School Fee Bills &amp; Receipts</h3>
          <span>{classFees.length} active</span>
        </div>
        <div className="table-scroll">
          <table className="data-table expense-table">
            <thead>
              <tr>
                <th>Class</th>
                <th>Bill</th>
                <th>Students</th>
                <th>Expected</th>
                <th>Received</th>
                <th>Due</th>
                <th>Due date</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {classFees.map((fee) => (
                <tr key={fee.id}>
                  <td>{fee.class_label}</td>
                  <td>{fee.title}</td>
                  <td>{fee.student_count ?? 0}</td>
                  <td>{formatExpenseAmount(fee.expected_amount ?? fee.amount)}</td>
                  <td>{formatExpenseAmount(fee.amount_received)}</td>
                  <td>{formatExpenseAmount(fee.outstanding_amount)}</td>
                  <td>{formatDate(fee.due_date)}</td>
                  <td>
                    <div className="table-actions-inline">
                      <button type="button" className="table-action" onClick={() => startEditClassFee(fee)}>Edit</button>
                      <button
                        type="button"
                        className="table-action danger"
                        onClick={() => handleDeleteClassFee(fee.id)}
                        disabled={deletingClassFeeId === fee.id || !onClassFeeDelete}
                      >
                        {deletingClassFeeId === fee.id ? "Deleting..." : "Deactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!classFees.length ? (
                <tr><td colSpan="8">No school-fee bills have been created yet.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </article>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Expense Register</h3>
          <div className="expense-tabs">
            {["all", "expense", "bill", "receipt"].map((filter) => (
              <button key={filter} type="button" className={activeFilter === filter ? "active" : ""} onClick={() => setActiveFilter(filter)}>
                {filter === "all" ? "All" : filter === "bill" ? "Bills" : filter === "receipt" ? "Receipts" : "Expenses"}
              </button>
            ))}
          </div>
        </div>
        <div className="table-scroll">
          <table className="data-table expense-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Tag</th>
                <th>Type</th>
                <th>Receipt</th>
                <th>Status</th>
                <th>Date</th>
                <th>Amount</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}<small>{item.vendor}{item.note ? ` - ${item.note}` : ""}</small></td>
                  <td><span className="expense-tag-pill" style={{ "--tag-color": item.color }}>{item.category}</span></td>
                  <td>{item.type}</td>
                  <td>{item.receiptNumber || "-"}</td>
                  <td><span className={`finance-status status-${item.status}`}>{item.status}</span></td>
                  <td>{formatDate(item.date)}</td>
                  <td>{formatExpenseAmount(item.amount)}</td>
                  <td>
                    <button type="button" className="table-action" onClick={() => handleDelete(item.id)} disabled={deletingId === item.id}>
                      {deletingId === item.id ? "Deleting..." : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
              {!filteredItems.length ? (
                <tr><td colSpan="8">No records in this view.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
