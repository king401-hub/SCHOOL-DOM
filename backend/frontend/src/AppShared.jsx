import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Paperclip, Smile, Send, Check, CheckCheck, Trash2, Phone, Video, MoreVertical, Search, X as XIcon } from "lucide-react";
import {
  API_BASE_URL,
  LEGACY_SESSION_KEY,
  MESSAGE_POLL_INTERVAL_MS,
  SESSION_KEY,
  TEACHER_ATTENDANCE_PREFIX,
  UI_THEME_KEY,
} from "./appConstants";

export function MultiSelectBox({ options = [], selected = [], onChange, labelForOption, emptyText = "No options available." }) {
  const selectedSet = new Set((selected || []).map((item) => String(item)));
  const toggleOption = (value) => {
    const normalized = String(value);
    const next = new Set(selectedSet);
    if (next.has(normalized)) {
      next.delete(normalized);
    } else {
      next.add(normalized);
    }
    onChange?.(Array.from(next));
  };

  if (!options.length) {
    return <p className="panel-empty compact">{emptyText}</p>;
  }

  return (
    <div className="multi-select-box">
      {options.map((item) => {
        const value = String(item.id);
        const checked = selectedSet.has(value);
        return (
          <label key={value} className={`multi-select-option ${checked ? "checked" : ""}`}>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggleOption(value)}
            />
            <span>{labelForOption ? labelForOption(item) : item.label || item.name}</span>
          </label>
        );
      })}
    </div>
  );
}

export function normalizePath(pathname) {
  if (!pathname || pathname === "/") {
    return "/";
  }
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

export function isTeacherAttendanceScanPath(pathname) {
  return normalizePath(pathname).startsWith(TEACHER_ATTENDANCE_PREFIX);
}

export function isStudentExamPath(pathname) {
  const normalized = normalizePath(pathname);
  return /^\/exam\/\d+$/.test(normalized) || /^\/exam-result\/\d+$/.test(normalized);
}

export function getTeacherAttendanceToken(pathname) {
  const normalized = normalizePath(pathname);
  if (!normalized.startsWith(TEACHER_ATTENDANCE_PREFIX)) {
    return "";
  }
  return decodeURIComponent(normalized.slice(TEACHER_ATTENDANCE_PREFIX.length));
}

export function readStoredSession() {
  const raw =
    window.localStorage.getItem(SESSION_KEY) ||
    window.sessionStorage.getItem(SESSION_KEY) ||
    window.localStorage.getItem(LEGACY_SESSION_KEY) ||
    window.sessionStorage.getItem(LEGACY_SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    window.localStorage.removeItem(SESSION_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    return null;
  }
}

export function clearStoredSession() {
  window.localStorage.removeItem(SESSION_KEY);
  window.sessionStorage.removeItem(SESSION_KEY);
  window.localStorage.removeItem(LEGACY_SESSION_KEY);
  window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("refresh_token");
}

export function writeStoredSession(session) {
  if (!session) {
    clearStoredSession();
    return;
  }

  const serialized = JSON.stringify(session);
  const hasLocal =
    window.localStorage.getItem(SESSION_KEY) !== null ||
    window.localStorage.getItem(LEGACY_SESSION_KEY) !== null;
  const hasSession =
    window.sessionStorage.getItem(SESSION_KEY) !== null ||
    window.sessionStorage.getItem(LEGACY_SESSION_KEY) !== null;

  if (hasLocal && !hasSession) {
    window.localStorage.setItem(SESSION_KEY, serialized);
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    return;
  }

  if (hasSession && !hasLocal) {
    window.sessionStorage.setItem(SESSION_KEY, serialized);
    window.localStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    return;
  }

  if (hasLocal && hasSession) {
    window.localStorage.setItem(SESSION_KEY, serialized);
    window.sessionStorage.setItem(SESSION_KEY, serialized);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    return;
  }

  // Fallback to localStorage when we cannot infer preference.
  window.localStorage.setItem(SESSION_KEY, serialized);
}

export function readStoredTheme() {
  const raw = (window.localStorage.getItem(UI_THEME_KEY) || "").toLowerCase();
  if (raw === "dark" || raw === "light") {
    return raw;
  }
  return "light";
}

export async function refreshAccessToken(session) {
  if (!session?.refresh) {
    const error = new Error("Session expired. Please sign in again.");
    error.status = 401;
    error.statusCode = 401;
    error.authExpired = true;
    throw error;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: session.refresh }),
    });
  } catch (networkError) {
    throw new Error("Unable to refresh session. Check your connection.");
  }

  const data = await response.json().catch(() => null);
  if (!response?.ok || !data?.access) {
    clearStoredSession();
    const error = new Error(data?.message || "Session expired. Please sign in again.");
    error.status = response?.status || 401;
    error.statusCode = response?.status || 401;
    error.authExpired = true;
    throw error;
  }

  session.access = data.access;
  if (data.refresh) {
    session.refresh = data.refresh;
  }
  session.signedInAt = new Date().toISOString();
  writeStoredSession(session);
  return session.access;
}

export function isFileLike(value) {
  if (typeof File !== "undefined" && value instanceof File) {
    return true;
  }
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return true;
  }
  return false;
}

export function payloadContainsFile(value) {
  if (isFileLike(value)) {
    return true;
  }
  if (Array.isArray(value)) {
    return value.some(payloadContainsFile);
  }
  if (value && typeof value === "object") {
    return Object.values(value).some(payloadContainsFile);
  }
  return false;
}

export function buildFormData(payload) {
  const formData = new FormData();
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => formData.append(key, item));
      return;
    }
    formData.append(key, value);
  });
  return formData;
}

export function formatApiError(data, fallback) {
  if (!data) {
    return fallback;
  }
  if (typeof data === "string") {
    return data;
  }
  if (data.message || data.detail) {
    return data.message || data.detail;
  }
  if (Array.isArray(data)) {
    return data.map((item) => formatApiError(item, "")).filter(Boolean).join(" ");
  }
  if (typeof data === "object") {
    const messages = Object.entries(data).flatMap(([field, value]) => {
      const text = formatApiError(value, "");
      if (!text) return [];
      return field === "non_field_errors" ? [text] : [`${field}: ${text}`];
    });
    return messages.join(" ");
  }
  return fallback;
}

export const SCHOOL_DATA_MUTATED_EVENT = "schooldom:data-mutated";

const _inFlightMutations = new Set();

export function emitSchoolDomDataMutation(detail = {}) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(
    new CustomEvent(SCHOOL_DATA_MUTATED_EVENT, {
      detail: {
        changed_at: new Date().toISOString(),
        ...detail,
      },
    })
  );
}

