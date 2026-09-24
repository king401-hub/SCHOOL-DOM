// Small pure helpers for the admin timetable board.

export const ALL_CLASSES = "all";

/** "08:40" -> 520 (minutes since midnight); null when it isn't a time. */
export function toMinutes(value) {
  const [hours, minutes] = String(value || "").split(":").map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours * 60 + minutes : null;
}

export const slotKey = (start, end) => `${start}|${end}`;
export const cellKey = (day, start, end) => `${day}|${start}|${end}`;
export const timeRange = (start, end) => `${start}–${end}`;

/** Today's weekday in the same numbering the API uses (Monday = 0). */
export const weekdayIndex = (date = new Date()) => (date.getDay() + 6) % 7;

/** A lesson that should have a teacher but doesn't. Title-only slots such as
 *  "Assembly" or "Break" legitimately have none, so they never count. */
export const needsTeacher = (entry) => Boolean(entry?.subject_id) && !entry?.teacher_id && !entry?.teacher_name;

export const entryLabel = (entry) => entry?.display_label || entry?.subject_name || entry?.title || "Lesson";

/* ---------------------------------------------------------------- names */

// Long subject names wrapped over 2-3 lines and swamped the card, so the grid
// shows a short form and keeps the full name in the tooltip / dialog.
const KNOWN_SHORT = {
  "mathematics": "Maths",
  "general mathematics": "Gen. Maths",
  "further mathematics": "F. Maths",
  "english language": "English",
  "literature in english": "Literature",
  "christian religious studies": "CRS",
  "christian religious knowledge": "CRK",
  "islamic religious studies": "IRS",
  "islamic religious knowledge": "IRK",
  "civic education": "Civic Edu.",
  "social studies": "Social St.",
  "basic science": "Basic Sci.",
  "basic technology": "Basic Tech.",
  "basic science and technology": "BST",
  "physical and health education": "PHE",
  "physical education": "P.E.",
  "computer studies": "Computer",
  "information technology": "ICT",
  "agricultural science": "Agric.",
  "business studies": "Business",
  "home economics": "Home Econ.",
  "cultural and creative arts": "CCA",
  "government": "Govt.",
  "economics": "Econs",
};

const SKIP_WORDS = new Set(["and", "of", "in", "the", "&", "for"]);

export function subjectShort(name, max = 13) {
  const full = String(name || "").trim().replace(/\s+/g, " ");
  if (!full) return "";
  const known = KNOWN_SHORT[full.toLowerCase()];
  if (known) return known;
  if (full.length <= max) return full;
  const words = full.split(" ").filter((word) => !SKIP_WORDS.has(word.toLowerCase()));
  if (words.length >= 3) return words.map((word) => word[0].toUpperCase()).join("").slice(0, 5);
  if (words.length === 2) {
    const compact = `${words[0]} ${words[1][0]}.`;
    if (compact.length <= max) return compact;
    return words.map((word) => word[0].toUpperCase()).join("");
  }
  return `${full.slice(0, max - 1)}…`;
}

/** A touch shorter, for the "all classes" chips. Always derived from the name
 *  (never the school's subject code) so every chip reads the same way. */
export function subjectTiny(entry) {
  return subjectShort(entryLabel(entry), 9);
}

/** "English Language" -> "EL", "Mathematics" -> "MA": the swatch in the details dialog. */
export function initialsOf(name) {
  const words = String(name || "").trim().split(/\s+/).filter((word) => word && !SKIP_WORDS.has(word.toLowerCase()));
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 3).map((word) => word[0]).join("").toUpperCase();
}

/** "SSS1 - ART" -> "SSS1 ART" */
export const classTiny = (label) => String(label || "").replace(/\s*-\s*/g, " ").trim();

/* --------------------------------------------------------------- colour */

// Golden-angle steps keep neighbouring subject ids far apart on the colour
// wheel, and using the id (not the list position) means a subject keeps its
// colour when others are added. Title-only slots (Assembly, Break) stay neutral.
export function hueFor(entry) {
  if (!entry?.subject_id) return null;
  return Math.round((Number(entry.subject_id) * 137.508) % 360);
}

export const hueStyle = (entry) => {
  const hue = hueFor(entry);
  return hue === null ? undefined : { "--tt-h": hue };
};

/* ---------------------------------------------------------------- sorting */

export const byDayThenTime = (a, b) => {
  if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
  return String(a.start_time).localeCompare(String(b.start_time));
};

/** Rows for the grid: the configured periods, plus any custom time an entry
 *  was saved at (otherwise that lesson would be invisible in the grid). */
export function buildRows(timeSlots, entries) {
  const rows = new Map();
  (timeSlots || []).forEach((slot) => {
    rows.set(slotKey(slot.start_time, slot.end_time), { ...slot, custom: false });
  });
  (entries || []).forEach((entry) => {
    const key = slotKey(entry.start_time, entry.end_time);
    if (!rows.has(key)) {
      rows.set(key, { start_time: entry.start_time, end_time: entry.end_time, is_break: false, custom: true });
    }
  });
  return [...rows.values()].sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
}

export function groupByCell(entries) {
  const map = new Map();
  entries.forEach((entry) => {
    const key = cellKey(entry.day_of_week, entry.start_time, entry.end_time);
    const list = map.get(key);
    if (list) list.push(entry);
    else map.set(key, [entry]);
  });
  return map;
}

export const shortDay = (label) => String(label || "").slice(0, 3);
