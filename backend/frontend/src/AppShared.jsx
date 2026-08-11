import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Paperclip, Smile, Send, Check, CheckCheck, Trash2, Phone, Video, MoreVertical, Search, X as XIcon, ChevronDown, Mic, Megaphone } from "lucide-react";
import {
  API_BASE_URL,
  LEGACY_SESSION_KEY,
  MESSAGE_POLL_INTERVAL_MS,
  SESSION_KEY,
  TEACHER_ATTENDANCE_PREFIX,
  UI_THEME_KEY,
} from "./appConstants";

// Shared popup/modal animation primitive used app-wide: a slow slide-up +
// fade-in on open, a matching slide-down + fade-out on close (real exit
// animation, not just entrance - the component delays unmounting until the
// close animation finishes). Defaults to the same `modal-overlay`/
// `edit-modal-card` classes/keyframes used by most existing modals in the
// app (see styles.css) so new consumers automatically match the established
// look; pass overlayClassName/cardClassName to drive a different existing
// overlay family (e.g. "cfm-overlay"/"cfm-card") instead of inventing a new
// visual style. Respects prefers-reduced-motion by skipping the closing
// delay entirely.
const POPUP_CLOSE_DURATION_MS = 260;

export function Popup({
  open,
  onClose,
  children,
  overlayClassName = "modal-overlay",
  cardClassName = "edit-modal-card",
  extraCardClassName = "",
  labelledBy,
  role = "dialog",
  closeOnBackdrop = true,
}) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      setClosing(false);
      return undefined;
    }
    if (!mounted) return undefined;
    const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setMounted(false);
      return undefined;
    }
    setClosing(true);
    const timer = window.setTimeout(() => {
      setMounted(false);
      setClosing(false);
    }, POPUP_CLOSE_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [open, mounted]);

  useEffect(() => {
    if (!mounted) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mounted, onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className={`${overlayClassName}${closing ? " is-closing" : ""}`}
      role={role}
      aria-modal="true"
      aria-labelledby={labelledBy}
      onClick={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose?.();
      }}
    >
      <div className={`${cardClassName}${extraCardClassName ? ` ${extraCardClassName}` : ""}${closing ? " is-closing" : ""}`}>
        {children}
      </div>
    </div>,
    document.body
  );
}

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
  const str = (v) => (typeof v === "string" && v) || null;
  const name =
    str(school.name) ||
    str(school.school_name) ||
    str(school.schoolName) ||
    str(school.school) ||
    str(school.institution_name) ||
    str(school.institutionName) ||
    str(school.tenant?.name) ||
    str(school.user?.school_name) ||
    str(school.user?.schoolName) ||
    str(school.user?.school?.name) ||
    str(school.user?.tenant?.name) ||
    // School Superadmin (proprietor) accounts have no single school/tenant -
    // fall back to their school group's name before the generic default.
    str(school.school_group?.name) ||
    str(school.group_name) ||
    str(school.user?.school_group?.name) ||
    "SchoolDom";
  return {
    name,
    code: str(school.school_code) || str(school.schoolCode) || str(school.tenant?.schema_name) || str(school.user?.school_code) || str(school.user?.schoolCode) || str(school.user?.tenant?.schema_name) || "",
    logo: str(school.logo) || str(school.logo_url) || str(school.logoUrl) || str(school.school_logo) || str(school.schoolLogo) || str(school.logo_path) || str(school.user?.school_logo) || str(school.user?.schoolLogo) || "",
    motto: str(school.motto) || str(school.tagline) || str(school.school_motto) || str(school.schoolMotto) || str(school.school_tagline) || str(school.schoolTagline) || str(school.user?.motto) || str(school.user?.tagline) || "",
    address: str(school.address) || str(school.school_address) || str(school.schoolAddress) || str(school.user?.school_address) || str(school.user?.schoolAddress) || "",
    phone: str(school.phone) || str(school.phone_number) || str(school.phoneNumber) || str(school.school_phone) || str(school.schoolPhone) || str(school.user?.school_phone) || str(school.user?.schoolPhone) || "",
    email: str(school.email) || str(school.school_email) || str(school.schoolEmail) || str(school.user?.school_email) || str(school.user?.schoolEmail) || "",
    school_type: str(school.school_type) || str(school.schoolType) || str(school.type) || str(school.user?.school_type) || str(school.user?.schoolType) || "k12",
    signature: str(school.signature) || str(school.school_signature) || str(school.schoolSignature) || "",
    initials: name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "SD",
  };
}

export const DEFAULT_DOCUMENT_THEME = {
  orientation: "portrait",
  id_card_orientation: "landscape",
  page_size: "A4",
  margin_mm: 15,
  font_family: "Segoe UI",
  font_size_body: 13,
  font_size_heading: 20,
  primary_color: "#0f766e",
  secondary_color: "#0f172a",
  accent_color: "#0f766e",
  table_style: "bordered",
  border_style: "solid",
  border_width: 1,
  header_note: "",
  footer_text: "",
  show_logo: true,
  show_signature: true,
  watermark_enabled: false,
  watermark_source: "text",
  watermark_text: "",
  watermark_opacity: 8,
};

/** Reads a `document_theme` payload off the first source object that has one
 * (as folded into `_school_payload`/`_school_identity_payload` server-side),
 * merged over the defaults so a school that never saved a theme still gets a
 * complete, renderable object. */
export function resolveDocumentTheme(...sources) {
  for (const source of sources) {
    const theme = source?.document_theme || source?.documentTheme;
    if (theme && Object.keys(theme).length) {
      return { ...DEFAULT_DOCUMENT_THEME, ...theme };
    }
  }
  return DEFAULT_DOCUMENT_THEME;
}

/** Maps a DocumentTheme into the CSS custom properties consumed by
 * documentStylesForExport() - the single theme -> CSS mapping shared by the
 * live preview and the real print/PDF/PNG output, so they can never drift. */
export function themeToCssVars(theme) {
  const t = { ...DEFAULT_DOCUMENT_THEME, ...(theme || {}) };
  return {
    "--doc-primary": t.primary_color,
    "--doc-secondary": t.secondary_color,
    "--doc-accent": t.accent_color,
    "--invoice-accent": t.accent_color,
    "--doc-font-family": `'${t.font_family}'`,
    "--doc-font-size-body": `${t.font_size_body}px`,
    "--doc-font-size-heading": `${t.font_size_heading}px`,
    "--doc-border-width": `${t.border_width}px`,
    "--doc-border-style": t.border_style,
    // Overrides the .id-card-workspace/.id-card-print-area class defaults
    // (inline style always wins) so ID cards pick up the school's theme too.
    "--id-card-teal": t.accent_color,
    "--id-card-green": t.primary_color,
  };
}

const escapePrintableHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

/** The single shared stylesheet for every generated document (report cards,
 * transcripts, testimonials, invoices, receipts, bills, payslips, ID cards,
 * broadsheets, service agreements) across popup-print, PDF (browser
 * print-to-PDF), and PNG (canvas rasterization) output, so a school's
 * Document Customization theme renders identically everywhere. */
