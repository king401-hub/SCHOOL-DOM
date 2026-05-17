import { useState } from "react";
import { Alert, StyleSheet, Text, TextInput, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { PrimaryButton } from "../components/PrimaryButton";
import { useAuth } from "../auth/AuthProvider";
import { colors, radius, spacing } from "../theme/tokens";

export function LoginScreen() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [otp, setOtp] = useState(null);
  const [otpCode, setOtpCode] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      if (otp) {
        await auth.completeOtp({ email: otp.email, code: otpCode, challenge: otp.challenge });
      } else {
        const result = await auth.signIn({ email, password, schoolCode });
        if (result.requiresOtp) setOtp(result);
      }
    } catch (error) {
      Alert.alert("Sign in failed", error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen contentStyle={styles.screen}>
      <View>
        <Text style={styles.brand}>SchoolDom App</Text>
        <Text style={styles.title}>Native school workspace</Text>
        <Text style={styles.copy}>Use your existing SchoolDom account and school code.</Text>
      </View>

      <Card>
        {otp ? (
          <>
            <Text style={styles.cardTitle}>Admin verification</Text>
            <Text style={styles.helper}>Enter the 6-digit code sent to {otp.email}.</Text>
            <TextInput style={styles.input} value={otpCode} onChangeText={setOtpCode} keyboardType="number-pad" maxLength={6} placeholder="000000" />
          </>
        ) : (
          <>
            <Text style={styles.cardTitle}>Sign in</Text>
            <TextInput style={styles.input} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="Email address" />
            <TextInput style={styles.input} value={password} onChangeText={setPassword} secureTextEntry placeholder="Password" />
            <TextInput style={styles.input} value={schoolCode} onChangeText={setSchoolCode} autoCapitalize="none" placeholder="School code" />
          </>
        )}
        <PrimaryButton title={loading ? "Please wait..." : otp ? "Verify and continue" : "Sign in"} onPress={submit} disabled={loading} />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: {
    flexGrow: 1,
    justifyContent: "center",
  },
  brand: {
    color: colors.primary,
    fontWeight: "900",
    fontSize: 16,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  title: {
    color: colors.text,
    fontSize: 34,
    fontWeight: "900",
    marginTop: spacing.sm,
  },
  copy: {
    color: colors.muted,
    fontSize: 16,
    marginTop: spacing.sm,
  },
  cardTitle: {
    color: colors.textDark,
    fontSize: 22,
    fontWeight: "900",
  },
  helper: {
    color: colors.mutedDark,
  },
  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: "#dbe3ef",
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.textDark,
    backgroundColor: colors.cardSoft,
  },
});
