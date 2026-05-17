import { Alert, StyleSheet, Text, View } from "react-native";
import { Screen } from "../components/Screen";
import { PrimaryButton } from "../components/PrimaryButton";
import { useAuth } from "../auth/AuthProvider";
import { colors, spacing } from "../theme/tokens";

export function LockScreen() {
  const { unlock, signOut } = useAuth();

  async function handleUnlock() {
    const ok = await unlock();
    if (!ok) Alert.alert("Unlock failed", "Biometric authentication did not complete.");
  }

  return (
    <Screen scroll={false} contentStyle={styles.screen}>
      <View>
        <Text style={styles.title}>SchoolDom is locked</Text>
        <Text style={styles.copy}>Unlock with your device biometrics to continue.</Text>
      </View>
      <PrimaryButton title="Unlock" onPress={handleUnlock} />
      <PrimaryButton title="Use another account" tone="ghost" onPress={signOut} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    justifyContent: "center",
  },
  title: {
    color: colors.text,
    fontSize: 30,
    fontWeight: "900",
  },
  copy: {
    color: colors.muted,
    marginTop: spacing.sm,
  },
});
