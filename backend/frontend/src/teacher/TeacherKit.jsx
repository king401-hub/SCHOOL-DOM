// Shared building blocks for the redesigned teacher workspace ("Teacher Studio").
// Purely presentational + a few tiny hooks; nothing here talks to the API.
// Styles live in ./teacher-studio.css (scoped under .teacher-workspace-shell).
import { useCallback, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ motion */

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && Boolean(window.matchMedia?.(REDUCED_MOTION_QUERY).matches)
  );
  useEffect(() => {
    const query = window.matchMedia?.(REDUCED_MOTION_QUERY);
    if (!query) return undefined;
    const onChange = () => setReduced(query.matches);
    query.addEventListener?.("change", onChange);
    return () => query.removeEventListener?.("change", onChange);
  }, []);
  return reduced;
}

const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t));

/** Counts from the previously shown number to `target`, so an auto-refresh that
 *  changes a figure animates the difference instead of snapping. Honors
 *  prefers-reduced-motion. Non-numeric targets are returned untouched. */
export function useCountUp(target, { duration = 900, delay = 0 } = {}) {
  const reduced = usePrefersReducedMotion();
  const end = Number(target);
  const numeric = target !== null && target !== "" && target !== undefined && Number.isFinite(end);
  const shown = useRef(numeric && !reduced ? 0 : end);
  const [value, setValue] = useState(shown.current);

  useEffect(() => {
    if (!numeric) return undefined;
    if (reduced || shown.current === end) {
      shown.current = end;
      setValue(end);
      return undefined;
    }
    const from = shown.current;
    let frame = 0;
    let timer = 0;
    const startedAt = { current: 0 };
    const tick = (now) => {
      if (!startedAt.current) startedAt.current = now;
      const progress = Math.min(1, (now - startedAt.current) / duration);
      const next = from + (end - from) * easeOutExpo(progress);
      shown.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
      else {
        shown.current = end;
        setValue(end);
      }
    };
    timer = window.setTimeout(() => {
      frame = requestAnimationFrame(tick);
    }, delay);
    return () => {
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [end, numeric, reduced, duration, delay]);

  return numeric ? value : target;
}

export function CountUp({ value, decimals = 0, prefix = "", suffix = "", duration, delay, className }) {
  const shown = useCountUp(value, { duration, delay });
  if (typeof shown !== "number") return <span className={className}>{shown ?? "—"}</span>;
  const text = decimals > 0 ? shown.toFixed(decimals) : Math.round(shown).toLocaleString();
  return (
    <span className={className}>
      {prefix}
      {text}
      {suffix}
    </span>
  );
}

/** style prop that positions a child in a staggered entrance (see .ts-reveal). */
export const stagger = (index, step = 45) => ({ "--ts-i": Math.min(index, 10), "--ts-step": `${step}ms` });

/* ------------------------------------------------------------------- text */

export function greetingFor(date = new Date()) {
  const hour = date.getHours();
  if (hour < 5) return "Burning the midnight oil";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const TITLE_PATTERN = /^(mr|mrs|miss|ms|dr|prof|engr|chief|pastor|rev|alhaji|alhaja|sir|madam)\.?$/i;

/** "Mrs. Ada Okafor" -> "Mrs. Okafor"; "Ada Okafor" -> "Ada". */
export function friendlyName(fullName) {
  const parts = String(fullName || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "there";
  if (TITLE_PATTERN.test(parts[0]) && parts.length > 1) {
    const title = parts[0].replace(/\.?$/, ".");
    return `${title} ${parts[parts.length - 1]}`;
  }
  return parts[0];
}

export function formatLongDate(date = new Date()) {
  return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

export function timeAgo(value, now = Date.now()) {
  const then = new Date(value).getTime();
  if (!Number.isFinite(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(then).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Stable colour slot (0-7) for a subject/class name, so "Mathematics" is the
 *  same hue on the timetable, exam cards and chips. */
export function toneIndex(name) {
  const text = String(name || "").trim().toLowerCase();
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return hash % 8;
}

export function pluralize(count, singular, plural) {
  return `${count} ${Number(count) === 1 ? singular : plural || `${singular}s`}`;
}

/** "08:40" -> 520 (minutes since midnight); null when it isn't a time. */
export const toMinutes = (value) => {
  const [hours, minutes] = String(value || "").split(":").map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours * 60 + minutes : null;
};

/** "13:05" -> "1:05 pm" */
export const clock = (value) => {
  const minutes = toMinutes(value);
  if (minutes === null) return "";
  const hours24 = Math.floor(minutes / 60);
  const suffix = hours24 >= 12 ? "pm" : "am";
  const hours12 = hours24 % 12 || 12;
  return `${hours12}:${String(minutes % 60).padStart(2, "0")} ${suffix}`;
};

/* --------------------------------------------------------------- hotkeys */

/** Registers a keyboard shortcut; ignored while typing in a field. */
export function useHotkey(matcher, handler, { allowInInputs = false, enabled = true } = {}) {
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (event) => {
      const target = event.target;
      const typing =
        target instanceof HTMLElement &&
        (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      if (typing && !allowInInputs) return;
      if (event.defaultPrevented || event.isComposing) return;
      if (matcher(event)) latest.current(event);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [matcher, allowInInputs, enabled]);
}

/* ------------------------------------------------------------- primitives */

export function Kbd({ children }) {
  return <kbd className="ts-kbd">{children}</kbd>;
}

/** Page title block used at the top of every teacher page. */
export function PageHeader({ eyebrow, title, subtitle, icon: Icon, actions, meta, tone = "indigo", className = "" }) {
  return (
    <header className={`ts-page-header ${className}`.trim()} data-tone={tone}>
      <span className="ts-page-header__glow" aria-hidden="true" />
      <div className="ts-page-header__main">
        {Icon ? (
          <span className="ts-page-header__icon" aria-hidden="true">
            <Icon size={22} strokeWidth={1.8} />
          </span>
        ) : null}
        <div className="ts-page-header__text">
          {eyebrow ? <p className="ts-eyebrow">{eyebrow}</p> : null}
          <h1 className="ts-page-title">{title}</h1>
          {subtitle ? <p className="ts-page-sub">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="ts-page-header__actions">{actions}</div> : null}
      {meta ? <div className="ts-page-header__meta">{meta}</div> : null}
    </header>
  );
}

/** A titled surface. Use instead of a bare <article className="app-panel"> in new layouts. */
export function SectionCard({ title, subtitle, action, icon: Icon, children, className = "", as: Tag = "section", ...rest }) {
  return (
    <Tag className={`ts-card ${className}`.trim()} {...rest}>
      {title || action ? (
        <div className="ts-card__head">
          <div className="ts-card__titles">
            {Icon ? (
              <span className="ts-card__icon" aria-hidden="true">
                <Icon size={16} strokeWidth={2} />
              </span>
            ) : null}
            <div>
              {title ? <h2 className="ts-card__title">{title}</h2> : null}
              {subtitle ? <p className="ts-card__sub">{subtitle}</p> : null}
            </div>
          </div>
          {action ? <div className="ts-card__action">{action}</div> : null}
        </div>
      ) : null}
      {children}
    </Tag>
  );
}

export function Skeleton({ width, height, radius, className = "", style }) {
  return (
    <span
      className={`ts-skel ${className}`.trim()}
      aria-hidden="true"
      style={{ width, height, borderRadius: radius, ...style }}
    />
  );
}

export function SkeletonLines({ lines = 3, className = "" }) {
  return (
    <div className={`ts-skel-lines ${className}`.trim()} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} height={12} width={index === lines - 1 ? "58%" : "100%"} />
      ))}
    </div>
  );
}

/** Circular progress; animates from 0 on mount. */
export function ProgressRing({ value = 0, size = 96, stroke = 9, label, sublabel, tone = "indigo" }) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDrawn(clamped));
    return () => cancelAnimationFrame(frame);
  }, [clamped]);
  return (
    <div className="ts-ring" data-tone={tone} style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={`${label ?? clamped}${sublabel ? ` ${sublabel}` : ""}`}>
        <circle className="ts-ring__track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} fill="none" />
        <circle
          className="ts-ring__bar"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - drawn / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ts-ring__label">
        <strong>{label ?? `${Math.round(clamped)}%`}</strong>
        {sublabel ? <small>{sublabel}</small> : null}
      </div>
    </div>
  );
}

const AVATAR_TONES = 8;

export function Avatar({ name = "", src = "", size = 40, className = "" }) {
  const [failed, setFailed] = useState("");
  const initials =
    String(name)
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "T";
  const show = Boolean(src) && failed !== src;
  return (
    <span
      className={`ts-avatar ${className}`.trim()}
      data-tone={toneIndex(name) % AVATAR_TONES}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
    >
      {show ? <img src={src} alt="" onError={() => setFailed(src)} /> : <span aria-hidden="true">{initials}</span>}
    </span>
  );
}

/* --------------------------------------------------------- empty states */

const ART = {
  books: (
    <>
      <rect x="18" y="34" width="20" height="46" rx="4" className="a1" />
      <rect x="42" y="24" width="20" height="56" rx="4" className="a2" />
      <rect x="66" y="40" width="20" height="40" rx="4" className="a3" />
      <path d="M22 44h12M46 34h12M70 50h12" className="line" />
      <rect x="12" y="80" width="80" height="6" rx="3" className="base" />
    </>
  ),
  calendar: (
    <>
      <rect x="16" y="26" width="72" height="58" rx="10" className="a2" />
      <path d="M16 42h72" className="line" />
      <path d="M34 20v14M70 20v14" className="line thick" />
      <circle cx="36" cy="58" r="4" className="a1" />
      <circle cx="52" cy="58" r="4" className="a3" />
      <circle cx="68" cy="58" r="4" className="a1" />
      <circle cx="36" cy="72" r="4" className="a3" />
      <circle cx="52" cy="72" r="4" className="a1" />
    </>
  ),
  inbox: (
    <>
      <path d="M18 54 30 30h44l12 24v26a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6V54Z" className="a2" />
      <path d="M18 54h22l4 8h16l4-8h22" className="line" />
      <circle cx="78" cy="30" r="8" className="a1" />
    </>
  ),
  check: (
    <>
      <circle cx="52" cy="52" r="32" className="a2" />
      <path d="m36 53 11 11 21-24" className="line thick check" />
      <circle cx="82" cy="24" r="5" className="a1" />
      <circle cx="22" cy="78" r="4" className="a3" />
    </>
  ),
  clipboard: (
    <>
      <rect x="24" y="22" width="56" height="66" rx="8" className="a2" />
      <rect x="38" y="16" width="28" height="14" rx="5" className="a1" />
      <path d="M36 46h32M36 58h32M36 70h20" className="line" />
    </>
  ),
  search: (
    <>
      <circle cx="46" cy="46" r="24" className="a2" />
      <path d="m64 64 20 20" className="line thick" />
      <path d="M36 46h20" className="line" />
    </>
  ),
};

export function EmptyState({ art = "books", title, message, action, compact = false }) {
  return (
    <div className={`ts-empty${compact ? " ts-empty--compact" : ""}`}>
      <svg className="ts-empty__art" viewBox="0 0 104 104" fill="none" aria-hidden="true">
        {ART[art] || ART.books}
      </svg>
      {title ? <h3 className="ts-empty__title">{title}</h3> : null}
      {message ? <p className="ts-empty__message">{message}</p> : null}
      {action ? <div className="ts-empty__action">{action}</div> : null}
    </div>
  );
}

/* -------------------------------------------------------------- metric tile */

/** A headline number with an icon and a one-line note. Shares the .metric-card
 *  skin (see teacher-pages.css) so tiles look the same wherever they appear. */
export function MetricTile({ label, value, note, icon: Icon, tone = "indigo", decimals = 0, suffix = "" }) {
  const numeric = typeof value === "number" || (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value)));
  return (
    <div className="metric-card ts-metric" data-tone={tone}>
      <div className="metric-card-head">
        {Icon ? (
          <span className="metric-icon" aria-hidden="true">
            <Icon size={18} strokeWidth={1.9} />
          </span>
        ) : null}
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-value">{numeric ? <CountUp value={Number(value)} decimals={decimals} suffix={suffix} /> : value ?? "—"}</strong>
      {note ? <span className="metric-trend">{note}</span> : null}
    </div>
  );
}

