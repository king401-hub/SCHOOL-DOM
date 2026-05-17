import { Pressable, StyleSheet, Text } from "react-native";
import { colors, radius, spacing } from "../theme/tokens";

export function PrimaryButton({ title, onPress, disabled, tone = "primary" }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        tone === "ghost" && styles.ghost,
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
      ]}
    >
      <Text style={[styles.text, tone === "ghost" && styles.ghostText]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 48,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
  },
  ghost: {
    backgroundColor: colors.surfaceSoft,
    borderWidth: 1,
    borderColor: colors.border,
  },
  disabled: {
    opacity: 0.55,
  },
  pressed: {
    transform: [{ scale: 0.98 }],
  },
  text: {
    color: "#fff",
    fontWeight: "800",
  },
  ghostText: {
    color: colors.text,
  },
});
