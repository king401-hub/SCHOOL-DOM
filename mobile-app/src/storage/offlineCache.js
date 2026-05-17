import AsyncStorage from "@react-native-async-storage/async-storage";

const PREFIX = "schooldom.cache.";

export async function readCache(key) {
  const raw = await AsyncStorage.getItem(`${PREFIX}${key}`);
  return raw ? JSON.parse(raw) : null;
}

export async function writeCache(key, data) {
  await AsyncStorage.setItem(
    `${PREFIX}${key}`,
    JSON.stringify({
      data,
      cachedAt: new Date().toISOString(),
    })
  );
}
