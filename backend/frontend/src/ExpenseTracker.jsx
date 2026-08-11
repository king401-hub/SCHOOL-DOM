import { useEffect, useMemo, useState } from "react";
import { DashboardIcon, ScreenState, Spinner, formatDate, openPrintableDocument, resolveSchoolBrand, resolveDocumentTheme } from "./AppShared";

const PAYSLIP_STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "paid", label: "Paid" },
];

const PAYMENT_METHOD_OPTIONS = ["Bank Transfer", "Cash", "Cheque"];

const monthName = (month) =>
  new Date(2000, Number(month) - 1, 1).toLocaleString(undefined, { month: "long" });

const NAIRA_SYMBOL = "\u20A6";

const EXPENSE_TAGS = [
  { label: "Operations", color: "#14b8a6" },
  { label: "Utilities", color: "#f59e0b" },
  { label: "Supplies", color: "#6366f1" },
  { label: "Payroll", color: "#ec4899" },
  { label: "Maintenance", color: "#22c55e" },
  { label: "Transport", color: "#ef4444" },
];

export default function ExpenseTracker({
  data, school, loading, error, onRetry, onCreate, onDelete, onSettle,
  onCreatePayslip, onSendPayslip, onLoadStaffOptions,
}) {
  const items = data?.records || [];
  const salaryPaymentSummary = data?.salary_payment_summary || {};
  const schoolBrand = resolveSchoolBrand(data?.school, school);
  const documentTheme = resolveDocumentTheme(data?.school, school);
  const [form, setForm] = useState({
    title: "",
    vendor: "",
    phoneNumber: "",
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
  const [searchTerm, setSearchTerm] = useState("");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState("");

  // ── Payslip ──────────────────────────────────────────────────────────
  const now = new Date();
  const [payslipForm, setPayslipForm] = useState({
    staffId: "",
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    basicSalary: "0",
    allowances: "0",
    deductions: "0",
    paymentDate: now.toISOString().slice(0, 10),
    paymentMethod: PAYMENT_METHOD_OPTIONS[0],
    status: "approved",
    remarks: "",
  });
  const [staffOptions, setStaffOptions] = useState([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffLoaded, setStaffLoaded] = useState(false);
  const [payslipSaving, setPayslipSaving] = useState(false);
  const [payslipError, setPayslipError] = useState("");
  const [generatedPayslip, setGeneratedPayslip] = useState(null);
  const [sendChannel, setSendChannel] = useState("email");
  const [sendRecipient, setSendRecipient] = useState("");
  const [sendingPayslip, setSendingPayslip] = useState(false);
  const [sendFeedback, setSendFeedback] = useState("");
  const [sendError, setSendError] = useState("");

  useEffect(() => {
    if (form.type === "payslip" && !staffLoaded && onLoadStaffOptions) {
      setStaffLoading(true);
      onLoadStaffOptions()
        .then((list) => setStaffOptions(list || []))
        .catch(() => setStaffOptions([]))
        .finally(() => {
          setStaffLoading(false);
          setStaffLoaded(true);
        });
    }
  }, [form.type, staffLoaded, onLoadStaffOptions]);

  const selectedStaff = useMemo(
    () => staffOptions.find((item) => String(item.id) === String(payslipForm.staffId)) || null,
    [staffOptions, payslipForm.staffId]
  );

  const netSalaryPreview = useMemo(() => {
    const basic = Number(payslipForm.basicSalary || 0);
    const allowances = Number(payslipForm.allowances || 0);
    const deductions = Number(payslipForm.deductions || 0);
    return Math.max(basic + allowances - deductions, 0);
  }, [payslipForm.basicSalary, payslipForm.allowances, payslipForm.deductions]);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [settlingId, setSettlingId] = useState("");

  const formatExpenseAmount = (value) =>
    `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  // Total Outflow, Settled/Unsettled, Balance, and Spending % all come from
  // the shared backend finance summary (finance.services.compute_finance_summary)
  // instead of being derived here - this is the same object the Finance
  // Dashboard reads, so the two pages can never disagree on these figures.
  const financeSummary = data?.finance_summary || {};
  const expectedFeesAmount = Number(financeSummary.expected_fees || 0);
  const feesCollectedAmount = Number(financeSummary.fees_collected || 0);
  const outstandingAmount = Number(financeSummary.outstanding || 0);
  const totalOutflowAmount = Number(financeSummary.total_outflow || 0);
  const settledOutflowAmount = Number(financeSummary.settled_outflow || 0);
  const unsettledPaymentsAmount = Number(financeSummary.unsettled_payments || 0);
  const balanceAmount = Number(financeSummary.balance || 0);
  // Backend allows this to exceed 100 internally (overspending signal); only the display is capped.
  const spendingPercentage = Math.min(100, Math.round(Number(financeSummary.spending_percentage || 0)));
  const staffSalaryAmount = Number(salaryPaymentSummary.staff_salary_amount || 0);

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
  const typeFilteredItems = activeFilter === "all" ? items : items.filter((item) => item.type === activeFilter);
  const searchNeedle = searchTerm.trim().toLowerCase();
  const filteredItems = !searchNeedle
    ? typeFilteredItems
    : typeFilteredItems.filter((item) =>
        [item.title, item.vendor, item.category, item.receiptNumber, item.note]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(searchNeedle))
      );

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
        phoneNumber: form.phoneNumber.trim(),
        amount,
        note: form.note.trim(),
        receiptNumber: form.receiptNumber.trim(),
      });
      setForm((current) => ({
        ...current,
        title: "",
        vendor: "",
        phoneNumber: "",
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

  const handleSelectStaff = (staffId) => {
    const staff = staffOptions.find((item) => String(item.id) === String(staffId));
    setPayslipForm((current) => ({
      ...current,
      staffId,
      basicSalary: staff ? String(staff.base_salary ?? "0") : current.basicSalary,
    }));
  };

  const handlePayslipSubmit = async (event) => {
    event.preventDefault();
    setPayslipError("");
    setSendFeedback("");
    setSendError("");
    if (!payslipForm.staffId) {
      setPayslipError("Select an employee.");
      return;
    }
    setPayslipSaving(true);
    try {
      const result = await onCreatePayslip({
        staff_id: payslipForm.staffId,
        year: payslipForm.year,
        month: payslipForm.month,
        allowances: payslipForm.allowances || "0",
        deductions: payslipForm.deductions || "0",
        payment_date: payslipForm.paymentDate,
        payment_method: payslipForm.paymentMethod,
        status: payslipForm.status,
        remarks: payslipForm.remarks.trim(),
      });
      setGeneratedPayslip(result?.payslip || null);
      setSendRecipient(selectedStaff?.email || "");
      setFeedback("Payslip generated.");
    } catch (err) {
      setPayslipError(err.message || "Could not generate payslip.");
    } finally {
      setPayslipSaving(false);
    }
  };

  const handleSendPayslip = async (event) => {
    event.preventDefault();
    setSendFeedback("");
    setSendError("");
    if (!generatedPayslip) return;
    setSendingPayslip(true);
    try {
      const result = await onSendPayslip(generatedPayslip.expense_record_id, {
        channel: sendChannel,
        recipient: sendRecipient.trim(),
      });
      setSendFeedback(result?.message || "Payslip sent.");
    } catch (err) {
      setSendError(err.message || "Could not send payslip.");
    } finally {
      setSendingPayslip(false);
    }
  };

  const handlePrintPayslip = () => {
    try {
      openPrintableDocument("payslip-document", `Payslip - ${generatedPayslip?.staff_name || ""} - ${generatedPayslip?.period || ""}`, documentTheme);
    } catch (err) {
      setSendError(err.message || "Could not open the printable payslip.");
    }
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

  const handleSettle = async (itemId) => {
    setFeedback("");
    setFormError("");
    setSettlingId(itemId);
    try {
      await onSettle(itemId);
      setFeedback("Record marked as settled.");
    } catch (err) {
      setFormError(err.message || "Could not settle record.");
    } finally {
      setSettlingId("");
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
          <strong>{formatExpenseAmount(totalOutflowAmount)}</strong>
        </div>
      </div>
      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <article className="app-panel expense-chart-panel">
        <div className="expense-panel-head">
          <h3>Spending Graph</h3>
          <span>{categoryRows.length} tags</span>
        </div>
        <div className="expense-chart-layout">
          <div>
            <div className="expense-donut" style={{ "--paid": `${spendingPercentage}%` }}>
              <strong>{spendingPercentage}%</strong>
              <span>spent</span>
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
              <span>Expected fees</span>
              <strong>{formatExpenseAmount(expectedFeesAmount)}</strong>
            </div>
            <div>
              <span>Fees collected</span>
              <strong>{formatExpenseAmount(feesCollectedAmount)}</strong>
            </div>
            <div>
              <span>Outstanding</span>
              <strong>{formatExpenseAmount(outstandingAmount)}</strong>
            </div>
            <div>
              <span>Settled outflow</span>
              <strong>{formatExpenseAmount(settledOutflowAmount)}</strong>
            </div>
            <div>
              <span>Unsettled payments</span>
              <strong>{formatExpenseAmount(unsettledPaymentsAmount)}</strong>
            </div>
            <div>
              <span>Staff salary</span>
              <strong>{formatExpenseAmount(staffSalaryAmount)}</strong>
            </div>
            <div>
              <span>Balance</span>
              <strong>{formatExpenseAmount(balanceAmount)}</strong>
            </div>
          </div>
        </div>
      </article>

      <div className="expense-workspace">
        <article className="app-panel expense-create-panel">
          <h3>{form.type === "payslip" ? "Generate Payslip" : "Create Expense, Bill, or Receipt"}</h3>
          <label className="panel-field">
            Type
            <select value={form.type} onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}>
              <option value="expense">Expense</option>
              <option value="bill">Bill</option>
              <option value="receipt">Receipt</option>
              <option value="payslip">Payslip</option>
            </select>
          </label>

          {form.type === "payslip" ? (
            <form className="panel-form" onSubmit={handlePayslipSubmit}>
              <div className="panel-form-grid">
                <label className="panel-field">
                  Employee
                  <select value={payslipForm.staffId} onChange={(event) => handleSelectStaff(event.target.value)} required>
                    <option value="">{staffLoading ? "Loading staff..." : "Select employee"}</option>
                    {staffOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
                <label className="panel-field">
                  Staff ID
                  <input value={selectedStaff?.staff_code || ""} readOnly />
                </label>
                <label className="panel-field">
                  Department
                  <input value={selectedStaff?.department || ""} readOnly />
                </label>
                <label className="panel-field">
                  Position
                  <input value={selectedStaff?.role || ""} readOnly />
                </label>
                <label className="panel-field">
                  Pay Period - Month
                  <select value={payslipForm.month} onChange={(event) => setPayslipForm((current) => ({ ...current, month: Number(event.target.value) }))}>
                    {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                      <option key={month} value={month}>{monthName(month)}</option>
                    ))}
                  </select>
                </label>
                <label className="panel-field">
                  Pay Period - Year
                  <input type="number" value={payslipForm.year} onChange={(event) => setPayslipForm((current) => ({ ...current, year: Number(event.target.value) }))} />
                </label>
                <label className="panel-field">
                  Basic Salary
                  <input type="number" min="0" step="0.01" value={payslipForm.basicSalary} onChange={(event) => setPayslipForm((current) => ({ ...current, basicSalary: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Allowances
                  <input type="number" min="0" step="0.01" value={payslipForm.allowances} onChange={(event) => setPayslipForm((current) => ({ ...current, allowances: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Deductions
                  <input type="number" min="0" step="0.01" value={payslipForm.deductions} onChange={(event) => setPayslipForm((current) => ({ ...current, deductions: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Net Salary
                  <input value={formatExpenseAmount(netSalaryPreview)} readOnly />
                </label>
                <label className="panel-field">
                  Payment Date
                  <input type="date" value={payslipForm.paymentDate} onChange={(event) => setPayslipForm((current) => ({ ...current, paymentDate: event.target.value }))} />
                </label>
                <label className="panel-field">
                  Payment Method
                  <select value={payslipForm.paymentMethod} onChange={(event) => setPayslipForm((current) => ({ ...current, paymentMethod: event.target.value }))}>
                    {PAYMENT_METHOD_OPTIONS.map((method) => (
                      <option key={method} value={method}>{method}</option>
                    ))}
                  </select>
                </label>
                <label className="panel-field">
                  Status
                  <select value={payslipForm.status} onChange={(event) => setPayslipForm((current) => ({ ...current, status: event.target.value }))}>
                    {PAYSLIP_STATUS_OPTIONS.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                <label className="panel-field full">
                  Remarks
                  <textarea value={payslipForm.remarks} onChange={(event) => setPayslipForm((current) => ({ ...current, remarks: event.target.value }))} rows="2" placeholder="Optional notes for this payslip" />
                </label>
              </div>
              {feedback ? <p className="form-feedback success">{feedback}</p> : null}
              {payslipError ? <p className="form-feedback error">{payslipError}</p> : null}
              <div className="panel-form-actions">
                <button type="submit" disabled={payslipSaving}>{payslipSaving ? <><Spinner size={12} /> Generating...</> : "Generate Payslip"}</button>
              </div>
            </form>
          ) : (
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
                  Phone number
                  <input type="tel" value={form.phoneNumber} onChange={(event) => setForm((current) => ({ ...current, phoneNumber: event.target.value }))} placeholder="Vendor phone number" />
                </label>
                <label className="panel-field">
                  Date
                  <input type="date" value={form.date} onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))} />
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
                <button type="submit" disabled={isSaving}>{isSaving ? <><Spinner size={12} /> Saving...</> : "Save Record"}</button>
              </div>
            </form>
          )}
        </article>

        {generatedPayslip ? (
          <article className="app-panel expense-create-panel payslip-preview-panel">
            <div className="expense-panel-head">
              <h3>Payslip Preview</h3>
              <div className="table-actions-inline">
                <button type="button" className="table-action" onClick={handlePrintPayslip}>Print</button>
                <button type="button" className="table-action" onClick={handlePrintPayslip}>Download as PDF</button>
                <button type="button" className="table-action" onClick={() => setGeneratedPayslip(null)}>Close</button>
              </div>
            </div>

            <div id="payslip-document" className="payslip-document">
              <div className="print-letterhead">
                {schoolBrand.logo ? <img src={schoolBrand.logo} alt={`${schoolBrand.name} logo`} /> : null}
                <div>
                  <h1>{schoolBrand.name}</h1>
                  <p>{schoolBrand.address || "School address"}</p>
                </div>
              </div>
              <h2>Payslip - {generatedPayslip.period}</h2>
              <div className="print-meta">
                <p><strong>Employee:</strong> {generatedPayslip.staff_name}</p>
                <p><strong>Staff ID:</strong> {generatedPayslip.staff_code}</p>
                <p><strong>Department:</strong> {generatedPayslip.department || "-"}</p>
                <p><strong>Position:</strong> {generatedPayslip.role || "-"}</p>
                <p><strong>Payment Date:</strong> {formatDate(generatedPayslip.payment_date)}</p>
                <p><strong>Payment Method:</strong> {generatedPayslip.payment_method || "-"}</p>
                <p><strong>Status:</strong> {generatedPayslip.status}</p>
              </div>
              <table>
                <tbody>
                  <tr><td>Basic Salary</td><td>{formatExpenseAmount(generatedPayslip.basic_salary)}</td></tr>
                  <tr><td>Allowances</td><td>{formatExpenseAmount(generatedPayslip.allowances)}</td></tr>
                  <tr><td>Deductions</td><td>-{formatExpenseAmount(generatedPayslip.deductions)}</td></tr>
                  {Number(generatedPayslip.advances_applied) > 0 ? (
                    <tr><td>Salary Advance Applied</td><td>-{formatExpenseAmount(generatedPayslip.advances_applied)}</td></tr>
                  ) : null}
                  <tr><td><strong>Net Salary</strong></td><td><strong>{formatExpenseAmount(generatedPayslip.net_salary)}</strong></td></tr>
                </tbody>
              </table>
              {generatedPayslip.remarks ? <p className="print-body">Remarks: {generatedPayslip.remarks}</p> : null}
              <p className="print-signature">Authorized signature: ____________________</p>
            </div>

            <form className="panel-form" onSubmit={handleSendPayslip}>
              <div className="panel-form-grid">
                <label className="panel-field">
                  Send via
                  <select value={sendChannel} onChange={(event) => setSendChannel(event.target.value)}>
                    <option value="email">Email</option>
                    <option value="sms">SMS Link</option>
                  </select>
                </label>
                <label className="panel-field">
                  {sendChannel === "email" ? "Recipient email" : "Recipient phone"}
                  <input
                    value={sendRecipient}
                    onChange={(event) => setSendRecipient(event.target.value)}
                    placeholder={sendChannel === "email" ? selectedStaff?.email || "employee@school.edu" : selectedStaff?.phone || "080..."}
                  />
                </label>
              </div>
              {sendFeedback ? <p className="form-feedback success">{sendFeedback}</p> : null}
              {sendError ? <p className="form-feedback error">{sendError}</p> : null}
              <div className="panel-form-actions">
                <button type="submit" disabled={sendingPayslip}>{sendingPayslip ? <><Spinner size={12} /> Sending...</> : "Send Payslip"}</button>
              </div>
            </form>
          </article>
        ) : null}

      </div>

      <article className="app-panel">
        <div className="expense-panel-head">
          <h3>Expense Register</h3>
          <div className="expense-tabs">
            {["all", "expense", "bill", "receipt", "payslip"].map((filter) => (
              <button key={filter} type="button" className={activeFilter === filter ? "active" : ""} onClick={() => setActiveFilter(filter)}>
                {filter === "all" ? "All" : filter === "bill" ? "Bills" : filter === "receipt" ? "Receipts" : filter === "payslip" ? "Payslips" : "Expenses"}
              </button>
            ))}
          </div>
        </div>
        <input
          type="search"
          className="expense-search-input"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Search by name, vendor, tag, or receipt no."
          aria-label="Search expense records"
        />
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
                  <td>{item.title}<small>{[item.vendor, item.phoneNumber, item.note].filter(Boolean).join(" - ")}</small></td>
                  <td><span className="expense-tag-pill" style={{ "--tag-color": item.color }}>{item.category}</span></td>
                  <td>
                    {item.type === "payslip" ? (
                      <span className="type-badge type-badge-payslip">Payslip</span>
                    ) : (
                      <span className="type-badge">{item.type}</span>
                    )}
                  </td>
                  <td>{item.receiptNumber || "-"}</td>
                  <td><span className={`finance-status status-${item.status}`}>{item.status}</span></td>
                  <td>{formatDate(item.date)}</td>
                  <td>{formatExpenseAmount(item.amount)}</td>
                  <td>
                    {item.status !== "paid" ? (
                      <button
                        type="button"
                        className="table-action"
                        onClick={() => handleSettle(item.id)}
                        disabled={settlingId === item.id}
                      >
                        {settlingId === item.id ? <><Spinner size={12} /> Settling...</> : "Settle"}
                      </button>
                    ) : null}
                    <button type="button" className="table-action" onClick={() => handleDelete(item.id)} disabled={deletingId === item.id}>
                      {deletingId === item.id ? <><Spinner size={12} /> Deleting...</> : "Delete"}
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
