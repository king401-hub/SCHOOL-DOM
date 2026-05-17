import * as SecureStore from "expo-secure-store";

const SESSION_KEY = "schooldom.native.session";
const BIOMETRIC_KEY = "schooldom.native.biometric_enabled";

export async function getSession() {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
}

export async function saveSession(session) {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
}

export async function clearSession() {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}

export async function isBiometricEnabled() {
  return (await SecureStore.getItemAsync(BIOMETRIC_KEY)) === "true";
}

export async function setBiometricEnabled(value) {
  await SecureStore.setItemAsync(BIOMETRIC_KEY, value ? "true" : "false");
}
