const axios = require("axios");
const { DEFAULT_CLOUD_URL } = require("./config.cjs");
const {
  getAdminSnapshot,
  getPendingSyncItems,
  getSetting,
  markSyncFailure,
  markSyncSuccess,
  saveSyncSnapshot,
  setSetting,
} = require("./db.cjs");

function normalizeCloudUrl(value) {
  const raw = String(value || DEFAULT_CLOUD_URL).trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(raw)) return `http://${raw}`;
  return raw;
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function syncFromCloud({ cloudUrl, accessToken, fallbackPin }) {
  const baseURL = normalizeCloudUrl(cloudUrl || getSetting("cloudUrl"));
  setSetting("cloudUrl", baseURL);
  const client = axios.create({
    baseURL,
    timeout: 20000,
    headers: authHeaders(accessToken),
  });
  const response = await client.get("/api/exams/cbt/offline-sync/");
  const data = response.data || {};
  const exams = (data.exams || data.published_exams || []).map((exam) => ({
    ...exam,
    pin: exam.pin || exam.exam_pin || exam.access_pin || fallbackPin || "",
  }));
  return saveSyncSnapshot({
    exams,
    students: data.students || [],
  });
}

async function pushPendingResults({ cloudUrl, accessToken }) {
  const baseURL = normalizeCloudUrl(cloudUrl || getSetting("cloudUrl"));
  const client = axios.create({
    baseURL,
    timeout: 20000,
    headers: authHeaders(accessToken),
  });
  const items = getPendingSyncItems();
  let synced = 0;
  const failures = [];
  for (const item of items) {
    try {
      await client.request({
        url: item.endpoint,
        method: item.method,
        data: item.payload,
      });
      markSyncSuccess(item.id, item.entity_id);
      synced += 1;
    } catch (error) {
      const message = error.response?.data?.message || error.response?.data?.detail || error.message || "Sync failed.";
      markSyncFailure(item.id, message);
      failures.push({ id: item.id, message });
    }
  }
  return { synced, failures, snapshot: getAdminSnapshot() };
}

async function cloudHealthCheck(cloudUrl) {
  const baseURL = normalizeCloudUrl(cloudUrl || getSetting("cloudUrl"));
  try {
    await axios.get(`${baseURL}/api/health/`, { timeout: 5000 });
    return { online: true, baseURL };
  } catch {
    return { online: false, baseURL };
  }
}

module.exports = {
  cloudHealthCheck,
  normalizeCloudUrl,
  pushPendingResults,
  syncFromCloud,
};
