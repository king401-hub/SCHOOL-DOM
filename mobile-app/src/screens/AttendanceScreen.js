import { Alert, Text, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { PrimaryButton } from "../components/PrimaryButton";
import { markAttendance } from "../api/endpoints";
import { getCurrentPosition } from "../services/location";
import { colors, spacing } from "../theme/tokens";

export function AttendanceScreen() {
  async function submitAttendance() {
    try {
      const position = await getCurrentPosition();
      await markAttendance({
        status: "present",
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      });
      Alert.alert("Attendance sent", "Your attendance was submitted.");
    } catch (error) {
      Alert.alert("Attendance failed", error.message);
    }
  }

  return (
    <Screen>
      <Text style={{ color: colors.text, fontSize: 28, fontWeight: "900" }}>Attendance</Text>
      <Card>
        <Text style={{ color: colors.textDark, fontWeight: "900", fontSize: 18 }}>GPS attendance</Text>
        <Text style={{ color: colors.mutedDark, marginBottom: spacing.md }}>Submit your current location to the shared Django attendance API.</Text>
        <PrimaryButton title="Mark attendance" onPress={submitAttendance} />
      </Card>
    </Screen>
  );
}