export async function requestJson(session, method, endpoint, payload = null, options = {}) {
  const { retryOnAuthFailure = true, skipDuplicateCheck = false } = options;

  const isMutation = !["GET", "HEAD", "OPTIONS"].includes(String(method || "").toUpperCase());
  const mutationKey = (isMutation && !skipDuplicateCheck) ? `${method}:${endpoint}` : null;

  if (mutationKey && _inFlightMutations.has(mutationKey)) {
    const err = new Error("Please wait — a request is already in progress.");
    err.status = 429;
    err.isDuplicate = true;
    throw err;
  }
  if (mutationKey) _inFlightMutations.add(mutationKey);

  try {
    const headers = {};
    if (session?.access) {
      headers.Authorization = `Bearer ${session.access}`;
    } else {
      const error = new Error("Session expired. Please sign in again.");
      error.status = 401;
      error.statusCode = 401;
      error.authExpired = true;
      clearStoredSession();
      throw error;
    }

    const shouldSendFormData = payload !== null && (payload instanceof FormData || payloadContainsFile(payload));
    const body =
      payload === null
        ? undefined
        : payload instanceof FormData
          ? payload
          : shouldSendFormData
            ? buildFormData(payload)
            : JSON.stringify(payload);

    if (payload !== null && !shouldSendFormData && !(payload instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    let response;
    try {
      response = await fetch(`${API_BASE_URL}${endpoint}`, { method, headers, body });
    } catch (networkError) {
      throw new Error("Network error. Please check your connection.");
    }

    const data = await response.json().catch(() => null);
    if (response?.ok) {
      if (isMutation) emitSchoolDomDataMutation({ endpoint, method });
      return data ?? {};
    }

    if (response?.status === 401 && retryOnAuthFailure) {
      try {
        await refreshAccessToken(session);
        return requestJson(session, method, endpoint, payload, {
          ...options,
          retryOnAuthFailure: false,
          skipDuplicateCheck: true,
        });
      } catch (refreshError) {
        clearStoredSession();
        throw refreshError;
      }
    }

    if (response?.status === 413) {
      const error = new Error("The selected file is too large for the server upload limit. Try a smaller image or increase MAX_UPLOAD_SIZE on the server.");
      error.status = response.status;
      error.statusCode = response.status;
      throw error;
    }

    const error = new Error(formatApiError(data, `Request failed (${response?.status || "network"}).`));
    error.status = response?.status;
    error.statusCode = response?.status;
    throw error;
  } finally {
    if (mutationKey) _inFlightMutations.delete(mutationKey);
  }
}

export async function fetchDashboardSnapshot(session) {
  const role = session?.user?.role;
  const endpoint =
    role === "student"
      ? "/api/app/student/dashboard/"
      : role === "teacher"
        ? "/api/app/teacher/dashboard/"
        : role === "staff"
          ? "/api/hr/me/"
          : role === "parent"
            ? "/api/finance/parent/dashboard/"
            : "/api/app/dashboard/";
  return requestJson(session, "GET", endpoint);
}

export async function postJson(session, endpoint, body) {
  return requestJson(session, "POST", endpoint, body);
}

export async function copyToClipboard(value) {
  const text = String(value || "");
  if (!text) {
    return false;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "0";
  textarea.style.top = "0";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, text.length);
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  } finally {
    document.body.removeChild(textarea);
  }
  if (copied) {
    return true;
  }

  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}

export function formatDate(value) {
  if (!value) {
    return "-";
  }
  try {
    return new Date(value).toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return String(value);
  }
}

export function userDisplayName(user) {
  if (!user) {
    return "User";
  }
  return user.full_name || [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email || "User";
}

export function userInitials(user) {
  const name = userDisplayName(user);
  const parts = name.split(" ").filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

export function resolveSchoolBrand(...sources) {
  const school = sources.find((item) => item && Object.keys(item).length) || {};
  const name =
    school.name ||
    school.school_name ||
    school.schoolName ||
    school.school ||
    school.institution_name ||
    school.institutionName ||
    school.tenant?.name ||
    school.user?.school_name ||
    school.user?.schoolName ||
    school.user?.school?.name ||
    school.user?.tenant?.name ||
    "SchoolDom";
  return {
    name,
    code: school.school_code || school.schoolCode || school.tenant?.schema_name || school.user?.school_code || school.user?.schoolCode || school.user?.tenant?.schema_name || "",
    logo: school.logo || school.logo_url || school.logoUrl || school.school_logo || school.schoolLogo || school.logo_path || school.user?.school_logo || school.user?.schoolLogo || "",
    motto: school.motto || school.tagline || school.school_motto || school.schoolMotto || school.school_tagline || school.schoolTagline || school.user?.motto || school.user?.tagline || "",
    address: school.address || school.school_address || school.schoolAddress || school.user?.school_address || school.user?.schoolAddress || "",
    phone: school.phone || school.phone_number || school.phoneNumber || school.school_phone || school.schoolPhone || school.user?.school_phone || school.user?.schoolPhone || "",
    email: school.email || school.school_email || school.schoolEmail || school.user?.school_email || school.user?.schoolEmail || "",
    school_type: school.school_type || school.schoolType || school.type || school.user?.school_type || school.user?.schoolType || "k12",
    initials: name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "SD",
  };
}

export function academicGroupLabels(...sources) {
  const brand = resolveSchoolBrand(...sources);
  const isNonK12 = String(brand.school_type || "k12").toLowerCase() === "non_k12";
  return isNonK12
    ? {
        singular: "Department / Faculty",
        plural: "Departments & Faculties",
        shortPlural: "Departments",
        select: "Select department / faculty",
        unassigned: "Unassigned department",
        fee: "Department / Faculty Fee",
        feePlural: "Department / Faculty Fees",
      }
    : {
        singular: "Class",
        plural: "Classes",
        shortPlural: "Classes",
        select: "Select class",
        unassigned: "Unassigned",
        fee: "Class Fee",
        feePlural: "Class Fees",
      };
}

export function SchoolBrand({ school, subtitle = "", compact = false }) {
  const brand = resolveSchoolBrand(school);
  return (
    <div className={`school-brand ${compact ? "compact" : ""}`}>
      <div className="school-brand-logo">
        {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
      </div>
      <div>
        <div className="brand-title-primary">{brand.name}</div>
        {subtitle ? <div className="brand-sub">{subtitle}</div> : null}
        {brand.motto ? <div className="brand-motto">{brand.motto}</div> : null}
      </div>
    </div>
  );
}

export function roleLabel(role) {
  if (!role) {
    return "Member";
  }
  return role
    .split("_")
    .map((chunk) => chunk[0].toUpperCase() + chunk.slice(1))
    .join(" ");
}

export function userRoleLabel(user) {
  if (!user) {
    return "Member";
  }
  return user.display_role || user.admin_title || user.adminTitle || roleLabel(user.role);
}

export function BellIcon({ className = "" }) {
    return (
      <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 18h5l-1.4-1.9a2 2 0 0 1-.4-1.2V11a6.2 6.2 0 0 0-12.4 0v3.9a2 2 0 0 1-.4 1.2L4 18h5" />
      <path d="M9.6 18a2.4 2.4 0 0 0 4.8 0" />
    </svg>
  );
}

export function FilterIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16l-6.3 7.4v4.8l-3.4 1.8v-6.6L4 6z" />
    </svg>
  );
}

export function PaintbrushIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M18.7 3.3a2.2 2.2 0 0 1 3.1 3.1l-8.9 8.9-3.1-3.1 8.9-8.9Z" />
      <path d="M8.7 13.3c-1.6.3-2.7 1.3-3.1 2.9-.2.9-.7 1.6-1.5 2.1 2.1.7 5.4.7 6.8-1.3.7-1 .7-2.3-.1-3.1l-2.1-.6Z" />
    </svg>
  );
}

export function ThemeModeIcon({ mode = "dark", className = "" }) {
  if (mode === "light") {
    return (
      <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4.5" />
        <path d="M12 2v3" />
        <path d="M12 19v3" />
        <path d="M2 12h3" />
        <path d="M19 12h3" />
        <path d="M4.9 4.9l2.1 2.1" />
        <path d="M17 17l2.1 2.1" />
        <path d="M19.1 4.9L17 7" />
        <path d="M7 17l-2.1 2.1" />
      </svg>
    );
  }

  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />
    </svg>
  );
}

export function DashboardIcon({ name = "overview", className = "" }) {
  const paths = {
    overview: [
      <path key="1" d="M4 13h6V4H4v9Z" />,
      <path key="2" d="M14 20h6V4h-6v16Z" />,
      <path key="3" d="M4 20h6v-3H4v3Z" />,
    ],
    home: [
      <path key="1" d="M3 11.5 12 4l9 7.5" />,
      <path key="2" d="M5.5 10.5V20h13v-9.5" />,
      <path key="3" d="M9.5 20v-6h5v6" />,
    ],
    exam: [
      <path key="1" d="M7 4h10l2 2v14H5V4h2Z" />,
      <path key="2" d="M8 9h8" />,
      <path key="3" d="M8 13h6" />,
      <path key="4" d="M8 17h4" />,
    ],
    calendar: [
      <path key="1" d="M5 5h14v15H5V5Z" />,
      <path key="2" d="M8 3v4" />,
      <path key="3" d="M16 3v4" />,
      <path key="4" d="M5 10h14" />,
    ],
    attendance: [
      <path key="1" d="M9 12l2 2 4-5" />,
      <path key="2" d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />,
    ],
    planning: [
      <path key="1" d="M5 4h14v16H5V4Z" />,
      <path key="2" d="M8 8h8" />,
      <path key="3" d="M8 12h8" />,
      <path key="4" d="M8 16h5" />,
    ],
    message: [
      <path key="1" d="M4 6h16v12H4V6Z" />,
      <path key="2" d="m4 7 8 6 8-6" />,
    ],
    results: [
      <path key="1" d="M5 19V9" />,
      <path key="2" d="M12 19V5" />,
      <path key="3" d="M19 19v-7" />,
      <path key="4" d="M4 19h16" />,
    ],
    requests: [
      <path key="1" d="M7 4h10v16H7V4Z" />,
      <path key="2" d="M9 9h6" />,
      <path key="3" d="M9 13h4" />,
      <path key="4" d="M16 18l3 3" />,
    ],
    money: [
      <path key="1" d="M12 3v18" />,
      <path key="2" d="M17 7.5c-.8-1.1-2.2-1.8-4-1.8-2.2 0-4 .9-4 2.8 0 4.5 8 1.6 8 6 0 1.9-1.8 2.8-4 2.8-2 0-3.6-.8-4.5-2.2" />,
    ],
    id: [
      <path key="1" d="M4 6h16v12H4V6Z" />,
      <path key="2" d="M8 10h4" />,
      <path key="3" d="M8 14h8" />,
      <path key="4" d="M15 10h1" />,
    ],
  };

  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] || paths.overview}
    </svg>
  );
}

