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

function normalizeAccessToken(token) {
  const value = String(token || "").trim();
  return value.replace(/^Bearer\s+/i, "").trim();
}

function authHeaders(token) {
  const accessToken = normalizeAccessToken(token);
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

function requireAccessToken(accessToken) {
  if (!normalizeAccessToken(accessToken)) {
    throw new Error("Paste a valid admin JWT access token before syncing with SchoolDom cloud.");
  }
}

function cloudRequestError(error, action) {
  const status = error.response?.status;
  const responseMessage = error.response?.data?.message || error.response?.data?.detail;

  if (status === 401) {
    return new Error(`${action} failed: the JWT access token is missing, expired, invalid, or was copied incorrectly. Sign in to SchoolDom again, copy a fresh access token, and paste only the token value.`);
  }
  if (status === 403) {
    return new Error(`${action} failed: this user is signed in but does not have admin or teacher permission for CBT sync.`);
  }
  if (status) {
    return new Error(`${action} failed: SchoolDom cloud returned ${status}${responseMessage ? ` - ${responseMessage}` : ""}.`);
  }
  return new Error(`${action} failed: ${error.message || "Could not reach SchoolDom cloud."}`);
}

async function syncFromCloud({ cloudUrl, accessToken, fallbackPin }) {
  requireAccessToken(accessToken);
  const baseURL = normalizeCloudUrl(cloudUrl || getSetting("cloudUrl"));
  setSetting("cloudUrl", baseURL);
  const client = axios.create({
    baseURL,
    timeout: 20000,
    headers: authHeaders(accessToken),
  });
  let response;
  try {
    response = await client.get("/api/exams/cbt/offline-sync/");
  } catch (error) {
    throw cloudRequestError(error, "Cloud sync");
  }
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
  requireAccessToken(accessToken);
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
