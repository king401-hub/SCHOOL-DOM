import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { registerDevice } from "../api/endpoints";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications() {
  if (!Device.isDevice) return null;

  const existing = await Notifications.getPermissionsAsync();
  const finalPermission =
    existing.status === "granted" ? existing : await Notifications.requestPermissionsAsync();
  if (finalPermission.status !== "granted") return null;

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("schooldom-default", {
      name: "SchoolDom",
      importance: Notifications.AndroidImportance.MAX,
    });
  }

  const token = await Notifications.getExpoPushTokenAsync();
  await registerDevice({
    token: token.data,
    platform: Platform.OS,
    provider: "expo",
    device_name: Device.deviceName || Device.modelName || "SchoolDom device",
  });
  return token.data;
}
