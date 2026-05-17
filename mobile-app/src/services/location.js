import * as Location from "expo-location";

export async function getCurrentPosition() {
  const permission = await Location.requestForegroundPermissionsAsync();
  if (permission.status !== "granted") {
    throw new Error("Location permission is required.");
  }
  return Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
}
