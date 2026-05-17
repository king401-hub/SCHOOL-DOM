import "react-native-gesture-handler";
import { useEffect } from "react";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { AuthProvider, useAuth } from "./src/auth/AuthProvider";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { registerBackgroundSync } from "./src/services/backgroundSync";
import { colors } from "./src/theme/tokens";

SplashScreen.preventAutoHideAsync().catch(() => {});

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.background,
    card: colors.surface,
    primary: colors.primary,
    text: colors.text,
    border: colors.border,
  },
};

function AppShell() {
  const { isBooting } = useAuth();

  useEffect(() => {
    registerBackgroundSync();
  }, []);

  useEffect(() => {
    if (!isBooting) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [isBooting]);

  return (
    <NavigationContainer theme={navTheme}>
      <StatusBar style="light" backgroundColor={colors.background} />
      <RootNavigator />
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
