import { useCallback, useEffect, useState } from "react";
import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { useAuth } from "../auth/AuthProvider";
import { loadDashboard } from "../api/endpoints";
import { readCache, writeCache } from "../storage/offlineCache";
import { colors, spacing } from "../theme/tokens";

export function DashboardScreen() {
  const { session } = useAuth();
  const [snapshot, setSnapshot] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await loadDashboard(session?.user?.role);
      setSnapshot(data);
      await writeCache("dashboard", data);
    } catch {
      const cached = await readCache("dashboard");
      if (cached?.data) setSnapshot(cached.data);
    } finally {
      setRefreshing(false);
    }
  }, [session?.user?.role]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const metrics = snapshot?.metrics || {};
  const school = snapshot?.school?.name || session?.school?.name || "SchoolDom";

  return (
    <Screen
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.primary} />}
    >
      <View>
        <Text style={styles.kicker}>{school}</Text>
        <Text style={styles.title}>Welcome, {session?.user?.full_name || session?.user?.email}</Text>
        <Text style={styles.copy}>{session?.user?.role || "User"} workspace synced with the SchoolDom backend.</Text>
      </View>
      <View style={styles.grid}>
        <Metric label="Unread" value={metrics.unread_messages ?? metrics.unread_inbox ?? 0} />
        <Metric label="Notifications" value={metrics.unread_notifications ?? 0} />
        <Metric label="Students" value={metrics.students ?? metrics.total_students ?? "-"} />
        <Metric label="Exams" value={metrics.exams ?? metrics.upcoming_exams ?? "-"} />
      </View>
    </Screen>
  );
}

function Metric({ label, value }) {
  return (
    <Card style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{String(value)}</Text>
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
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  metric: {
    width: "47%",
  },
  metricLabel: {
    color: colors.mutedDark,
    fontWeight: "800",
  },
  metricValue: {
    color: colors.textDark,
    fontSize: 26,
    fontWeight: "900",
  },
});
