import { Alert, Text } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { PrimaryButton } from "../components/PrimaryButton";
import { useAuth } from "../auth/AuthProvider";
import { pickDocument, takeProfilePhoto } from "../services/files";
import { registerForPushNotifications } from "../services/notifications";
import { colors, spacing } from "../theme/tokens";

export function SettingsScreen() {
  const { enableBiometrics, signOut } = useAuth();

  return (
    <Screen>
      <Text style={{ color: colors.text, fontSize: 28, fontWeight: "900" }}>Settings</Text>
      <Card>
        <Text style={{ color: colors.textDark, fontWeight: "900", fontSize: 18 }}>Device services</Text>
        <PrimaryButton title="Enable biometric unlock" onPress={() => enableBiometrics(true).then(() => Alert.alert("Enabled", "Biometric unlock is ready."))} />
        <PrimaryButton title="Enable push notifications" onPress={() => registerForPushNotifications().then(() => Alert.alert("Notifications", "Device registered if permission was granted."))} />
        <PrimaryButton title="Open camera" tone="ghost" onPress={takeProfilePhoto} />
        <PrimaryButton title="Pick file" tone="ghost" onPress={pickDocument} />
      </Card>
      <PrimaryButton title="Sign out" tone="ghost" onPress={signOut} />
    </Screen>
  );
}