export function MetricCard({ label, value, trend, trendUp, icon = "overview", tone = "blue" }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-card-head">
        <span className={`metric-icon metric-icon-${tone}`}>
          <DashboardIcon name={icon} className="inline-icon" />
        </span>
        <p className="metric-label">{label}</p>
      </div>
      <p className="metric-value">{value ?? "—"}</p>
      {trend ? (
        <p className={`metric-trend${trendUp === false ? " metric-trend-down" : ""}`}>
          {trendUp === true ? "↑ " : trendUp === false ? "↓ " : ""}{trend}
        </p>
      ) : null}
    </article>
  );
}

export function ScreenState({ loading, error, onRetry }) {
  if (loading) {
    return (
      <div className="screen-grid">
        <div className="skeleton-card" aria-busy="true" aria-label="Loading…">
          <div className="skeleton-line skeleton-line-short" />
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-line-medium" />
        </div>
        <div className="metric-grid">
          {[0,1,2,3].map((i) => (
            <div key={i} className="skeleton-card skeleton-metric" aria-hidden="true">
              <div className="skeleton-line skeleton-line-short" />
              <div className="skeleton-line skeleton-line-value" />
            </div>
          ))}
        </div>
        <div className="skeleton-card skeleton-tall" aria-hidden="true">
          <div className="skeleton-line skeleton-line-short" />
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-line-medium" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  if (!error) {
    return null;
  }

  return (
    <div className="screen-grid">
      <article className="app-panel state-panel state-panel-error">
        <div className="state-panel-icon">⚠</div>
        <h3>Something went wrong</h3>
        <p>{error}</p>
        {onRetry ? (
          <div className="panel-form-actions">
            <button type="button" className="btn-primary" onClick={onRetry}>
              Try again
            </button>
          </div>
        ) : null}
      </article>
    </div>
  );
}

export const OFFLINE_DRAFTS_KEY = "schooldom.offline_exam_drafts";
export const OFFLINE_EXAM_CREATE_QUEUE_KEY = "schooldom.offline_exam_create_queue";
export const LOCAL_SENT_MESSAGES_KEY = "schooldom.local_sent_messages";

export function readOfflineDrafts() {
  if (typeof window === "undefined") {
    return {};
  }
  const raw = window.localStorage.getItem(OFFLINE_DRAFTS_KEY);
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    window.localStorage.removeItem(OFFLINE_DRAFTS_KEY);
    return {};
  }
}

export function writeOfflineDrafts(payload) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(payload));
  emitSchoolDomDataMutation({ source: "offline-exam-draft", action: "drafts-updated" });
}

export function readOfflineExamCreateQueue() {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(OFFLINE_EXAM_CREATE_QUEUE_KEY) || "[]");
  } catch {
    window.localStorage.removeItem(OFFLINE_EXAM_CREATE_QUEUE_KEY);
    return [];
  }
}

export function writeOfflineExamCreateQueue(payload) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(OFFLINE_EXAM_CREATE_QUEUE_KEY, JSON.stringify(payload));
  emitSchoolDomDataMutation({ source: "offline-exam-create", action: "queue-updated" });
}

export function queueOfflineExamCreate(payload) {
  const queue = readOfflineExamCreateQueue();
  queue.push({ id: `exam-draft-${Date.now()}`, payload, queued_at: new Date().toISOString() });
  writeOfflineExamCreateQueue(queue);
}

function localSentMessagesKey(scope = "") {
  const normalized = String(scope || "").trim();
  return normalized ? `${LOCAL_SENT_MESSAGES_KEY}.${normalized}` : LOCAL_SENT_MESSAGES_KEY;
}

function readLocalSentMessages(scope = "") {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(localSentMessagesKey(scope)) || "[]");
  } catch {
    window.localStorage.removeItem(localSentMessagesKey(scope));
    return [];
  }
}

function writeLocalSentMessages(messages, scope = "") {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(localSentMessagesKey(scope), JSON.stringify(messages.slice(0, 200)));
}

function messageSubject(message = {}) {
  return message.subject || message.title || "";
}

function messageBody(message = {}) {
  return message.body || message.message || message.content || message.text || message.response_text || "";
}

function messageAttachments(message = {}) {
  return Array.isArray(message.attachments) ? message.attachments : [];
}

function attachmentLabel(file) {
  if (!file) return "";
  return file.name || file.filename || file.url || "Attachment";
}

function attachmentUrl(file) {
  return file?.url || file?.preview_url || file?.previewUrl || "";
}

function isImageAttachment(file) {
  const contentType = String(file?.content_type || file?.contentType || file?.type || "").toLowerCase();
  const label = attachmentLabel(file).toLowerCase();
  const url = attachmentUrl(file).toLowerCase().split("?")[0];
  return contentType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(label) || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(url);
}

function MessageAttachment({ attachment, index }) {
  const url = attachmentUrl(attachment);
  const label = attachmentLabel(attachment);
  const key = `${url || label}-${index}`;

  if (url && isImageAttachment(attachment)) {
    return (
      <a key={key} className="message-image-attachment" href={url} target="_blank" rel="noreferrer" aria-label={`Open ${label}`}>
        <img src={url} alt={label} />
        <span>{label}</span>
      </a>
    );
  }

  if (url) {
    return (
      <a key={key} href={url} target="_blank" rel="noreferrer">
        {label}
      </a>
    );
  }

  return <span key={key}>{label}</span>;
}

