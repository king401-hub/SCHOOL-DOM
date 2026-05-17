import { SafeAreaView } from "react-native-safe-area-context";
import { ScrollView, StyleSheet, View } from "react-native";
import { colors, spacing } from "../theme/tokens";

export function Screen({ children, scroll = true, contentStyle, refreshControl }) {
  const body = <View style={[styles.content, contentStyle]}>{children}</View>;
  return (
    <SafeAreaView style={styles.safe}>
      {scroll ? <ScrollView keyboardShouldPersistTaps="handled" refreshControl={refreshControl}>{body}</ScrollView> : body}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
});