export function documentStylesForExport(theme) {
  const t = { ...DEFAULT_DOCUMENT_THEME, ...(theme || {}) };
  const tableStyleCss =
    t.table_style === "striped"
      ? `.document-table tbody tr:nth-child(even),.invoice-doc-items tbody tr:nth-child(even){background:#f1f5f9}.document-table td,.document-table th,.invoice-doc-items td,.invoice-doc-items th{border-left:none;border-right:none;border-top:none}`
      : t.table_style === "minimal"
      ? `.document-table td,.document-table th,.invoice-doc-items td,.invoice-doc-items th{border-left:none;border-right:none;border-top:none}`
      : "";
  const watermarkCss = t.watermark_enabled
    ? `.doc-watermark{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0;overflow:hidden}.doc-watermark span{font-size:64px;font-weight:800;color:var(--doc-primary);opacity:${Math.max(1, Math.min(40, Number(t.watermark_opacity) || 8))}%;transform:rotate(-30deg);white-space:nowrap}.doc-watermark img{max-width:60%;opacity:${Math.max(1, Math.min(40, Number(t.watermark_opacity) || 8))}%}.official-document,.invoice-document,.service-agreement-document{position:relative}.official-document>*:not(.doc-watermark),.invoice-document>*:not(.doc-watermark),.service-agreement-document>*:not(.doc-watermark){position:relative;z-index:1}`
    : "";
  return `
    @page{size:${t.page_size} ${t.orientation};margin:${t.margin_mm}mm}
    :root{--doc-primary:${t.primary_color};--doc-secondary:${t.secondary_color};--doc-accent:${t.accent_color};--invoice-accent:${t.accent_color};--doc-font-family:'${t.font_family}';--doc-font-size-body:${t.font_size_body}px;--doc-font-size-heading:${t.font_size_heading}px;--doc-border-width:${t.border_width}px;--doc-border-style:${t.border_style}}
    *{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#0f172a;font-family:var(--doc-font-family),'Segoe UI',Georgia,'Times New Roman',serif;font-size:var(--doc-font-size-body);padding:40px}
    .print-letterhead{display:flex;align-items:center;gap:14px;border-bottom:2px solid var(--doc-secondary);padding-bottom:14px;margin-bottom:24px}
    .print-letterhead img{width:56px;height:56px;object-fit:contain}.print-letterhead h1{font-size:1.15rem;margin:0}
    .print-letterhead p{margin:2px 0 0;font-size:0.85rem;color:#4b5563}.print-body p{line-height:1.7;font-size:0.95rem}
    .print-meta{margin-bottom:18px;font-size:0.85rem;color:#4b5563}.print-signature{margin-top:48px;font-size:0.9rem}
    .official-document{width:min(100%,850px);margin:24px auto;background:#fff;color:#111827;padding:42px;border:1px solid #d7e0ec;box-shadow:0 18px 45px rgba(15,23,42,.12)}.official-doc-header{text-align:center;border-bottom:3px double var(--doc-accent);padding-bottom:18px;margin-bottom:24px}.official-doc-logo{width:82px;height:82px;border-radius:18px;border:1px solid #cbd5e1;display:grid;place-items:center;margin:0 auto 10px;overflow:hidden;background:#f8fafc}.official-doc-logo img{width:100%;height:100%;object-fit:contain}.official-doc-logo span{font-family:Arial,sans-serif;font-weight:900;color:var(--doc-accent)}.official-doc-header h1{font-size:calc(var(--doc-font-size-heading) * 1.4);text-transform:uppercase;letter-spacing:.04em;margin:0}.official-doc-header p{margin:5px 0 0;color:#475569;font-family:Arial,sans-serif}.official-doc-motto{font-style:italic;font-weight:800;color:var(--doc-accent)}.official-doc-title{text-align:center;text-transform:uppercase;letter-spacing:.12em;font-size:var(--doc-font-size-heading);margin:20px 0;color:var(--doc-accent)}.doc-info-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin-bottom:22px}.doc-line{display:flex;gap:10px;border-bottom:1px solid #94a3b8;min-height:30px;align-items:flex-end}.doc-line strong{font-family:Arial,sans-serif;font-size:12px;text-transform:uppercase;white-space:nowrap;color:#334155}.doc-line span{font-weight:700}.document-table{width:100%;border-collapse:collapse;margin:14px 0 24px;font-family:Arial,sans-serif;font-size:13px}.document-table th,.document-table td{border:var(--doc-border-width) var(--doc-border-style) #cbd5e1;padding:8px;text-align:left}.document-table th{background:#eef6f3;color:var(--doc-accent);text-transform:uppercase;font-size:11px}.term-record{break-inside:avoid;margin-bottom:18px}.term-record h3{margin:0 0 8px;font-family:Arial,sans-serif;color:var(--doc-accent)}.testimonial-border{border:12px double var(--doc-accent);padding:28px;background:linear-gradient(0deg,rgba(15,118,110,.035),rgba(15,118,110,.035)),#fff}.testimonial-title{font-size:42px;color:var(--doc-accent);font-weight:900;text-align:center;font-family:var(--doc-font-family),Georgia,'Times New Roman',serif;margin:12px 0 24px}.testimonial-list{display:grid;gap:10px;counter-reset:item}.testimonial-row{display:grid;grid-template-columns:34px 190px 1fr;gap:10px;align-items:end}.testimonial-row:before{counter-increment:item;content:counter(item) ".";font-weight:800}.testimonial-row strong{font-family:Arial,sans-serif;font-size:12px}.testimonial-row span{border-bottom:1px solid #334155;min-height:24px;font-weight:700;padding:0 6px}.doc-summary-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}.doc-summary-strip div{border:1px solid #cbd5e1;padding:10px;background:#f8fafc}.doc-summary-strip strong,.doc-summary-strip span{display:block}.doc-summary-strip strong{font-family:Arial,sans-serif;font-size:11px;color:#64748b;text-transform:uppercase}.doc-summary-strip span{font-size:18px;font-weight:900}.signature-row{display:grid;grid-template-columns:1fr 120px 1fr;gap:20px;align-items:end;margin-top:42px}.signature-line{border-top:1px solid #111827;text-align:center;padding-top:8px;font-family:Arial,sans-serif;font-weight:800;font-size:12px}.doc-signature-img{display:block;height:34px;max-width:150px;object-fit:contain;margin:0 auto 4px}.stamp-seal{width:98px;height:98px;border-radius:50%;background:#dc2626;box-shadow:inset 0 0 0 8px rgba(255,255,255,.18);margin:auto}.stamp-box{border:2px dashed #94a3b8;min-height:86px;display:grid;place-items:center;color:#64748b;font-family:Arial,sans-serif;text-transform:uppercase;font-weight:800}.document-note{font-family:Arial,sans-serif;color:#64748b;font-size:12px}.no-print{display:none}.id-card-print-area{width:100%;min-height:620px;background:#fff;display:grid;grid-template-columns:370px 370px;gap:18px;place-content:center;place-items:center;font-family:Inter,Arial,sans-serif}.id-card-flip-inner{display:contents;transform:none!important}.id-card-face{position:relative;inset:auto;backface-visibility:visible}.id-card-back{transform:none}.id-card-preview-card{width:370px;min-height:560px;background:#fff;color:#102033;border:1px solid #d7e0ec;border-radius:22px;overflow:hidden;box-shadow:none}.id-card-back{display:grid;grid-template-rows:auto 1fr auto;background:#08111f;color:#fff}.id-card-ribbon{background:var(--doc-accent);color:#fff;text-align:center;text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:900;padding:10px}.id-card-top,.id-card-back-head{display:flex;gap:12px;align-items:center;padding:18px 22px;background:linear-gradient(135deg,#f8fbff,#e8f2fb)}.id-card-back-head{background:#102033;color:#fff}.id-card-school-logo,.id-card-photo{display:grid;place-items:center;overflow:hidden;background:#fff;border:1px solid #d8e3ef}.id-card-school-logo{width:54px;height:54px;border-radius:16px;flex:0 0 auto}.id-card-school-logo img,.id-card-photo img,.id-card-back-qr img{width:100%;height:100%;object-fit:cover}.id-card-school-logo span,.id-card-photo span{font-weight:900;color:var(--doc-accent)}.id-card-top strong,.id-card-back-head strong{display:block;font-size:18px}.id-card-motto{display:block;color:var(--doc-accent);font-size:11px;font-style:italic;font-weight:800;margin-top:2px}.id-card-back-head .id-card-motto{color:#a7f3d0}.id-card-top span,.id-card-back-head span{display:block;color:#64748b;font-size:12px;margin-top:2px}.id-card-back-head span{color:#cbd5e1}.id-card-person{display:grid;grid-template-columns:94px 1fr;gap:16px;padding:24px 22px 18px}.id-card-photo{width:94px;height:112px;border-radius:18px}.id-card-person p{margin:4px 0 8px;font-size:24px;line-height:1.05;font-weight:900}.id-card-person strong{display:inline-flex;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:6px 10px;font-size:13px}.id-card-person span{display:block;color:#475569;margin-top:10px;font-weight:700}.id-card-details{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 22px 18px}.id-card-details div{border:1px solid #e2e8f0;border-radius:12px;padding:10px;background:#f8fafc}.id-card-details dt{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800}.id-card-details dd{margin:4px 0 0;font-weight:800;font-size:13px}.id-card-signature-block{display:grid;justify-items:center;gap:2px;margin:0 22px 14px}.id-card-signature-img{height:36px;max-width:140px;object-fit:contain}.id-card-signature-block span{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800}.id-card-front-footer{margin:0 22px 22px;padding:16px;border-radius:18px;background:#08111f;color:#fff}.id-card-front-footer strong,.id-card-front-footer span{display:block}.id-card-front-footer span{color:#cbd5e1;font-size:12px;margin-top:6px}.id-card-back-qr-panel{display:grid;justify-items:center;padding:18px 22px 10px;text-align:center}.id-card-back-qr-panel p{margin:0 0 16px;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#a7f3d0}.id-card-back-qr{width:250px;height:250px;border-radius:18px;background:#fff;padding:12px;display:grid;place-items:center;color:var(--doc-accent);font-weight:900}.id-card-back-qr img{object-fit:contain}.id-card-back-qr-panel strong{display:inline-flex;margin-top:12px;background:#e7f7ef;color:#0d6b3f;border-radius:999px;padding:7px 12px;font-size:14px}.id-card-back-qr-panel span{display:block;margin-top:6px;font-size:22px;line-height:1.05;font-weight:900}.id-card-back-footer{padding:0 24px 32px;text-align:center;color:#cbd5e1;font-size:12px;line-height:1.45}.id-card-flip-button{display:none}table.print-generic{width:100%;border-collapse:collapse;margin:12px 0}table.print-generic th,table.print-generic td{border-bottom:1px solid #e5e7eb;padding:8px 10px;text-align:left}table.print-generic th:last-child,table.print-generic td:last-child{text-align:right}@media print{body{background:#fff}.official-document{box-shadow:none;margin:0 auto;border:none;min-height:100vh}.testimonial-border{min-height:calc(100vh - 84px)}}@media(max-width:720px){.official-document{padding:24px}.doc-info-grid,.doc-summary-strip,.signature-row{grid-template-columns:1fr}.testimonial-row{grid-template-columns:28px 1fr}.testimonial-row span{grid-column:2}}
    .service-agreement-document{font-family:Georgia,'Times New Roman',serif;color:#1f2933;line-height:1.55;max-width:800px;margin:0 auto;padding:0 6px}
    .service-agreement-document h1{text-align:center;font-size:20px;letter-spacing:.03em;margin:0 0 4px}
    .service-agreement-document .sa-subtitle{text-align:center;color:#52606d;margin-bottom:20px}
    .service-agreement-document h2{font-size:15px;color:#1a365d;margin:20px 0 8px;page-break-inside:avoid}
    .service-agreement-document p{margin:6px 0}
    .service-agreement-document .sa-fill{border-bottom:1px solid #94a3b8;padding:0 4px;font-weight:600}
    .service-agreement-document .sa-input{display:none}
    .service-agreement-document .sa-signature-block{margin-top:32px}
    .service-agreement-document .sa-sig-row{display:flex;align-items:center;gap:12px;border-bottom:1px solid #cbd5e1;padding:10px 0}
    .service-agreement-document .sa-sig-label{flex:0 0 160px;color:#52606d;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
    .service-agreement-document .sa-signature-img{max-height:60px;object-fit:contain}
    .transcript-document .doc-summary-strip{grid-template-columns:repeat(5,1fr)}
    .invoice-document{--invoice-accent:${t.accent_color};font-family:Arial,Helvetica,sans-serif;color:#1e293b}
    .invoice-doc-header{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;border-bottom:2px solid var(--invoice-accent);padding-bottom:16px;margin-bottom:18px}
    .invoice-doc-brand{display:flex;gap:14px;align-items:flex-start}
    .invoice-doc-logo{width:56px;height:56px;border-radius:14px;overflow:hidden;display:grid;place-items:center;background:#f1f5f9;flex:0 0 auto}
    .invoice-doc-logo img{width:100%;height:100%;object-fit:contain}
    .invoice-doc-logo span{font-weight:900;color:var(--invoice-accent)}
    .invoice-doc-brand strong{display:block;font-size:16px;color:#0f172a;margin-bottom:3px}
    .invoice-doc-brand span{display:block;font-size:11.5px;color:#64748b;line-height:1.5}
    .invoice-doc-title-block{text-align:right}
    .invoice-doc-title-block h2{margin:0 0 8px;font-size:22px;letter-spacing:.04em;color:#0f172a}
    .invoice-doc-meta-table{border-collapse:collapse;margin-left:auto}
    .invoice-doc-meta-table td{padding:4px 10px;font-size:12px;border-bottom:1px solid #e2e8f0;text-align:left}
    .invoice-doc-meta-table td:first-child{color:#64748b}
    .invoice-doc-meta-table td:last-child{font-weight:700;color:#0f172a}
    .invoice-doc-cards{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px}
    .invoice-doc-card,.invoice-doc-panel{border:1px solid #e2e8f0;border-radius:10px;overflow:hidden}
    .invoice-doc-card-head,.invoice-doc-panel-head{padding:8px 14px;font-weight:800;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#fff;background:#0f172a}
    .invoice-doc-card-head.accent{background:var(--invoice-accent)}
    .invoice-doc-card-body,.invoice-doc-panel-body{padding:12px 14px}
    .invoice-doc-card-body div{display:flex;justify-content:space-between;gap:10px;padding:4px 0;font-size:12.5px;border-bottom:1px dashed #f1f5f9}
    .invoice-doc-card-body label{color:#64748b}
    .invoice-doc-card.summary .invoice-doc-summary-total{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:8px;margin-bottom:6px;border-bottom:1px solid #e2e8f0}
    .invoice-doc-summary-total span{font-size:12px;color:#64748b;text-transform:uppercase}
    .invoice-doc-summary-total strong{font-size:20px;color:var(--invoice-accent)}
    .invoice-doc-card.summary .row{display:flex;justify-content:space-between;font-size:12.5px;padding:4px 0;color:#475569}
    .invoice-doc-card.summary .row.balance{font-weight:800;color:#0f172a;border-top:1px solid #e2e8f0;margin-top:4px;padding-top:8px}
    .invoice-doc-items thead th{background:#0f172a;color:#fff}
    .invoice-doc-items tbody tr:nth-child(even){background:#f8fafc}
    .invoice-doc-items td,.invoice-doc-items th{text-align:left}
    .invoice-doc-items td:first-child,.invoice-doc-items th:first-child,.invoice-doc-items td:nth-child(3),.invoice-doc-items th:nth-child(3){text-align:center}
    .invoice-doc-items td:last-child,.invoice-doc-items th:last-child,.invoice-doc-items td:nth-child(4),.invoice-doc-items th:nth-child(4){text-align:right}
    .invoice-doc-total-row td{background:#f0fdfa;background:color-mix(in srgb,var(--invoice-accent) 12%,#ffffff);font-weight:900;font-size:14px;color:var(--invoice-accent);border-top:2px solid var(--invoice-accent);text-align:right}
    .invoice-doc-total-row td:first-child{text-align:left}
    .invoice-totals{margin:10px 0 18px;font-family:Arial,sans-serif}
    .invoice-totals .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #e2e8f0;font-size:13px;color:#334155}
    .invoice-totals .row.discount span:last-child{color:#16a34a}
    .invoice-doc-panel.note{border-color:#fde68a}
    .invoice-doc-panel.note .invoice-doc-panel-head{background:#b45309}
    .invoice-doc-panel-body.muted{color:#64748b;font-size:12.5px}
    .invoice-doc-panel-body ul{margin:0 0 10px;padding-left:18px;font-size:12.5px;color:#475569;line-height:1.6}
    .invoice-doc-thanks{font-weight:700;font-size:12.5px;color:#0f172a;margin:0}
    .invoice-account-number{letter-spacing:.04em;color:var(--invoice-accent)}
    .invoice-doc-portal-link{display:inline-block;margin-top:8px;font-size:12px;font-weight:700;color:var(--invoice-accent);text-decoration:none}
    .invoice-doc-signoff{margin-top:34px;display:flex;justify-content:flex-end}
    .invoice-doc-signature{text-align:center}
    .invoice-doc-signature img{display:block;height:40px;max-width:160px;object-fit:contain;margin:0 auto 4px}
    .invoice-doc-signature-blank{display:block;height:40px;border-bottom:1px solid #94a3b8;width:160px;margin:0 auto 4px}
    .invoice-doc-signature span{display:block;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.04em}
    .invoice-doc-signature strong{display:block;font-size:12px;color:#0f172a;margin-top:2px}
    ${tableStyleCss}
    ${watermarkCss}
  `;
}

