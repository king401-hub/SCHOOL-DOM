import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { ActivityIndicator, Text, View } from "react-native";
import { useAuth } from "../auth/AuthProvider";
import { LoginScreen } from "../screens/LoginScreen";
import { LockScreen } from "../screens/LockScreen";
import { DashboardScreen } from "../screens/DashboardScreen";
import { ExamsScreen } from "../screens/ExamsScreen";
import { MessagesScreen } from "../screens/MessagesScreen";
import { AttendanceScreen } from "../screens/AttendanceScreen";
import { ResultsScreen } from "../screens/ResultsScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { colors } from "../theme/tokens";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function TabIcon({ label, focused }) {
  return (
    <View style={{ alignItems: "center" }}>
      <Text style={{ color: focused ? colors.primary : colors.muted, fontWeight: "900" }}>{label.slice(0, 1)}</Text>
    </View>
  );
}

function AppTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarIcon: ({ focused }) => <TabIcon label={route.name} focused={focused} />,
      })}
    >
      <Tab.Screen name="Home" component={DashboardScreen} />
      <Tab.Screen name="Exams" component={ExamsScreen} />
      <Tab.Screen name="Messages" component={MessagesScreen} />
      <Tab.Screen name="Attendance" component={AttendanceScreen} />
      <Tab.Screen name="Results" component={ResultsScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  const { session, locked, isBooting } = useAuth();

  if (isBooting) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {!session ? (
        <Stack.Screen name="Login" component={LoginScreen} />
      ) : locked ? (
        <Stack.Screen name="Lock" component={LockScreen} />
      ) : (
        <Stack.Screen name="AppTabs" component={AppTabs} />
      )}
    </Stack.Navigator>
  );
}