/* -------------------------------------------------------------- dates */

const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

/** "Today", "Tomorrow", "In 5 days", "3 days ago" ... falls back to "9 Oct". */
export function relativeDay(value, now = new Date()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const days = Math.round((startOfDay(date) - startOfDay(now)) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "Yesterday";
  if (days > 1 && days < 31) return `In ${days} days`;
  if (days < -1 && days > -31) return `${-days} days ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: date.getFullYear() === now.getFullYear() ? undefined : "numeric" });
}

/** { day: "9", month: "OCT" } for the little calendar tile on exam rows. */
export function dateTile(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { day: "–", month: "" };
  return { day: String(date.getDate()), month: date.toLocaleDateString(undefined, { month: "short" }).toUpperCase() };
}

export const clockTime = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
};

/* --------------------------------------------------------------- misc */

/** Keeps an element's measured box in state (used by the sliding nav marker). */
export function useMeasuredElement() {
  const [box, setBox] = useState(null);
  const observer = useRef(null);
  const ref = useCallback((node) => {
    observer.current?.disconnect();
    if (!node) return;
    const measure = () => setBox({ top: node.offsetTop, height: node.offsetHeight });
    measure();
    if (typeof ResizeObserver !== "undefined") {
      observer.current = new ResizeObserver(measure);
      observer.current.observe(node);
    }
  }, []);
  return [ref, box];
}
