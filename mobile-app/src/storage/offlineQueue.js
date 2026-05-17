import AsyncStorage from "@react-native-async-storage/async-storage";

const QUEUE_KEY = "schooldom.native.offline_queue";

export async function readQueue() {
  const raw = await AsyncStorage.getItem(QUEUE_KEY);
  return raw ? JSON.parse(raw) : [];
}

export async function writeQueue(items) {
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(items));
}
