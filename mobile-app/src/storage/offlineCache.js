import AsyncStorage from "@react-native-async-storage/async-storage";

const PREFIX = "schooldom.cache.";

function scopeKey(key, scope) {
  const normalized = String(scope || "anonymous").trim().toLowerCase();
  return `${PREFIX}${normalized}.${key}`;
}

export async function readCache(key, scope) {
  const raw = await AsyncStorage.getItem(scopeKey(key, scope));
  return raw ? JSON.parse(raw) : null;
}

export async function writeCache(key, data, scope) {
  await AsyncStorage.setItem(
    scopeKey(key, scope),
    JSON.stringify({
      data,
      cachedAt: new Date().toISOString(),
    })
  );
}
