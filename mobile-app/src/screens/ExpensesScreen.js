import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Pressable, RefreshControl, StyleSheet, Text, TextInput, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { PrimaryButton } from "../components/PrimaryButton";
import { createExpenseRecord, deleteExpenseRecord, loadExpenses } from "../api/endpoints";
import { replayOfflineQueue } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { readCache, writeCache } from "../storage/offlineCache";
import { colors, radius, spacing } from "../theme/tokens";

const NAIRA_SYMBOL = "\u20A6";
const TYPE_OPTIONS = ["expense", "bill", "receipt"];
const STATUS_OPTIONS = ["pending", "due", "paid"];
const TAGS = [
  { label: "Operations", color: "#14b8a6" },
  { label: "Utilities", color: "#f59e0b" },
  { label: "Supplies", color: "#6366f1" },
  { label: "Payroll", color: "#ec4899" },
  { label: "Maintenance", color: "#22c55e" },
  { label: "Transport", color: "#ef4444" },
];

function money(value) {
  return `${NAIRA_SYMBOL}${Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

const initialForm = {
  title: "",
  vendor: "",
  phoneNumber: "",
  amount: "",
  type: "expense",
  status: "pending",
  category: TAGS[0].label,
  color: TAGS[0].color,
  date: today(),
  receiptNumber: "",
  note: "",
};

export function ExpensesScreen() {
  const { session } = useAuth();
  const [data, setData] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [activeType, setActiveType] = useState("all");
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const cacheScope =
    session?.school_code ||
    session?.school?.school_code ||
    session?.user?.tenant_id ||
    session?.user?.tenant ||
    session?.user?.id ||
    session?.user?.email;

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError("");
    try {
      await replayOfflineQueue();
      const snapshot = await loadExpenses();
      setData(snapshot);
      await writeCache("expenses", snapshot, cacheScope);
    } catch (refreshError) {
      const cached = await readCache("expenses", cacheScope);
      if (cached?.data) {
        setData(cached.data);
        setError("Showing cached expense records until the app reconnects.");
      } else {
        setError(refreshError.message || "Could not load expense records.");
      }
    } finally {
      setRefreshing(false);
    }
  }, [cacheScope]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const records = data?.records || [];
  const filteredRecords = activeType === "all" ? records : records.filter((item) => item.type === activeType);
  const totals = useMemo(() => {
    return records.reduce(
      (sum, item) => {
        const amount = Number(item.amount || 0);
        sum.all += amount;
        sum[item.type] = (sum[item.type] || 0) + amount;
        return sum;
      },
      { all: 0, expense: 0, bill: 0, receipt: 0 }
    );
  }, [records]);

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function setTag(tag) {
    setForm((current) => ({ ...current, category: tag.label, color: tag.color }));
  }

  async function submit() {
    setMessage("");
    setError("");
    const amount = Number(form.amount);
    if (!form.title.trim() || !amount || amount <= 0) {
      setError("Add a title and a valid amount.");
      return;
    }
    setSaving(true);
    try {
      const result = await createExpenseRecord({
        ...form,
        title: form.title.trim(),
        vendor: form.vendor.trim() || "Unassigned",
        phoneNumber: form.phoneNumber.trim(),
        amount,
        receiptNumber: form.receiptNumber.trim(),
        note: form.note.trim(),
      });
      setForm({ ...initialForm, type: form.type, status: form.status, date: today() });
      setMessage(result.offline ? result.message : "Record synced to the web dashboard.");
      await refresh();
    } catch (submitError) {
      setError(submitError.message || "Could not save expense record.");
    } finally {
      setSaving(false);
    }
  }

  function confirmDelete(record) {
    Alert.alert("Delete record", `Delete ${record.title}?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          setError("");
          setMessage("");
          try {
            await deleteExpenseRecord(record.id);
            setMessage("Record removed from the web dashboard.");
            await refresh();
          } catch (deleteError) {
            setError(deleteError.message || "Could not delete record.");
          }
        },
      },
    ]);
  }

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.primary} />}>
      <View>
        <Text style={styles.kicker}>Finance sync</Text>
        <Text style={styles.title}>Expenses</Text>
        <Text style={styles.copy}>Records saved here use the same backend as the web Expenses page.</Text>
      </View>

      <View style={styles.metricRow}>
        <Metric label="Total" value={money(totals.all)} />
        <Metric label="Bills" value={money(totals.bill)} />
      </View>

      <Card>
        <Text style={styles.cardTitle}>New Record</Text>
        <Field label="Title" value={form.title} onChangeText={(value) => updateForm("title", value)} placeholder="Example: Lab supplies" />
        <Field label="Amount" value={form.amount} onChangeText={(value) => updateForm("amount", value)} keyboardType="decimal-pad" placeholder="0.00" />
        <Field label="Vendor" value={form.vendor} onChangeText={(value) => updateForm("vendor", value)} placeholder="Vendor or staff member" />
        <Field label="Phone" value={form.phoneNumber} onChangeText={(value) => updateForm("phoneNumber", value)} keyboardType="phone-pad" placeholder="Optional" />
        <Field label="Date" value={form.date} onChangeText={(value) => updateForm("date", value)} placeholder="YYYY-MM-DD" />
        <Field label="Receipt No." value={form.receiptNumber} onChangeText={(value) => updateForm("receiptNumber", value)} placeholder="Optional" />
        <OptionRow label="Type" value={form.type} options={TYPE_OPTIONS} onChange={(value) => updateForm("type", value)} />
        <OptionRow label="Status" value={form.status} options={STATUS_OPTIONS} onChange={(value) => updateForm("status", value)} />
        <Text style={styles.label}>Color Tag</Text>
        <View style={styles.tagGrid}>
          {TAGS.map((tag) => (
            <Pressable key={tag.label} onPress={() => setTag(tag)} style={[styles.tagButton, form.category === tag.label && styles.activeTag]}>
              <View style={[styles.tagDot, { backgroundColor: tag.color }]} />
              <Text style={styles.tagText}>{tag.label}</Text>
            </Pressable>
          ))}
        </View>
        <Field label="Note" value={form.note} onChangeText={(value) => updateForm("note", value)} multiline placeholder="Optional details" />
        {message ? <Text style={styles.success}>{message}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <PrimaryButton title={saving ? "Saving..." : "Save and Sync"} onPress={submit} disabled={saving} />
      </Card>

      <View style={styles.filters}>
        {["all", ...TYPE_OPTIONS].map((type) => (
          <Pressable key={type} onPress={() => setActiveType(type)} style={[styles.filterButton, activeType === type && styles.filterActive]}>
            <Text style={[styles.filterText, activeType === type && styles.filterTextActive]}>{type === "all" ? "All" : type}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.list}>
        {filteredRecords.map((record) => (
          <Card key={record.id}>
            <View style={styles.recordHead}>
              <View style={styles.recordTitleWrap}>
                <Text style={styles.recordTitle}>{record.title}</Text>
                <Text style={styles.recordMeta}>{[record.vendor, record.phoneNumber, record.receiptNumber].filter(Boolean).join(" - ") || record.type}</Text>
              </View>
              <Text style={styles.recordAmount}>{money(record.amount)}</Text>
            </View>
            <View style={styles.recordFoot}>
              <Text style={styles.pill}>{record.status}</Text>
              <Text style={styles.recordDate}>{record.date}</Text>
              <Pressable onPress={() => confirmDelete(record)}>
                <Text style={styles.deleteText}>Delete</Text>
              </Pressable>
            </View>
          </Card>
        ))}
        {!filteredRecords.length ? <Text style={styles.empty}>No records in this view yet.</Text> : null}
      </View>
    </Screen>
  );
}

function Field({ label, style, ...props }) {
  return (
    <View style={style}>
      <Text style={styles.label}>{label}</Text>
      <TextInput {...props} placeholderTextColor="#94a3b8" style={[styles.input, props.multiline && styles.textarea]} />
    </View>
  );
}

function OptionRow({ label, value, options, onChange }) {
  return (
    <View>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.optionRow}>
        {options.map((option) => (
          <Pressable key={option} onPress={() => onChange(option)} style={[styles.optionButton, value === option && styles.optionActive]}>
            <Text style={[styles.optionText, value === option && styles.optionTextActive]}>{option}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Metric({ label, value }) {
  return (
    <Card style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  kicker: {
    color: colors.primary,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "900",
    marginTop: spacing.sm,
  },
  copy: {
    color: colors.muted,
    marginTop: spacing.sm,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.md,
  },
  metric: {
    flex: 1,
  },
  metricLabel: {
    color: colors.mutedDark,
    fontWeight: "800",
  },
  metricValue: {
    color: colors.textDark,
    fontSize: 20,
    fontWeight: "900",
  },
  cardTitle: {
    color: colors.textDark,
    fontSize: 18,
    fontWeight: "900",
  },
  label: {
    color: colors.mutedDark,
    fontWeight: "800",
    marginBottom: spacing.xs,
  },
  input: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: "#d8e0ea",
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    color: colors.textDark,
    backgroundColor: colors.cardSoft,
    fontWeight: "700",
  },
  textarea: {
    minHeight: 86,
    paddingTop: spacing.md,
    textAlignVertical: "top",
  },
  optionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  optionButton: {
    borderWidth: 1,
    borderColor: "#d8e0ea",
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.cardSoft,
  },
  optionActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  optionText: {
    color: colors.mutedDark,
    fontWeight: "900",
    textTransform: "capitalize",
  },
  optionTextActive: {
    color: colors.primary,
  },
  tagGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  tagButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: "#d8e0ea",
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  activeTag: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  tagDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  tagText: {
    color: colors.textDark,
    fontWeight: "800",
  },
  success: {
    color: colors.success,
    fontWeight: "800",
  },
  error: {
    color: colors.danger,
    fontWeight: "800",
  },
  filters: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  filterButton: {
    flex: 1,
    alignItems: "center",
    borderRadius: radius.sm,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surfaceSoft,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterText: {
    color: colors.muted,
    fontWeight: "900",
    textTransform: "capitalize",
  },
  filterTextActive: {
    color: "#fff",
  },
  list: {
    gap: spacing.md,
  },
  recordHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  recordTitleWrap: {
    flex: 1,
  },
  recordTitle: {
    color: colors.textDark,
    fontSize: 16,
    fontWeight: "900",
  },
  recordMeta: {
    color: colors.mutedDark,
    marginTop: spacing.xs,
  },
  recordAmount: {
    color: colors.textDark,
    fontWeight: "900",
  },
  recordFoot: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  pill: {
    overflow: "hidden",
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    color: colors.primary,
    fontWeight: "900",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "capitalize",
  },
  recordDate: {
    flex: 1,
    color: colors.mutedDark,
    fontWeight: "700",
  },
  deleteText: {
    color: colors.danger,
    fontWeight: "900",
  },
  empty: {
    color: colors.muted,
    textAlign: "center",
    fontWeight: "800",
  },
});
