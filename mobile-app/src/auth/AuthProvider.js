import { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as LocalAuthentication from "expo-local-authentication";
import { subscribeToAuthEvents } from "./authEvents";
import { clearSession, getSession, isBiometricEnabled, saveSession, setBiometricEnabled } from "../storage/sessionStore";
import { login, verifyAdminOtp } from "../api/auth";
import { registerForPushNotifications } from "../services/notifications";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [isBooting, setIsBooting] = useState(true);
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function boot() {
      const stored = await getSession();
      const biometric = await isBiometricEnabled();
      if (!mounted) return;
      setSession(stored);
      setLocked(Boolean(stored && biometric));
      setIsBooting(false);
    }
    boot();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    return subscribeToAuthEvents(async (event) => {
      if (event?.type !== "sessionExpired") return;
      await clearSession();
      setSession(null);
      setLocked(false);
    });
  }, []);

  const value = useMemo(
    () => ({
      session,
      locked,
      isBooting,
      async signIn(credentials) {
        const next = await login(credentials);
        if (next.requiresOtp) return next;
        await saveSession(next);
        setSession(next);
        registerForPushNotifications().catch(() => {});
        return next;
      },
      async completeOtp(payload) {
        const next = await verifyAdminOtp(payload);
        await saveSession(next);
        setSession(next);
        registerForPushNotifications().catch(() => {});
        return next;
      },
      async unlock() {
        const result = await LocalAuthentication.authenticateAsync({
          promptMessage: "Unlock SchoolDom",
          fallbackLabel: "Use passcode",
        });
        if (result.success) setLocked(false);
        return result.success;
      },
      async enableBiometrics(enabled) {
        await setBiometricEnabled(enabled);
        setLocked(false);
      },
      async signOut() {
        await clearSession();
        setSession(null);
        setLocked(false);
      },
    }),
    [isBooting, locked, session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
