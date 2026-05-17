import Constants from "expo-constants";

const configuredUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ||
  Constants.expoConfig?.extra?.apiBaseUrl ||
  "http://127.0.0.1:8000";

export const API_BASE_URL = configuredUrl.replace(/\/+$/, "");
