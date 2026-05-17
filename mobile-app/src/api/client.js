import { API_BASE_URL } from "./config";
import { clearSession, getSession, saveSession } from "../storage/sessionStore";
import { readQueue, writeQueue } from "../storage/offlineQueue";

function parseApiError(data, fallback) {
  if (!data) return fallback;
  if (typeof data === "string") return data;
  if (data.message || data.detail || data.error) return data.message || data.detail || data.error;
  if (typeof data === "object") {
    const first = Object.entries(data)[0];
    if (first) return `${first[0]}: ${Array.isArray(first[1]) ? first[1][0] : first[1]}`;
  }
  return fallback;
}

async function refreshAccessToken(session) {
  const response = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: session.refresh }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data?.access) {
    await clearSession();
    throw new Error("Session expired. Please sign in again.");
  }
  const nextSession = {
    ...session,
    access: data.access,
    refresh: data.refresh || session.refresh,
    signedInAt: new Date().toISOString(),
  };
  await saveSession(nextSession);
  return nextSession;
}

export async function apiRequest(method, endpoint, payload = null, options = {}) {
  const { retry = true, queueWhenOffline = false } = options;
  let session = await getSession();
  const headers = {};
  if (session?.access) headers.Authorization = `Bearer ${session.access}`;

  const body = payload instanceof FormData ? payload : payload ? JSON.stringify(payload) : undefined;
  if (payload && !(payload instanceof FormData)) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, { method, headers, body });
  } catch (error) {
    if (queueWhenOffline && method !== "GET") {
      const queue = await readQueue();
      await writeQueue([...queue, { method, endpoint, payload, queuedAt: new Date().toISOString() }]);
      return { success: true, offline: true, message: "Saved offline and will sync when connected." };
    }
    throw new Error("Network error. Check your connection.");
  }

  const data = await response.json().catch(() => null);
  if (response.ok) return data || {};

  if (response.status === 401 && retry && session?.refresh) {
    session = await refreshAccessToken(session);
    return apiRequest(method, endpoint, payload, { ...options, retry: false, session });
  }

  throw new Error(parseApiError(data, `Request failed (${response.status}).`));
}

export function getJson(endpoint) {
  return apiRequest("GET", endpoint);
}

export function postJson(endpoint, payload, options) {
  return apiRequest("POST", endpoint, payload, options);
}

export function patchJson(endpoint, payload, options) {
  return apiRequest("PATCH", endpoint, payload, options);
}

export async function replayOfflineQueue() {
  const queue = await readQueue();
  if (!queue.length) return { synced: 0, remaining: 0 };

  const remaining = [];
  let synced = 0;
  for (const item of queue) {
    try {
      await apiRequest(item.method, item.endpoint, item.payload, { queueWhenOffline: false });
      synced += 1;
    } catch {
      remaining.push(item);
    }
  }
  await writeQueue(remaining);
  return { synced, remaining: remaining.length };
}