export function OfficialDocHeader({ school, title }) {
  const brand = resolveSchoolBrand(school);
  return (
    <header className="official-doc-header">
      <div className="official-doc-logo">
        {brand.logo ? <img src={brand.logo} alt={`${brand.name} logo`} /> : <span>{brand.initials}</span>}
      </div>
      <h1>{brand.name}</h1>
      {brand.motto ? <p className="official-doc-motto">{brand.motto}</p> : null}
      <p>{school?.address || brand.code || "Official School Record"}</p>
      <h2 className="official-doc-title">{title}</h2>
    </header>
  );
}

/** Opens a popup (or, if popups are blocked, a hidden iframe) containing a
 * clone of the given element's markup and triggers the browser's print
 * dialog on load - this app's "Download as PDF" is the browser's own
 * Print -> Save as PDF, there is no server-side PDF generator. Optional
 * `theme` (a DocumentTheme payload) drives colors/fonts/page setup via
 * documentStylesForExport(); omit it to fall back to the shared defaults. */
export function openPrintableDocument(elementId, title, theme) {
  const element = document.getElementById(elementId);
  if (!element) {
    throw new Error("The document preview is not ready yet.");
  }
  const content = `<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /><title>${escapePrintableHtml(title)}</title><style>${documentStylesForExport(theme)}</style></head><body>${element.outerHTML}<script>window.onload=()=>{window.focus();window.print();};</script></body></html>`;

  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=980,height=1200");
  if (printWindow) {
    printWindow.document.write(content);
    printWindow.document.close();
    return;
  }

  const iframe = document.createElement("iframe");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.overflow = "hidden";
  document.body.appendChild(iframe);
  const iframeDoc = iframe.contentWindow?.document;
  if (!iframeDoc) {
    iframe.remove();
    throw new Error("Unable to open print preview.");
  }
  iframeDoc.open();
  iframeDoc.write(content);
  iframeDoc.close();
  iframe.onload = () => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    setTimeout(() => iframe.remove(), 1000);
  };
}