function LegacyMessageInboxPanel({
  title = "Inbox",
  messages = [],
  recipientOptions = [],
  onComposeSubmit,
  onMarkRead,
  onDelete,
}) {
  const [filter, setFilter] = useState("all");
  const [activeMessageId, setActiveMessageId] = useState("");
  const [composeForm, setComposeForm] = useState({ recipient: "", subject: "", body: "" });
  const [composeFeedback, setComposeFeedback] = useState("");
  const [composeError, setComposeError] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [actionBusyId, setActionBusyId] = useState("");

  useEffect(() => {
    if (recipientOptions.length === 0) {
      setComposeForm((previous) => ({ ...previous, recipient: "" }));
      return;
    }
    setComposeForm((previous) => {
      if (recipientOptions.some((option) => option.value === previous.recipient)) {
        return previous;
      }
      return { ...previous, recipient: recipientOptions[0].value };
    });
  }, [recipientOptions]);

  useEffect(() => {
    if (messages.length === 0) {
      setActiveMessageId("");
      return;
    }
    if (!activeMessageId || !messages.some((item) => item.id === activeMessageId)) {
      setActiveMessageId(messages[0].id);
    }
  }, [messages, activeMessageId]);

  const filteredMessages = useMemo(() => {
    if (filter === "all") {
      return messages;
    }
    return messages.filter((item) => !item.is_read);
  }, [filter, messages]);

  const selectedRecipient = recipientOptions.find((option) => option.value === composeForm.recipient);

  const handleComposeSubmit = async (event) => {
    event.preventDefault();
    if (!onComposeSubmit) {
      return;
    }
    if (!composeForm.recipient) {
      setComposeError("Select a recipient before sending.");
      return;
    }
    if (!composeForm.body.trim()) {
      setComposeError("Add a message before sending.");
      return;
    }
    setComposeError("");
    setComposeFeedback("");
    setIsComposing(true);
    try {
      await onComposeSubmit(composeForm.recipient, composeForm.subject.trim(), composeForm.body.trim(), selectedRecipient);
      setComposeFeedback("Message sent.");
      setComposeForm((prev) => ({ ...prev, subject: "", body: "" }));
    } catch (submissionError) {
      setComposeError(submissionError.message || "Could not send message.");
    } finally {
      setIsComposing(false);
    }
  };

  const handleMarkRead = async (messageId) => {
    if (!onMarkRead) {
      return;
    }
    setActionBusyId(`read:${messageId}`);
    try {
      await onMarkRead(messageId);
    } finally {
      setActionBusyId("");
    }
  };

  const handleDelete = async (messageId) => {
    if (!onDelete) {
      return;
    }
    setActionBusyId(`delete:${messageId}`);
    try {
      await onDelete(messageId);
      if (activeMessageId === messageId) {
        setActiveMessageId("");
      }
    } finally {
      setActionBusyId("");
    }
  };

  return (
    <article className="app-panel inbox-panel">
      <h3>{title}</h3>
      <div className="segmented-control inbox-filter">
        <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
          All ({messages.length})
        </button>
        <button type="button" className={filter === "unread" ? "active" : ""} onClick={() => setFilter("unread")}>
          Unread ({messages.filter((item) => !item.is_read).length})
        </button>
      </div>
    {filteredMessages.length === 0 ? (
        <p className="panel-empty">No messages found.</p>
      ) : (
        <div className="message-stack">
          {filteredMessages.map((item) => (
            <div key={item.id} className={`message-item ${item.is_read ? "" : "unread"}`}>
              <div className="message-head">
                <p>{item.subject || item.body || "Message"}</p>
                <small>{formatDate(item.created_at)}</small>
              </div>
              <span className="message-meta">
                From: {item.from || item.from_name || "Unknown sender"} • {item.is_read ? "Read" : "Unread"}
              </span>
              {activeMessageId === item.id ? (
                <>
                  <p className="message-body">{item.body || "No content provided."}</p>
                  {messageAttachments(item).length ? (
                    <div className="message-attachment-list">
                      {messageAttachments(item).map((attachment, index) => (
                        <MessageAttachment key={`${attachmentUrl(attachment) || attachmentLabel(attachment)}-${index}`} attachment={attachment} index={index} />
                      ))}
                    </div>
                  ) : null}
                </>
              ) : null}
              <div className="table-actions-inline">
                <button
                  type="button"
                  className="table-action"
                  onClick={() => setActiveMessageId(activeMessageId === item.id ? "" : item.id)}
                >
                  {activeMessageId === item.id ? "Hide" : "View"}
                </button>
                {!item.is_read ? (
                  <button
                    type="button"
                    className="table-action"
                    disabled={actionBusyId === `read:${item.id}` || actionBusyId === `delete:${item.id}`}
                    onClick={() => handleMarkRead(item.id)}
                  >
                    {actionBusyId === `read:${item.id}` ? "Marking..." : "Mark read"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="table-action danger"
                  disabled={actionBusyId === `read:${item.id}` || actionBusyId === `delete:${item.id}`}
                  onClick={() => handleDelete(item.id)}
                >
                  {actionBusyId === `delete:${item.id}` ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {onComposeSubmit ? (
        <form className="panel-form" onSubmit={handleComposeSubmit}>
          <div className="panel-form-grid">
            <label className="panel-field">
              Recipient
              <select
                value={composeForm.recipient}
                onChange={(event) => setComposeForm((prev) => ({ ...prev, recipient: event.target.value }))}
              >
                {recipientOptions.length === 0 ? (
                  <option value="">No recipients</option>
                ) : (
                  recipientOptions.map((recipient) => (
                    <option key={recipient.value} value={recipient.value}>
                      {recipient.label}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="panel-field">
              Subject
              <input
                value={composeForm.subject}
                onChange={(event) => setComposeForm((prev) => ({ ...prev, subject: event.target.value }))}
                placeholder="Optional subject"
              />
            </label>
            <label className="panel-field full">
              Message
              <textarea
                value={composeForm.body}
                onChange={(event) => setComposeForm((prev) => ({ ...prev, body: event.target.value }))}
                placeholder="Write your message"
              />
            </label>
          </div>
          {composeError ? <p className="form-feedback error">{composeError}</p> : null}
          {composeFeedback ? <p className="form-feedback success">{composeFeedback}</p> : null}
          <div className="panel-form-actions">
            <button type="submit" disabled={recipientOptions.length === 0 || isComposing}>
              {isComposing ? "Sending..." : "Send message"}
            </button>
          </div>
        </form>
      ) : null}
    </article>
  );
}

const CHAT_EMOJIS = [
  "😀","😂","😍","🥰","😊","😎","😢","😅","🤔","😮","😴","🤩","🥳","😤","🤗",
  "👍","👎","👏","🙌","🤝","✌️","👋","💪","🙏","❤️","💙","💚","💛","🧡","💜",
  "🎉","🎊","🎁","🏆","⭐","🌟","💡","📚","📖","✅","❌","⚠️","🔥","💯","🚀",
  "😡","😭","😱","🤯","😬","🥺","😏","😇","🤭","😶","😪","🤤","😠","😈","👀",
];

export function MessageInboxPanel({
  title = "Messages",
  messages = [],
  recipientOptions = [],
  sessionScope = "",
  onComposeSubmit,
  onMarkRead,
  onDelete,
  onRefresh,
  refreshIntervalMs = MESSAGE_POLL_INTERVAL_MS,
}) {
  const [filter, setFilter] = useState("all");
  const [activeThreadKey, setActiveThreadKey] = useState("");
  const [composeForm, setComposeForm] = useState({ recipient: "", subject: "", body: "" });
  const [searchTerm, setSearchTerm] = useState("");
  const [composeFeedback, setComposeFeedback] = useState("");
  const [composeError, setComposeError] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [actionBusyId, setActionBusyId] = useState("");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const localMessageScope = String(sessionScope || "default");
  const [localSentMessages, setLocalSentMessages] = useState(() => readLocalSentMessages(localMessageScope));
  const [composeAttachments, setComposeAttachments] = useState([]);
  const attachmentInputRef = useRef(null);
  const emojiPickerRef = useRef(null);
  const textareaRef = useRef(null);
  const chatBodyRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (emojiPickerRef.current && !emojiPickerRef.current.contains(e.target)) {
        setShowEmojiPicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const insertEmoji = (emoji) => {
    const el = textareaRef.current;
    if (!el) { setComposeForm((p) => ({ ...p, body: p.body + emoji })); return; }
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const newBody = composeForm.body.slice(0, start) + emoji + composeForm.body.slice(end);
    setComposeForm((p) => ({ ...p, body: newBody }));
    setTimeout(() => { el.focus(); el.setSelectionRange(start + emoji.length, start + emoji.length); }, 0);
    setShowEmojiPicker(false);
  };

  useEffect(() => {
    setLocalSentMessages(readLocalSentMessages(localMessageScope));
  }, [localMessageScope]);

  useEffect(() => {
    if (!onRefresh || !refreshIntervalMs) return undefined;
    const pollId = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        Promise.resolve(onRefresh()).catch(() => {});
      }
    }, refreshIntervalMs);
    return () => window.clearInterval(pollId);
  }, [onRefresh, refreshIntervalMs]);

  useEffect(() => {
    if (recipientOptions.length === 0) {
      setComposeForm((previous) => ({ ...previous, recipient: "" }));
      return;
    }
    setComposeForm((previous) => {
      if (recipientOptions.some((option) => option.value === previous.recipient)) return previous;
      return { ...previous, recipient: recipientOptions[0].value };
    });
  }, [recipientOptions]);

  useEffect(() => {
    if (!activeThreadKey && recipientOptions[0]?.value) {
      setActiveThreadKey(`contact:${recipientOptions[0].value}`);
    }
  }, [activeThreadKey, recipientOptions]);

  const conversationThreads = useMemo(() => {
    const threadMap = new Map();
    const allowedContactEmails = new Set(recipientOptions.map((contact) => String(contact.value || "").toLowerCase()).filter(Boolean));
    const upsertThread = (key, seed = {}) => {
      if (!threadMap.has(key)) {
        threadMap.set(key, {
          key,
          name: seed.name || "Conversation",
          email: seed.email || "",
          role: seed.role || "Contact",
          messages: [],
          unread: 0,
          latestAt: "",
          preview: "",
          contactOnly: Boolean(seed.contactOnly),
        });
      }
      return threadMap.get(key);
    };

    recipientOptions.forEach((contact) => {
      upsertThread(`contact:${contact.value}`, {
        name: contact.name || String(contact.label || contact.value).split(" - ")[0],
        email: contact.value,
        role: contact.role || String(contact.label || "Contact").split(" - ").slice(1).join(" - ") || "Contact",
        contactOnly: true,
      });
    });

    [
      ...messages,
      ...localSentMessages.filter((message) => {
        const email = String(message.to_email || message.from_email || message.sender_email || "").toLowerCase();
        return !email || allowedContactEmails.has(email);
      }),
    ].forEach((message) => {
      const isOutgoing = message.direction === "outgoing";
      const email = isOutgoing ? message.to_email || "" : message.from_email || message.sender_email || "";
      const key = email ? `contact:${email}` : `sender:${message.from || message.from_name || message.id}`;
      const thread = upsertThread(key, {
        name: isOutgoing ? message.to_name || email || "Recipient" : message.from || message.from_name || email || "Unknown sender",
        email,
        role: message.from_role || "Contact",
      });
      thread.contactOnly = false;
      thread.messages.push(message);
      thread.unread += isOutgoing || message.is_read ? 0 : 1;
      const createdAt = message.created_at || message.sent_at || "";
      if (!thread.latestAt || new Date(createdAt || 0) > new Date(thread.latestAt || 0)) {
        thread.latestAt = createdAt;
        thread.preview = messageSubject(message) || messageBody(message) || (messageAttachments(message).length ? "Attachment" : "");
      }
    });

    return Array.from(threadMap.values())
      .map((thread) => ({
        ...thread,
        messages: thread.messages.sort((a, b) => new Date(a.created_at || a.sent_at || 0) - new Date(b.created_at || b.sent_at || 0)),
      }))
      .sort((a, b) => new Date(b.latestAt || 0) - new Date(a.latestAt || 0));
  }, [localSentMessages, messages, recipientOptions]);

  useEffect(() => {
    if (conversationThreads.length === 0) {
      setActiveThreadKey("");
      return;
    }
    if (!activeThreadKey || !conversationThreads.some((item) => item.key === activeThreadKey)) {
      setActiveThreadKey(conversationThreads[0].key);
    }
  }, [activeThreadKey, conversationThreads]);

  const filteredThreads = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return conversationThreads.filter((thread) => {
      const matchesFilter = filter === "all" || thread.unread > 0;
      const haystack = `${thread.name} ${thread.email} ${thread.role} ${thread.preview} ${thread.messages.map((item) => `${messageSubject(item)} ${messageBody(item)}`).join(" ")}`.toLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
  }, [conversationThreads, filter, searchTerm]);

  const activeThread = conversationThreads.find((item) => item.key === activeThreadKey) || filteredThreads[0] || null;

  useEffect(() => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
  }, [activeThread?.messages?.length, activeThreadKey]);

  const selectedRecipient = recipientOptions.find((option) => option.value === composeForm.recipient);
  const composerRecipientOptions = useMemo(() => {
    if (!activeThread?.email || recipientOptions.some((option) => option.value === activeThread.email)) {
      return recipientOptions;
    }
    return [
      { value: activeThread.email, label: `${activeThread.name} - ${activeThread.role || "Contact"}` },
      ...recipientOptions,
    ];
  }, [activeThread, recipientOptions]);
  const composerRecipient = composerRecipientOptions.find((option) => option.value === composeForm.recipient);

  const handleComposeSubmit = async (event) => {
    event.preventDefault();
    if (!onComposeSubmit) return;
    if (!composeForm.recipient) {
      setComposeError("Select a recipient before sending.");
      return;
    }
    if (!composeForm.body.trim() && composeAttachments.length === 0) {
      setComposeError("Add a message or attachment before sending.");
      return;
    }
    setComposeError("");
    setComposeFeedback("");
    setIsComposing(true);
    try {
      await onComposeSubmit(composeForm.recipient, composeForm.subject.trim(), composeForm.body.trim(), selectedRecipient, composeAttachments);
      const sentMessage = {
        id: `local-sent-${Date.now()}`,
        direction: "outgoing",
        local: true,
        local_scope: localMessageScope,
        to_email: composeForm.recipient,
        to_name: selectedRecipient?.label || composerRecipient?.label || composeForm.recipient,
        from: "You",
        subject: composeForm.subject.trim(),
        body: composeForm.body.trim(),
        attachments: composeAttachments.map((file) => ({
          name: file.name,
          size: file.size,
          content_type: file.type,
          preview_url: file.type?.startsWith("image/") ? URL.createObjectURL(file) : "",
        })),
        created_at: new Date().toISOString(),
        is_read: true,
      };
      setLocalSentMessages((previous) => {
        const next = [sentMessage, ...previous].slice(0, 200);
        writeLocalSentMessages(next, localMessageScope);
        return next;
      });
      setComposeFeedback("Message sent.");
      setComposeForm((prev) => ({ ...prev, subject: "", body: "" }));
      setComposeAttachments([]);
      if (attachmentInputRef.current) {
        attachmentInputRef.current.value = "";
      }
      await onRefresh?.();
    } catch (submissionError) {
      setComposeError(submissionError.message || "Could not send message.");
    } finally {
      setIsComposing(false);
    }
  };

  const handleAttachmentChange = (event) => {
    const files = Array.from(event.target.files || []);
    setComposeAttachments(files.slice(0, 5));
    setComposeError("");
  };

  const handleMarkRead = async (messageId) => {
    if (!onMarkRead) return;
    setActionBusyId(`read:${messageId}`);
    try {
      await onMarkRead(messageId);
      await onRefresh?.();
    } finally {
      setActionBusyId("");
    }
  };

  const handleDelete = async (messageId) => {
    if (!onDelete) return;
    if (String(messageId).startsWith("local-sent-")) {
      setLocalSentMessages((previous) => {
        const next = previous.filter((item) => item.id !== messageId);
        writeLocalSentMessages(next, localMessageScope);
        return next;
      });
      return;
    }
    setActionBusyId(`delete:${messageId}`);
    try {
      await onDelete(messageId);
      await onRefresh?.();
    } finally {
      setActionBusyId("");
    }
  };

  const openThread = (thread) => {
    setActiveThreadKey(thread.key);
    if (thread.email) {
      setComposeForm((prev) => ({ ...prev, recipient: thread.email }));
    }
  };

  const markThreadRead = async () => {
    if (!activeThread) return;
    const unreadMessages = activeThread.messages.filter((item) => !item.is_read);
    for (const message of unreadMessages) {
      await handleMarkRead(message.id);
    }
  };

  const totalUnread = messages.filter((item) => !item.is_read).length;

  return (
    <article className="chat-shell">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && <div className="chat-sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* ── Left sidebar ─────────────────────────────────── */}
      <aside className={`chat-sidebar${sidebarOpen ? " open" : ""}`}>
        <div className="chat-sidebar-head">
          <div className="chat-sidebar-title">
            <span className="chat-sidebar-icon">💬</span>
            <h3>{title}</h3>
            {totalUnread > 0 && <span className="chat-unread-badge">{totalUnread}</span>}
          </div>
          <button type="button" className="chat-sidebar-close-btn" onClick={() => setSidebarOpen(false)}><XIcon size={18} /></button>
        </div>

        <div className="chat-search-wrap">
          <Search size={14} className="chat-search-icon" />
          <input className="chat-search-input" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search conversations…" />
        </div>

        <div className="chat-filter-tabs">
          <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All</button>
          <button type="button" className={filter === "unread" ? "active" : ""} onClick={() => setFilter("unread")}>Unread {totalUnread > 0 && <b>{totalUnread}</b>}</button>
        </div>

        <div className="chat-thread-list">
          {filteredThreads.length === 0 ? (
            <p className="chat-empty-hint">No conversations found.</p>
          ) : (
            filteredThreads.map((thread) => (
              <button
                key={thread.key}
                type="button"
                className={`chat-thread-item${activeThread?.key === thread.key ? " active" : ""}${thread.unread ? " unread" : ""}`}
                onClick={() => { openThread(thread); setSidebarOpen(false); }}
              >
                <span className="chat-thread-avatar" data-letter={thread.name.slice(0, 1).toUpperCase()}>{thread.name.slice(0, 1).toUpperCase()}</span>
                <span className="chat-thread-body">
                  <span className="chat-thread-name">{thread.name}</span>
                  <span className="chat-thread-preview">{thread.preview || thread.role || "Start a conversation"}</span>
                </span>
                <span className="chat-thread-meta">
                  {thread.latestAt && <span className="chat-thread-time">{formatDate(thread.latestAt)}</span>}
                  {thread.unread > 0 && <span className="chat-thread-badge">{thread.unread}</span>}
                </span>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* ── Right chat panel ─────────────────────────────── */}
      <section className="chat-panel">
        {/* Header */}
        <header className="chat-panel-head">
          <button type="button" className="chat-mobile-menu-btn" onClick={() => setSidebarOpen(true)}>
            <span /><span /><span />
          </button>
          {activeThread ? (
            <div className="chat-head-contact">
              <span className="chat-head-avatar" data-letter={activeThread.name.slice(0,1).toUpperCase()}>{activeThread.name.slice(0,1).toUpperCase()}</span>
              <div>
                <strong>{activeThread.name}</strong>
                <small>{activeThread.role}{activeThread.email ? ` · ${activeThread.email}` : ""}</small>
              </div>
            </div>
          ) : (
            <div className="chat-head-contact"><strong>New conversation</strong></div>
          )}
          <div className="chat-head-actions">
            {activeThread?.unread > 0 && (
              <button type="button" className="chat-icon-btn" onClick={markThreadRead} title="Mark all read">
                <CheckCheck size={18} />
              </button>
            )}
          </div>
        </header>

        {/* Message body */}
        <div className="chat-body" ref={chatBodyRef}>
          {activeThread?.messages.length ? (
            <>
              {activeThread.messages.map((message) => {
                const isOut = message.direction === "outgoing";
                const attachments = messageAttachments(message);
                return (
                  <div key={message.id} className={`chat-bubble-wrap${isOut ? " out" : " in"}`}>
                    {!isOut && (
                      <span className="chat-bubble-avatar" data-letter={(message.from || activeThread.name).slice(0,1).toUpperCase()}>
                        {(message.from || activeThread.name).slice(0,1).toUpperCase()}
                      </span>
                    )}
                    <div className={`chat-bubble${isOut ? " out" : " in"}`}>
                      {messageSubject(message) && <p className="chat-bubble-subject">{messageSubject(message)}</p>}
                      {messageBody(message) && <p className="chat-bubble-text">{messageBody(message)}</p>}
                      {attachments.length > 0 && (
                        <div className="chat-bubble-attachments">
                          {attachments.map((att, idx) => (
                            <MessageAttachment key={`${attachmentUrl(att) || attachmentLabel(att)}-${idx}`} attachment={att} index={idx} />
                          ))}
                        </div>
                      )}
                      <div className="chat-bubble-foot">
                        <span className="chat-bubble-time">{formatDate(message.created_at)}</span>
                        <span className="chat-bubble-status">
                          {isOut ? (message.is_read ? <CheckCheck size={13} /> : <Check size={13} />) : null}
                        </span>
                        <span className="chat-bubble-btns">
                          {!isOut && !message.is_read && (
                            <button type="button" disabled={actionBusyId === `read:${message.id}`} onClick={() => handleMarkRead(message.id)} title="Mark read">
                              <Check size={12} />
                            </button>
                          )}
                          <button type="button" disabled={actionBusyId === `delete:${message.id}`} onClick={() => handleDelete(message.id)} title="Delete">
                            <Trash2 size={12} />
                          </button>
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="chat-empty-state">
              <span className="chat-empty-icon">💬</span>
              <p>{activeThread ? "No messages yet — say hello!" : "Select a conversation to get started."}</p>
            </div>
          )}
        </div>

        {/* Composer */}
        {onComposeSubmit ? (
          <form className="chat-composer" onSubmit={handleComposeSubmit}>
            {composeAttachments.length > 0 && (
              <div className="chat-attachment-preview">
                {composeAttachments.map((file) => (
                  <span key={`${file.name}-${file.size}`} className="chat-attachment-chip">
                    <Paperclip size={11} />
                    {file.name}
                    <button type="button" onClick={() => setComposeAttachments((p) => p.filter((f) => f !== file))}><XIcon size={10}/></button>
                  </span>
                ))}
              </div>
            )}
            {(composeError || composeFeedback) && (
              <div className={`chat-composer-feedback${composeError ? " error" : " success"}`}>
                {composeError || composeFeedback}
              </div>
            )}
            <div className="chat-composer-row">
              {/* Emoji button */}
              <div className="chat-emoji-wrap" ref={emojiPickerRef}>
                <button
                  type="button"
                  className="chat-composer-icon-btn"
                  onClick={() => setShowEmojiPicker((p) => !p)}
                  aria-label="Insert emoji"
                  title="Emoji"
                >
                  <Smile size={20} />
                </button>
                {showEmojiPicker && (
                  <div className="chat-emoji-picker">
                    {CHAT_EMOJIS.map((emoji) => (
                      <button key={emoji} type="button" className="chat-emoji-btn" onClick={() => insertEmoji(emoji)}>
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Text input */}
              <textarea
                ref={textareaRef}
                className="chat-composer-input"
                value={composeForm.body}
                onChange={(e) => setComposeForm((p) => ({ ...p, body: e.target.value }))}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleComposeSubmit(e); } }}
                placeholder={composerRecipient ? `Message ${composerRecipient.label.split(" - ")[0]}…` : "Write a message…"}
                rows={1}
              />

              {/* Paperclip / attach */}
              <label className="chat-composer-icon-btn" title="Attach file" aria-label="Attach file">
                <Paperclip size={20} />
                <input ref={attachmentInputRef} type="file" multiple onChange={handleAttachmentChange} style={{display:"none"}} />
              </label>

              {/* Send */}
              <button
                type="submit"
                className="chat-send-btn"
                disabled={composerRecipientOptions.length === 0 || isComposing}
                aria-label="Send"
                title="Send (Enter)"
              >
                {isComposing ? <span className="chat-send-spinner" /> : <Send size={18} />}
              </button>
            </div>
          </form>
        ) : null}
      </section>
    </article>
  );
}

function notificationTimestampParts(value) {
  if (!value) {
    return { date: "-", time: "" };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { date: String(value), time: "" };
  }
  return {
    date: date.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" }),
    time: date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
}

function mapGlobalNotificationItem(item, type = "message") {
  if (type === "announcement") {
    return {
      id: `announcement-${item.id}`,
      sourceId: item.id,
      source: "announcement",
      user: "SchoolDom",
      role: "Announcement",
      module: "Announcements",
      category: "System",
      action: item.title || "New school announcement.",
      status: "Published",
      priority: item.priority || "Normal",
      tone: item.priority === "urgent" || item.priority === "high" ? "warning" : "info",
      createdAt: item.published_at,
      isRead: true,
    };
  }

  if (type === "notification") {
    const tone = item.type === "security" || item.type === "error" ? "danger" : item.type === "warning" ? "warning" : "info";
    return {
      id: `notification-${item.id}`,
      sourceId: item.id,
      source: "notification",
      user: "SchoolDom",
      role: "System",
      module: item.type || "Notifications",
      category: "System",
      action: item.message || item.title || "New platform notification.",
      status: item.is_read ? "Read" : "Unread",
      priority: tone === "danger" ? "High" : "Normal",
      tone,
      createdAt: item.created_at,
      isRead: Boolean(item.is_read),
    };
  }

  return {
    id: `message-${item.id}`,
    sourceId: item.id,
    source: "message",
    user: item.from || item.from_name || "SchoolDom",
    role: item.from_role || "Sender",
    module: "Inbox",
    category: "Messages",
    action: item.body || item.message || item.subject || "New message received.",
    status: item.is_read ? "Read" : "Unread",
    priority: item.is_read ? "Normal" : "High",
    tone: item.is_read ? "info" : "success",
    createdAt: item.created_at || item.sent_at,
    isRead: Boolean(item.is_read),
  };
}

function mergeNotificationRows(primary = [], secondary = []) {
  const seen = new Set();
  return [...primary, ...secondary].filter((item) => {
    const key = item?.id || item?.sourceId || JSON.stringify(item);
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function GlobalNotificationBell({ session, onNavigate }) {
  const [summary, setSummary] = useState({ total: 0, unread: 0 });
  const [latestUnread, setLatestUnread] = useState(null);
  const [toast, setToast] = useState("");
  const [open, setOpen] = useState(false);
  const [snapshot, setSnapshot] = useState({ notifications: [], inbox: [], announcements: [] });
  const [searchTerm, setSearchTerm] = useState("");
  const [readIds, setReadIds] = useState(() => new Set());
  const [busyId, setBusyId] = useState("");
  const [mobileBellEnabled, setMobileBellEnabled] = useState(false);
  const [mobileBellPosition, setMobileBellPosition] = useState(() => {
    try {
      if (typeof window === "undefined") return null;
      const saved = window.localStorage.getItem("schooldom.mobileNotificationBellPosition");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const latestUnreadIdRef = useRef("");
  const initializedRef = useRef(false);
  const dragRef = useRef({ active: false, moved: false, offsetX: 0, offsetY: 0 });

  const loadInbox = useCallback(async () => {
    try {
      const [messagesResult, dashboardResult] = await Promise.allSettled([
        requestJson(session, "GET", "/api/app/messages/"),
        fetchDashboardSnapshot(session),
      ]);
      const data = messagesResult.status === "fulfilled" ? messagesResult.value : {};
      const dashboardData = dashboardResult.status === "fulfilled" ? dashboardResult.value : {};
      const messages = mergeNotificationRows(data.inbox || data.messages || [], dashboardData?.inbox || dashboardData?.messages || []);
      const notifications = mergeNotificationRows(data.notifications || [], dashboardData?.notifications || []);
      const announcements = mergeNotificationRows(data.announcements || [], dashboardData?.announcements || []);
      const unreadMessages = messages.filter((item) => !item.is_read);
      const unreadNotifications = notifications.filter((item) => !item.is_read);
      const nextLatest =
        [...unreadMessages, ...unreadNotifications]
          .sort((a, b) => new Date(b.created_at || b.sent_at || 0) - new Date(a.created_at || a.sent_at || 0))[0] || null;
      setSnapshot({ notifications, inbox: messages, announcements });
      setSummary({
        total: messages.length + notifications.length + announcements.length,
        unread:
          Number(data.summary?.unread_inbox ?? dashboardData?.metrics?.unread_inbox ?? unreadMessages.length) +
          Number(data.summary?.unread_notifications ?? dashboardData?.metrics?.unread_notifications ?? unreadNotifications.length),
      });
      setLatestUnread(nextLatest);

      if (!initializedRef.current) {
        latestUnreadIdRef.current = nextLatest?.id || "";
        initializedRef.current = true;
        return;
      }

      if (nextLatest?.id && nextLatest.id !== latestUnreadIdRef.current) {
        latestUnreadIdRef.current = nextLatest.id;
        setToast(`${nextLatest.from || nextLatest.title || "New notification"}${nextLatest.body || nextLatest.message ? `: ${nextLatest.body || nextLatest.message}` : ""}`);
      }
    } catch {
      // Keep the bell quiet if polling fails temporarily.
    }
  }, [session]);

  useEffect(() => {
    initializedRef.current = false;
    latestUnreadIdRef.current = "";
    loadInbox();
    const pollId = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadInbox();
      }
    }, MESSAGE_POLL_INTERVAL_MS);
    return () => window.clearInterval(pollId);
  }, [loadInbox]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeoutId = window.setTimeout(() => setToast(""), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  useEffect(() => {
    const updateMobileState = () => setMobileBellEnabled(isMobileViewport());
    updateMobileState();
    window.addEventListener("resize", updateMobileState);
    return () => window.removeEventListener("resize", updateMobileState);
  }, []);

  useEffect(() => {
    if (!mobileBellPosition) return;
    try {
      window.localStorage.setItem("schooldom.mobileNotificationBellPosition", JSON.stringify(mobileBellPosition));
    } catch {
      // Ignore storage failures; dragging should still work for the current page.
    }
  }, [mobileBellPosition]);

  const notificationItems = useMemo(() => {
    const items = [
      ...(snapshot.notifications || []).map((item) => mapGlobalNotificationItem(item, "notification")),
      ...(snapshot.inbox || []).map((item) => mapGlobalNotificationItem(item, "message")),
      ...(snapshot.announcements || []).map((item) => mapGlobalNotificationItem(item, "announcement")),
    ];
    return items
      .map((item) => ({ ...item, isRead: readIds.has(item.id) || item.isRead }))
      .sort((a, b) => new Date(b.createdAt || 0) - new Date(a.createdAt || 0));
  }, [snapshot, readIds]);

  const filteredItems = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return notificationItems;
    }
    return notificationItems.filter((item) =>
      `${item.user} ${item.role} ${item.module} ${item.action} ${item.status} ${item.priority}`.toLowerCase().includes(query)
    );
  }, [notificationItems, searchTerm]);

  const unreadCount = notificationItems.filter((item) => !item.isRead).length;

  const isMobileViewport = () => typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches;

  const clampMobileBellPosition = useCallback((x, y) => {
    const buttonSize = 44;
    const padding = 8;
    const maxX = Math.max(padding, window.innerWidth - buttonSize - padding);
    const maxY = Math.max(padding, window.innerHeight - buttonSize - padding);
    return {
      x: Math.min(Math.max(padding, x), maxX),
      y: Math.min(Math.max(padding, y), maxY),
    };
  }, []);

  const beginMobileBellDrag = (event) => {
    if (!isMobileViewport()) return;
    const rect = event.currentTarget.getBoundingClientRect();
    dragRef.current = {
      active: true,
      moved: false,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const moveMobileBell = (event) => {
    if (!dragRef.current.active || !isMobileViewport()) return;
    const next = clampMobileBellPosition(event.clientX - dragRef.current.offsetX, event.clientY - dragRef.current.offsetY);
    const previous = mobileBellPosition || {};
    if (Math.abs((previous.x ?? next.x) - next.x) > 2 || Math.abs((previous.y ?? next.y) - next.y) > 2) {
      dragRef.current.moved = true;
    }
    setMobileBellPosition(next);
  };

  const endMobileBellDrag = (event) => {
    if (!dragRef.current.active) return;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    window.setTimeout(() => {
      dragRef.current = { active: false, moved: false, offsetX: 0, offsetY: 0 };
    }, 0);
  };

  const handleBellClick = () => {
    if (dragRef.current.moved) return;
    setOpen(true);
  };

  const markRead = async (item) => {
    setBusyId(item.id);
    setReadIds((prev) => {
      const next = new Set(prev);
      next.add(item.id);
      return next;
    });
    try {
      if (item.source === "message" && item.sourceId && !item.isRead) {
        await requestJson(session, "POST", `/api/app/messages/${item.sourceId}/read/`);
        await loadInbox();
      }
      if (item.source === "notification" && item.sourceId && !item.isRead) {
        await requestJson(session, "POST", `/api/app/notifications/${item.sourceId}/read/`);
        await loadInbox();
      }
    } finally {
      setBusyId("");
    }
  };

  const markAllRead = async () => {
    const unreadItems = notificationItems.filter((item) => !item.isRead);
    if (!unreadItems.length) return;
    setBusyId("__all__");
    try {
      const unreadMessages = unreadItems.filter((item) => item.source === "message" && item.sourceId);
      const unreadNotifications = unreadItems.filter((item) => item.source === "notification" && item.sourceId);
      await Promise.all(
        [
          ...unreadMessages.map((item) => requestJson(session, "POST", `/api/app/messages/${item.sourceId}/read/`).catch(() => null)),
          ...unreadNotifications.map((item) => requestJson(session, "POST", `/api/app/notifications/${item.sourceId}/read/`).catch(() => null)),
        ]
      );
      setReadIds((prev) => {
        const next = new Set(prev);
        unreadItems.forEach((item) => next.add(item.id));
        return next;
      });
      setSummary((prev) => ({ ...prev, unread: 0 }));
      if (unreadMessages.length || unreadNotifications.length) {
        await loadInbox();
      }
    } finally {
      setBusyId("");
    }
  };

  return (
    <div
      className={`global-notification-shell ${mobileBellEnabled && mobileBellPosition ? "has-mobile-position" : ""}`}
      style={mobileBellEnabled && mobileBellPosition ? { top: `${mobileBellPosition.y}px`, left: `${mobileBellPosition.x}px`, right: "auto" } : undefined}
    >
      {toast ? (
        <button type="button" className="notification-toast" onClick={() => setOpen(true)}>
          <strong>New message</strong>
          <span>{toast}</span>
        </button>
      ) : null}
      <button
        type="button"
        className={`notification-button global-notification-button ${unreadCount > 0 ? "has-unread" : ""}`}
        onClick={handleBellClick}
        onPointerDown={beginMobileBellDrag}
        onPointerMove={moveMobileBell}
        onPointerUp={endMobileBellDrag}
        onPointerCancel={endMobileBellDrag}
        title={latestUnread ? `${latestUnread.from || "New notification"}${latestUnread.subject ? `: ${latestUnread.subject}` : ""}` : "Notifications"}
        aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
      >
        <BellIcon className="inline-icon" />
        <span>Notifications</span>
        {unreadCount > 0 ? <strong className="notification-badge">{unreadCount > 99 ? "99+" : unreadCount}</strong> : null}
      </button>
      {open ? (
        <div className="notification-drawer-overlay" role="presentation" onClick={() => setOpen(false)}>
          <aside className="notification-drawer" role="dialog" aria-modal="true" aria-label="Notifications" onClick={(event) => event.stopPropagation()}>
            <section className="screen-grid admin-notification-center notification-popup-center">
              <header className="notification-center-hero">
                <div>
                  <p className="topbar-kicker">Live updates</p>
                  <h2>Notifications</h2>
                  <p>Inbox messages, announcements, and system updates.</p>
                </div>
                <button type="button" className="notification-close-button" onClick={() => setOpen(false)}>Close</button>
              </header>
              <div className="notification-layout">
                <section className="app-panel notification-feed-panel">
                  <div className="notification-toolbar">
                    <div className="notification-search">
                      <FilterIcon className="inline-icon" />
                      <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search notifications..." />
                    </div>
                    <button type="button" className="table-action notification-mark-all" disabled={unreadCount === 0 || busyId === "__all__"} onClick={markAllRead}>
                      {busyId === "__all__" ? "Clearing..." : "Mark all as read"}
                    </button>
                  </div>
                  <div className="notification-card-list">
                    {filteredItems.length === 0 ? (
                      <p className="panel-empty">No notifications match this view.</p>
                    ) : (
                      filteredItems.map((item) => {
                        const time = notificationTimestampParts(item.createdAt);
                        return (
                          <article key={item.id} className={`admin-notification-card tone-${item.tone} ${item.isRead ? "is-read" : "is-unread"}`}>
                            <div className="notification-card-marker" />
                            <div className="notification-card-body">
                              <div className="notification-card-topline">
                                <div>
                                  <h3>{item.user}</h3>
                                  <p>{item.role} - {item.module}</p>
                                </div>
                                <div className="notification-badge-row">
                                  <span className={`notification-status status-${item.tone}`}>{item.status}</span>
                                  <span className={`notification-priority priority-${String(item.priority).toLowerCase()}`}>{item.priority}</span>
                                </div>
                              </div>
                              <p className="notification-action">{item.action}</p>
                              <div className="notification-card-footer">
                                <span>{time.date}</span>
                                <span>{time.time}</span>
                                <span>{item.category}</span>
                              </div>
                            </div>
                            <button type="button" className="table-action" disabled={item.isRead || busyId === item.id} onClick={() => markRead(item)}>
                              {item.isRead ? "Read" : busyId === item.id ? "Saving..." : "Mark read"}
                            </button>
                          </article>
                        );
                      })
                    )}
                  </div>
                </section>
              </div>
            </section>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export function GlobalHomeButton({ session, currentPath, onNavigate }) {
  const homePath = session ? "/dashboard" : "/";
  const isHome = normalizePath(currentPath) === homePath;

  return (
    <button
      type="button"
      className={`global-home-button ${isHome ? "is-home" : ""}`}
      onClick={() => onNavigate?.(homePath)}
      aria-label={isHome ? "Home" : "Go to home"}
      title={isHome ? "Home" : "Go to home"}
    >
      <DashboardIcon name="home" className="inline-icon" />
    </button>
  );
}

export function StudentOfflineExamPage({ exams = [], onSubmitOffline, onClose }) {
  const [drafts, setDrafts] = useState(() => readOfflineDrafts());
  const [status, setStatus] = useState({});

  const handleDraftChange = (examId, value) => {
    setDrafts((prev) => {
      const next = {
        ...prev,
        [examId]: { answer: value, savedAt: new Date().toISOString() },
      };
      writeOfflineDrafts(next);
      return next;
    });
  };

  const handleSubmit = async (exam) => {
    const answer = drafts[exam.id]?.answer || "";
    if (!answer.trim()) {
      setStatus((prev) => ({ ...prev, [exam.id]: { type: "error", message: "Add an answer before submitting." } }));
      return;
    }
    setStatus((prev) => ({ ...prev, [exam.id]: { type: "pending" } }));
    try {
      await onSubmitOffline(exam.id, { answer, submitted_at: new Date().toISOString() });
      setStatus((prev) => ({ ...prev, [exam.id]: { type: "success", message: "Submitted offline." } }));
    } catch (submissionError) {
      setStatus((prev) => ({
        ...prev,
        [exam.id]: { type: "error", message: submissionError.message || "Could not submit." },
      }));
    }
  };

  if (exams.length === 0) {
  return (
    <article className="app-panel">
        <h3>Offline exams</h3>
        <p className="panel-empty">No offline exams assigned.</p>
        <div className="panel-form-actions">
          <button type="button" onClick={onClose}>
            Return to dashboard
          </button>
        </div>
      </article>
    );
  }

  return (
    <article className="app-panel offline-page">
      <header className="offline-header">
        <div>
          <h3>Offline assessments</h3>
          <p>Answer the prompts below and submit when you regain connectivity.</p>
        </div>
        <button type="button" onClick={onClose}>
          Back to dashboard
        </button>
      </header>
      {exams.map((exam) => (
            <div key={exam.id} className="offline-exam-card">
          <div className="offline-exam-head">
            <div>
              <p className="offline-exam-title">{exam.title || "Unnamed assessment"}</p>
              <small>
                {exam.class_name || "Class not assigned"} • Due {exam.due_date || exam.start_date || "TBD"}
              </small>
            </div>
            <span className="offline-status">
              {status[exam.id]?.type === "success"
                ? "Submitted offline"
                : status[exam.id]?.type === "pending"
                  ? "Submitting…"
                  : "Draft"}
            </span>
          </div>
          <p className="field-note">{exam.instructions || exam.description || "No instructions provided."}</p>
          <textarea
            className="offline-textarea"
            value={drafts[exam.id]?.answer || ""}
            onChange={(event) => handleDraftChange(exam.id, event.target.value)}
            placeholder="Draft your answer here..."
          />
          <div className="panel-form-actions">
            <button
              type="button"
              onClick={() => handleSubmit(exam)}
              disabled={status[exam.id]?.type === "pending"}
            >
              Submit offline
            </button>
            <span className="field-note">
              Last saved {drafts[exam.id]?.savedAt ? formatDate(drafts[exam.id].savedAt) : "not saved yet"}
            </span>
          </div>
          {status[exam.id]?.message ? (
            <p className={`form-feedback ${status[exam.id].type === "error" ? "error" : "success"}`}>
              {status[exam.id].message}
            </p>
          ) : null}
        </div>
      ))}
    </article>
  );
}