/** Rasterizes the given element (via an SVG foreignObject -> canvas, no
 * external library) into a downloaded PNG, styled with the same
 * documentStylesForExport(theme) used by print/PDF output. */
export async function downloadPrintablePng(elementId, filename, title, theme) {
  const element = document.getElementById(elementId);
  if (!element) {
    throw new Error("The document preview is not ready yet.");
  }
  const clone = element.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
  const rect = element.getBoundingClientRect();
  const width = Math.max(850, Math.ceil(rect.width || element.scrollWidth || 850));
  const height = Math.max(1100, Math.ceil(element.scrollHeight || rect.height || 1100));
  const html = `<div xmlns="http://www.w3.org/1999/xhtml" style="width:${width}px;background:#ffffff;">${clone.outerHTML}</div>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><foreignObject width="100%" height="100%"><style>${documentStylesForExport(theme)}</style>${html}</foreignObject></svg>`;
  const svgUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  const image = new Image();
  const pngUrl = await new Promise((resolve, reject) => {
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const scale = 2;
        canvas.width = width * scale;
        canvas.height = height * scale;
        const context = canvas.getContext("2d");
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.scale(scale, scale);
        context.drawImage(image, 0, 0);
        canvas.toBlob((blob) => {
          if (!blob) {
            reject(new Error("Could not render PNG."));
            return;
          }
          resolve(URL.createObjectURL(blob));
        }, "image/png");
      } catch (renderError) {
        reject(renderError);
      }
    };
    image.onerror = () => reject(new Error(`Could not render ${title || "document"} as PNG.`));
    image.src = svgUrl;
  });
  URL.revokeObjectURL(svgUrl);
  const link = document.createElement("a");
  link.href = pngUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(pngUrl);
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
    clock: [
      <path key="1" d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />,
      <path key="2" d="M12 7v5l3.5 2" />,
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

export function Spinner({ size = 14 }) {
  return (
    <svg className="inline-spinner" width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// Shared button for anything that fires an async request: shows an inline
// spinner + swapped label and disables itself while `loading` is true.
export function LoadingButton({
  loading = false,
  disabled = false,
  loadingText,
  spinnerSize = 14,
  type = "button",
  children,
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={Boolean(loading) || Boolean(disabled)}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <Spinner size={spinnerSize} />
          {loadingText ?? children}
        </>
      ) : (
        children
      )}
    </button>
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

export function TimetableGridTable({ entries = [], days = [], renderCell, emptyMessage = "No timetable entries yet." }) {
  const timeSlots = useMemo(() => {
    const seen = new Map();
    entries.forEach((entry) => {
      const key = `${entry.start_time}|${entry.end_time}`;
      if (!seen.has(key)) {
        seen.set(key, { start_time: entry.start_time, end_time: entry.end_time });
      }
    });
    return Array.from(seen.values()).sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
  }, [entries]);

  if (!entries.length) {
    return <p className="panel-empty">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrap timetable-grid-wrap">
      <table className="data-table timetable-grid-table">
        <thead>
          <tr>
            <th className="timetable-grid-time-col">Time</th>
            {days.map((day) => (
              <th key={day.value}>{day.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {timeSlots.map((slot) => (
            <tr key={`${slot.start_time}-${slot.end_time}`}>
              <td className="timetable-grid-time-col">{slot.start_time} - {slot.end_time}</td>
              {days.map((day) => {
                const cellEntries = entries.filter(
                  (entry) =>
                    String(entry.day_of_week) === String(day.value) &&
                    entry.start_time === slot.start_time &&
                    entry.end_time === slot.end_time
                );
                return (
                  <td key={day.value} className="timetable-grid-cell">
                    {cellEntries.length ? (
                      cellEntries.map((entry) => (
                        <div key={entry.id} className="timetable-grid-entry">
                          {renderCell(entry)}
                        </div>
                      ))
                    ) : (
                      <span className="timetable-grid-blank">-</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
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
  groups = [],
  onLoadGroupDetail,
  onSendGroupMessage,
  onMarkGroupRead,
  canManageGroups = false,
  classOptions = [],
  onCreateGroup,
  onUpdateGroup,
  onDeleteGroup,
  onAddGroupMembers,
  onRemoveGroupMember,
  onAddGroupClass,
  onSearchStudentOptions,
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

  // ── Groups (view + chat) ──────────────────────────────────────────
  const [chatMode, setChatMode] = useState("contact"); // "contact" | "group"
  const [activeGroupId, setActiveGroupId] = useState("");
  const [groupDetail, setGroupDetail] = useState(null);
  const [loadingGroupDetail, setLoadingGroupDetail] = useState(false);
  const [groupComposeBody, setGroupComposeBody] = useState("");
  const [groupComposeAttachments, setGroupComposeAttachments] = useState([]);
  const [groupComposeIsAnnouncement, setGroupComposeIsAnnouncement] = useState(false);
  const [groupSending, setGroupSending] = useState(false);
  const [groupComposeError, setGroupComposeError] = useState("");
  const groupAttachmentInputRef = useRef(null);
  const groupChatBodyRef = useRef(null);

  // ── Groups management (admin only) ────────────────────────────────
  const [showGroupsManagement, setShowGroupsManagement] = useState(false);
  const [groupModalMode, setGroupModalMode] = useState(null); // null | "create" | <group object>
  const [openGroupMenuId, setOpenGroupMenuId] = useState("");
  const [groupActionError, setGroupActionError] = useState("");

  // ── Voice notes ────────────────────────────────────────────────────
  const [isRecordingVoice, setIsRecordingVoice] = useState(false);
  const [voiceRecordError, setVoiceRecordError] = useState("");
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);

  const loadGroupDetail = useCallback(async (groupId) => {
    if (!groupId || !onLoadGroupDetail) {
      setGroupDetail(null);
      return;
    }
    setLoadingGroupDetail(true);
    try {
      const detail = await onLoadGroupDetail(groupId);
      setGroupDetail(detail);
    } catch (err) {
      setGroupComposeError(err.message || "Could not load group.");
    } finally {
      setLoadingGroupDetail(false);
    }
  }, [onLoadGroupDetail]);

  useEffect(() => {
    if (chatMode === "group" && activeGroupId) loadGroupDetail(activeGroupId);
  }, [chatMode, activeGroupId, loadGroupDetail]);

  useEffect(() => {
    if (chatMode !== "group" || !activeGroupId || !refreshIntervalMs) return undefined;
    const pollId = window.setInterval(() => {
      if (document.visibilityState === "visible") loadGroupDetail(activeGroupId);
    }, refreshIntervalMs);
    return () => window.clearInterval(pollId);
  }, [chatMode, activeGroupId, refreshIntervalMs, loadGroupDetail]);

  useEffect(() => {
    if (groupChatBodyRef.current) groupChatBodyRef.current.scrollTop = groupChatBodyRef.current.scrollHeight;
  }, [groupDetail?.messages?.length]);

  const activeGroup = groups.find((group) => group.id === activeGroupId) || null;
  const totalGroupUnread = groups.reduce((sum, group) => sum + (group.unread || 0), 0);

  const filteredGroups = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return groups.filter((group) => {
      const matchesFilter = filter !== "unread" || group.unread > 0;
      const haystack = `${group.name} ${group.class_label || ""} ${group.description || ""} ${group.last_message?.body || ""}`.toLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
  }, [groups, searchTerm, filter]);

  const openGroup = (groupId) => {
    setChatMode("group");
    setActiveGroupId(groupId);
    setSidebarOpen(false);
    onMarkGroupRead?.(groupId).catch(() => {});
  };

  const handleGroupAttachmentChange = (event) => {
    const files = Array.from(event.target.files || []);
    setGroupComposeAttachments((previous) => [...previous, ...files].slice(0, 5));
    setGroupComposeError("");
  };

  const handleGroupComposeSubmit = async (event) => {
    event.preventDefault();
    if (!onSendGroupMessage || !activeGroupId) return;
    if (!groupComposeBody.trim() && groupComposeAttachments.length === 0) {
      setGroupComposeError("Add a message or attachment before sending.");
      return;
    }
    setGroupComposeError("");
    setGroupSending(true);
    try {
      await onSendGroupMessage(activeGroupId, {
        body: groupComposeBody.trim(),
        is_announcement: groupComposeIsAnnouncement,
        attachments: groupComposeAttachments,
      });
      setGroupComposeBody("");
      setGroupComposeAttachments([]);
      setGroupComposeIsAnnouncement(false);
      if (groupAttachmentInputRef.current) groupAttachmentInputRef.current.value = "";
      await loadGroupDetail(activeGroupId);
    } catch (err) {
      setGroupComposeError(err.message || "Could not send message.");
    } finally {
      setGroupSending(false);
    }
  };

  const handleToggleVoiceRecording = async () => {
    setVoiceRecordError("");
    if (isRecordingVoice) {
      mediaRecorderRef.current?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceRecordError("Voice recording is not supported on this device/browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recordedChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
        const file = new File([blob], `voice-note-${Date.now()}.webm`, { type: "audio/webm" });
        setGroupComposeAttachments((previous) => [...previous, file].slice(0, 5));
        setIsRecordingVoice(false);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecordingVoice(true);
    } catch (err) {
      setVoiceRecordError("Microphone access was denied or is unavailable.");
    }
  };

  const handleToggleGroupActive = async (group) => {
    if (!onUpdateGroup) return;
    setGroupActionError("");
    setOpenGroupMenuId("");
    try {
      await onUpdateGroup(group.id, { is_active: !group.is_active });
    } catch (err) {
      setGroupActionError(err.message || "Could not update group.");
    }
  };

  const handleDeleteGroup = async (group) => {
    if (!onDeleteGroup) return;
    setOpenGroupMenuId("");
    if (typeof window !== "undefined" && !window.confirm(`Delete "${group.name}"? This cannot be undone.`)) return;
    setGroupActionError("");
    try {
      await onDeleteGroup(group.id);
      if (activeGroupId === group.id) {
        setActiveGroupId("");
        setGroupDetail(null);
      }
    } catch (err) {
      setGroupActionError(err.message || "Could not delete group.");
    }
  };

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
    setChatMode("contact");
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
          <button type="button" className={filter === "groups" ? "active" : ""} onClick={() => setFilter("groups")}>Groups {totalGroupUnread > 0 && <b>{totalGroupUnread}</b>}</button>
        </div>

        {canManageGroups ? (
          <div className="chat-groups-manage">
            <button
              type="button"
              className={`chat-groups-manage-toggle${showGroupsManagement ? " open" : ""}`}
              onClick={() => setShowGroupsManagement((previous) => !previous)}
            >
              <span>Manage Groups</span>
              <ChevronDown size={16} className="chat-groups-manage-chevron" />
            </button>
            <div className={`chat-groups-manage-panel${showGroupsManagement ? " open" : ""}`}>
              <button type="button" className="chat-groups-new-btn" onClick={() => setGroupModalMode("create")}>+ New Group</button>
              {groupActionError ? <p className="form-feedback error compact">{groupActionError}</p> : null}
              <div className="chat-groups-manage-list">
                {groups.length === 0 ? (
                  <p className="chat-empty-hint">No groups yet. Create one to get started.</p>
                ) : (
                  groups.map((group) => (
                    <div key={group.id} className="chat-groups-manage-row">
                      <button type="button" className="chat-groups-manage-row-main" onClick={() => openGroup(group.id)}>
                        <span className={`chat-groups-status-dot${group.is_active ? " active" : ""}`} />
                        <span className="chat-groups-manage-row-text">
                          <span className="chat-groups-manage-row-name">{group.name}</span>
                          <small>{group.class_label || "Custom group"} · {group.member_count} member{group.member_count === 1 ? "" : "s"}</small>
                        </span>
                      </button>
                      <div className="chat-groups-manage-row-actions">
                        <button type="button" onClick={() => setOpenGroupMenuId((current) => (current === group.id ? "" : group.id))} aria-label="Group actions">
                          <MoreVertical size={16} />
                        </button>
                        {openGroupMenuId === group.id ? (
                          <div className="chat-groups-menu">
                            <button type="button" onClick={() => { setGroupModalMode(group); setOpenGroupMenuId(""); }}>Edit</button>
                            <button type="button" onClick={() => handleToggleGroupActive(group)}>{group.is_active ? "Archive" : "Activate"}</button>
                            <button type="button" className="danger" onClick={() => handleDeleteGroup(group)}>Delete</button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div className="chat-thread-list">
          {filter === "groups" ? (
            filteredGroups.length === 0 ? (
              <p className="chat-empty-hint">No groups yet.</p>
            ) : (
              filteredGroups.map((group) => (
                <button
                  key={group.id}
                  type="button"
                  className={`chat-thread-item${chatMode === "group" && activeGroupId === group.id ? " active" : ""}${group.unread ? " unread" : ""}`}
                  onClick={() => openGroup(group.id)}
                >
                  <span className="chat-thread-avatar group-avatar" data-letter={group.name.slice(0, 1).toUpperCase()}>{group.name.slice(0, 1).toUpperCase()}</span>
                  <span className="chat-thread-body">
                    <span className="chat-thread-name">{group.name}</span>
                    <span className="chat-thread-preview">
                      {group.last_message ? (group.last_message.body || "Attachment") : `${group.member_count} member${group.member_count === 1 ? "" : "s"}`}
                    </span>
                  </span>
                  <span className="chat-thread-meta">
                    {group.last_message ? <span className="chat-thread-time">{formatDate(group.last_message.created_at)}</span> : null}
                    <small className="chat-thread-member-count">{group.member_count} members</small>
                    {group.unread > 0 ? <span className="chat-thread-badge">{group.unread}</span> : null}
                  </span>
                </button>
              ))
            )
          ) : filteredThreads.length === 0 ? (
            <p className="chat-empty-hint">No conversations found.</p>
          ) : (
            filteredThreads.map((thread) => (
              <button
                key={thread.key}
                type="button"
                className={`chat-thread-item${chatMode === "contact" && activeThread?.key === thread.key ? " active" : ""}${thread.unread ? " unread" : ""}`}
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
          {chatMode === "group" && activeGroup ? (
            <div className="chat-head-contact">
              <span className="chat-head-avatar group-avatar" data-letter={activeGroup.name.slice(0,1).toUpperCase()}>{activeGroup.name.slice(0,1).toUpperCase()}</span>
              <div>
                <strong>{activeGroup.name}</strong>
                <small>{activeGroup.member_count} member{activeGroup.member_count === 1 ? "" : "s"}{activeGroup.class_label ? ` · ${activeGroup.class_label}` : ""}</small>
              </div>
            </div>
          ) : chatMode === "contact" && activeThread ? (
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
            {chatMode === "contact" && activeThread?.unread > 0 && (
              <button type="button" className="chat-icon-btn" onClick={markThreadRead} title="Mark all read">
                <CheckCheck size={18} />
              </button>
            )}
          </div>
        </header>

        {/* Message body */}
        {chatMode === "group" ? (
        <div className="chat-body" ref={groupChatBodyRef}>
          {loadingGroupDetail && !groupDetail ? (
            <div className="chat-empty-state"><span className="chat-empty-icon">💬</span><p>Loading messages…</p></div>
          ) : (groupDetail?.messages || []).length ? (
            groupDetail.messages.map((message) => (
              <div key={message.id} className={`chat-bubble-wrap${message.outgoing ? " out" : " in"}`}>
                {!message.outgoing && (
                  <span className="chat-bubble-avatar" data-letter={(message.sender_name || "?").slice(0,1).toUpperCase()}>
                    {(message.sender_name || "?").slice(0,1).toUpperCase()}
                  </span>
                )}
                <div className={`chat-bubble${message.outgoing ? " out" : " in"}${message.is_announcement ? " announcement" : ""}`}>
                  {message.is_announcement ? <span className="chat-bubble-announcement-tag"><Megaphone size={12} /> Announcement</span> : null}
                  {!message.outgoing && <p className="chat-bubble-subject">{message.sender_name}</p>}
                  {message.body && <p className="chat-bubble-text">{message.body}</p>}
                  {(message.attachments || []).length > 0 && (
                    <div className="chat-bubble-attachments">
                      {message.attachments.map((att, idx) => (
                        <MessageAttachment key={`${attachmentUrl(att) || attachmentLabel(att)}-${idx}`} attachment={att} index={idx} />
                      ))}
                    </div>
                  )}
                  <div className="chat-bubble-foot">
                    <span className="chat-bubble-time">{formatDate(message.created_at)}</span>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="chat-empty-state">
              <span className="chat-empty-icon">💬</span>
              <p>{activeGroup ? "No messages yet — say hello!" : "Select a group to view the conversation."}</p>
            </div>
          )}
        </div>
        ) : (
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
        )}

        {/* Composer */}
        {chatMode === "group" ? (
          onSendGroupMessage && activeGroupId ? (
            <form className="chat-composer" onSubmit={handleGroupComposeSubmit}>
              {groupComposeAttachments.length > 0 && (
                <div className="chat-attachment-preview">
                  {groupComposeAttachments.map((file, idx) => (
                    <span key={`${file.name}-${file.size}-${idx}`} className="chat-attachment-chip">
                      <Paperclip size={11} />
                      {file.name}
                      <button type="button" onClick={() => setGroupComposeAttachments((p) => p.filter((f) => f !== file))}><XIcon size={10}/></button>
                    </span>
                  ))}
                </div>
              )}
              {(groupComposeError || voiceRecordError) && (
                <div className="chat-composer-feedback error">{groupComposeError || voiceRecordError}</div>
              )}
              {canManageGroups ? (
                <label className="chat-announcement-toggle">
                  <input type="checkbox" checked={groupComposeIsAnnouncement} onChange={(e) => setGroupComposeIsAnnouncement(e.target.checked)} />
                  <Megaphone size={13} /> Send as announcement
                </label>
              ) : null}
              <div className="chat-composer-row">
                <textarea
                  className="chat-composer-input"
                  value={groupComposeBody}
                  onChange={(e) => setGroupComposeBody(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleGroupComposeSubmit(e); } }}
                  placeholder={`Message ${activeGroup?.name || "group"}…`}
                  rows={1}
                />
                <label className="chat-composer-icon-btn" title="Attach file" aria-label="Attach file">
                  <Paperclip size={20} />
                  <input ref={groupAttachmentInputRef} type="file" multiple onChange={handleGroupAttachmentChange} style={{display:"none"}} />
                </label>
                <button
                  type="button"
                  className={`chat-composer-icon-btn${isRecordingVoice ? " recording" : ""}`}
                  onClick={handleToggleVoiceRecording}
                  title={isRecordingVoice ? "Stop recording" : "Record voice note"}
                  aria-label="Record voice note"
                >
                  <Mic size={20} />
                </button>
                <button type="submit" className="chat-send-btn" disabled={groupSending} aria-label="Send" title="Send (Enter)">
                  {groupSending ? <span className="chat-send-spinner" /> : <Send size={18} />}
                </button>
              </div>
            </form>
          ) : null
        ) : onComposeSubmit ? (
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

      {groupModalMode ? (
        <GroupFormModal
          group={groupModalMode === "create" ? null : groupModalMode}
          classOptions={classOptions}
          onSearchStudentOptions={onSearchStudentOptions}
          onCreateGroup={onCreateGroup}
          onUpdateGroup={onUpdateGroup}
          onAddGroupMembers={onAddGroupMembers}
          onRemoveGroupMember={onRemoveGroupMember}
          onAddGroupClass={onAddGroupClass}
          onClose={() => setGroupModalMode(null)}
        />
      ) : null}
    </article>
  );
}

function GroupFormModal({
  group,
  classOptions = [],
  onSearchStudentOptions,
  onCreateGroup,
  onUpdateGroup,
  onAddGroupMembers,
  onRemoveGroupMember,
  onAddGroupClass,
  onClose,
}) {
  const isEdit = Boolean(group?.id);
  const [name, setName] = useState(group?.name || "");
  const [description, setDescription] = useState(group?.description || "");
  const [classId, setClassId] = useState(group?.school_class || "");
  const [members, setMembers] = useState(group?.members || []);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedNewIds, setSelectedNewIds] = useState([]);
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");

  const memberUserIds = useMemo(() => new Set(members.map((m) => m.id)), [members]);

  const runSearch = useCallback(async () => {
    if (!onSearchStudentOptions) return;
    setSearching(true);
    try {
      const results = await onSearchStudentOptions({ q: searchTerm, class_id: "" });
      setSearchResults(results || []);
    } catch (err) {
      setError(err.message || "Could not search students.");
    } finally {
      setSearching(false);
    }
  }, [onSearchStudentOptions, searchTerm]);

  useEffect(() => {
    runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm]);

  const toggleSelectNew = (studentProfileId) => {
    setSelectedNewIds((previous) =>
      previous.includes(studentProfileId) ? previous.filter((id) => id !== studentProfileId) : [...previous, studentProfileId]
    );
  };

  const handleSave = async (event) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Give this group a name.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      if (isEdit) {
        await onUpdateGroup?.(group.id, { name: name.trim(), description, school_class_id: classId || null });
        if (selectedNewIds.length) {
          await onAddGroupMembers?.(group.id, selectedNewIds);
        }
        onClose();
      } else {
        await onCreateGroup?.({ name: name.trim(), description, school_class_id: classId || null, student_profile_ids: selectedNewIds });
        onClose();
      }
    } catch (err) {
      setError(err.message || "Could not save group.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddSelected = async () => {
    if (!isEdit || !selectedNewIds.length) return;
    setBusyAction("add-selected");
    setError("");
    try {
      const result = await onAddGroupMembers?.(group.id, selectedNewIds);
      if (result?.group?.members) setMembers(result.group.members);
      setSelectedNewIds([]);
    } catch (err) {
      setError(err.message || "Could not add students.");
    } finally {
      setBusyAction("");
    }
  };

  const handleAddClass = async () => {
    if (!isEdit || !classId) return;
    setBusyAction("add-class");
    setError("");
    try {
      const result = await onAddGroupClass?.(group.id, classId);
      if (result?.group?.members) setMembers(result.group.members);
    } catch (err) {
      setError(err.message || "Could not add the class.");
    } finally {
      setBusyAction("");
    }
  };

  const handleRemoveMember = async (userId) => {
    if (!isEdit) return;
    setBusyAction(`remove-${userId}`);
    setError("");
    try {
      const result = await onRemoveGroupMember?.(group.id, userId);
      if (result?.group?.members) setMembers(result.group.members);
    } catch (err) {
      setError(err.message || "Could not remove member.");
    } finally {
      setBusyAction("");
    }
  };

  return (
    <div className="chat-groups-modal-backdrop" role="presentation" onClick={onClose}>
      <article className="chat-groups-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header className="chat-groups-modal-head">
          <h3>{isEdit ? "Edit Group" : "Create New Group"}</h3>
          <button type="button" className="chat-sidebar-close-btn" onClick={onClose} aria-label="Close"><XIcon size={16} /></button>
        </header>

        <form className="chat-groups-modal-body" onSubmit={handleSave}>
          <label className="panel-field">
            Group Name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Science Stars" required />
          </label>
          <label className="panel-field">
            Group Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="Optional description" />
          </label>
          <label className="panel-field">
            Select Class
            <select value={classId} onChange={(e) => setClassId(e.target.value)}>
              <option value="">Custom group (no class)</option>
              {classOptions.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
          </label>
          {isEdit && classId ? (
            <button type="button" className="btn-secondary" onClick={handleAddClass} disabled={busyAction === "add-class"}>
              {busyAction === "add-class" ? "Adding class…" : "+ Add entire class to this group"}
            </button>
          ) : null}

          {isEdit && members.length > 0 ? (
            <div className="chat-groups-modal-members">
              <p className="panel-sub">Current members ({members.length})</p>
              <div className="chat-groups-member-chip-list">
                {members.map((member) => (
                  <span key={member.id} className="chat-groups-member-chip">
                    {member.name}
                    <button type="button" onClick={() => handleRemoveMember(member.id)} disabled={busyAction === `remove-${member.id}`} aria-label={`Remove ${member.name}`}>
                      <XIcon size={11} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          <label className="panel-field">
            Search Students
            <input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search by name or Student ID" />
          </label>
          <div className="chat-groups-student-picker">
            {searching ? (
              <p className="panel-empty compact">Searching…</p>
            ) : searchResults.length === 0 ? (
              <p className="panel-empty compact">No students found.</p>
            ) : (
              searchResults
                .filter((student) => !memberUserIds.has(student.user_id))
                .map((student) => (
                  <label key={student.student_profile_id} className="chat-groups-student-option">
                    <input
                      type="checkbox"
                      checked={selectedNewIds.includes(student.student_profile_id)}
                      onChange={() => toggleSelectNew(student.student_profile_id)}
                    />
                    <span>{student.name}</span>
                    <small>{student.student_id}{student.class_label ? ` · ${student.class_label}` : ""}</small>
                  </label>
                ))
            )}
          </div>
          {isEdit ? (
            <button type="button" className="btn-secondary" onClick={handleAddSelected} disabled={!selectedNewIds.length || busyAction === "add-selected"}>
              {busyAction === "add-selected" ? "Adding…" : `Add Selected Students${selectedNewIds.length ? ` (${selectedNewIds.length})` : ""}`}
            </button>
          ) : null}

          {error ? <p className="form-feedback error">{error}</p> : null}

          <div className="chat-groups-modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save Group"}</button>
          </div>
        </form>
      </article>
    </div>
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
  const [pushPermission, setPushPermission] = useState(() =>
    typeof window !== "undefined" && "Notification" in window ? window.Notification.permission : "unsupported"
  );
  const [pushBusy, setPushBusy] = useState(false);
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

  const handleEnableNotifications = async () => {
    if (pushBusy) return;
    setPushBusy(true);
    try {
      const permission = await window.schoolDomPWA?.requestNotifications?.();
      if (permission) setPushPermission(permission);
    } finally {
      setPushBusy(false);
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
                    {pushPermission === "granted" ? (
                      <span className="table-action ghost" aria-live="polite">Notifications on</span>
                    ) : pushPermission === "denied" ? (
                      <span className="table-action ghost" title="Notifications are blocked in your browser settings">
                        Notifications blocked
                      </span>
                    ) : pushPermission === "unsupported" ? null : (
                      <button type="button" className="table-action" disabled={pushBusy} onClick={handleEnableNotifications}>
                        {pushBusy ? "Enabling..." : "Enable browser notifications"}
                      </button>
                    )}
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

/**
 * PhoneCountryInput — phone field with a country-code prefix picker.
 *
 * Props:
 *   countries  – array of { code, name, flag, dial_code } from /api/app/countries/
 *   value      – controlled full phone string (e.g. "+2348012345678")
 *   onChange   – called with the new full phone string
 *   defaultCountryCode – ISO alpha-2 to pre-select when value is empty (e.g. "NG")
 *   disabled, placeholder, className
 */
export function PhoneCountryInput({
  countries = [],
  value = "",
  onChange,
  defaultCountryCode = "NG",
  disabled = false,
  placeholder = "Phone number",
  className = "",
}) {
  const inferCountry = useCallback(
    (raw) => {
      if (!raw) return defaultCountryCode || "NG";
      const sorted = [...countries].sort((a, b) => b.dial_code.length - a.dial_code.length);
      for (const c of sorted) {
        if (c.dial_code && raw.startsWith(c.dial_code)) return c.code;
      }
      return defaultCountryCode || "NG";
    },
    [countries, defaultCountryCode]
  );

  const stripDialCode = useCallback(
    (raw, code) => {
      const country = countries.find((c) => c.code === code);
      const dial = country?.dial_code || "";
      if (dial && raw.startsWith(dial)) return raw.slice(dial.length).replace(/^\s+/, "");
      return raw.replace(/^\+\d{1,4}\s?/, "");
    },
    [countries]
  );

  const [selectedCode, setSelectedCode] = useState(() => inferCountry(value));
  const [localNumber, setLocalNumber] = useState(() => stripDialCode(value, inferCountry(value)));

  useEffect(() => {
    const code = inferCountry(value);
    setSelectedCode(code);
    setLocalNumber(stripDialCode(value, code));
  }, [value, inferCountry, stripDialCode]);

  const selectedCountry = countries.find((c) => c.code === selectedCode);
  const dialCode = selectedCountry?.dial_code || "";

  const handleCountryChange = (event) => {
    const code = event.target.value;
    setSelectedCode(code);
    const country = countries.find((c) => c.code === code);
    const dial = country?.dial_code || "";
    onChange?.(dial ? `${dial}${localNumber}` : localNumber);
  };

  const handleNumberChange = (event) => {
    const digits = event.target.value.replace(/[^\d\s\-().]/g, "");
    setLocalNumber(digits);
    onChange?.(dialCode ? `${dialCode}${digits}` : digits);
  };

  return (
    <div className={`phone-country-input${className ? ` ${className}` : ""}`}>
      <select
        value={selectedCode}
        onChange={handleCountryChange}
        disabled={disabled}
        aria-label="Country code"
        className="phone-country-select"
      >
        {countries.map((c) => (
          <option key={c.code} value={c.code}>
            {c.dial_code}
          </option>
        ))}
      </select>
      <input
        type="tel"
        value={localNumber}
        onChange={handleNumberChange}
        placeholder={placeholder}
        disabled={disabled}
        className="phone-number-field"
      />
    </div>
  );
}
