// Character data for the global accent picker. Every entry below is a literal,
// precomposed Unicode character written directly in source — never built from
// codepoints at runtime, so there is no ambiguity about which glyph is stored.
//
// Each "group" becomes one button in the picker grid:
//   - `tap`      is what a plain tap inserts (the fast path).
//   - `variants` is the full ordered list shown in the long-press flyout.
// For plain-vowel groups (a/e/i/o/u) `tap` is an accented form — not the bare
// letter, since the bare letter is already on every physical keyboard — but the
// bare letter is still reachable as the last entry in `variants` via long-press.
// ẹ/ọ/ṣ/ń have no bare-keyboard equivalent at all, so they are their own primary
// buttons and `tap` inserts them directly.

export const YORUBA_GROUPS = [
  { key: "a", tap: "à", variants: ["à", "á", "a"] },
  { key: "e", tap: "è", variants: ["è", "é", "e"] },
  { key: "ẹ", tap: "ẹ", variants: ["ẹ", "ẹ̀", "ẹ́"] },
  { key: "i", tap: "ì", variants: ["ì", "í", "i"] },
  { key: "o", tap: "ò", variants: ["ò", "ó", "o"] },
  { key: "ọ", tap: "ọ", variants: ["ọ", "ọ̀", "ọ́"] },
  { key: "u", tap: "ù", variants: ["ù", "ú", "u"] },
  { key: "ṣ", tap: "ṣ", variants: ["ṣ"] },
  { key: "ń", tap: "ń", variants: ["ń"] },
];

export const FRENCH_GROUPS = [
  { key: "a", tap: "à", variants: ["à", "â", "ä"] },
  { key: "c", tap: "ç", variants: ["ç"] },
  { key: "e", tap: "é", variants: ["é", "è", "ê", "ë"] },
  { key: "i", tap: "î", variants: ["î", "ï"] },
  { key: "o", tap: "ô", variants: ["ô", "ö"] },
  { key: "u", tap: "ù", variants: ["ù", "û", "ü"] },
  { key: "y", tap: "ÿ", variants: ["ÿ"] },
  { key: "æ", tap: "æ", variants: ["æ"] },
  { key: "œ", tap: "œ", variants: ["œ"] },
];

// Arabic has no Latin-keyboard equivalent at all, so every letter's `tap` is
// the bare letter itself (unlike the Yorùbá/French groups above). Contextual
// joining (initial/medial/final letterforms) is handled automatically by the
// browser's Arabic text shaping once the plain codepoint is inserted — nothing
// extra is needed here. The trailing five groups are the core harakat
// (short-vowel diacritics); each is a standalone combining mark that attaches
// to whatever letter already precedes it in the field.
export const ARABIC_GROUPS = [
  { key: "alif", tap: "ا", variants: ["ا"] },
  { key: "ba", tap: "ب", variants: ["ب"] },
  { key: "ta", tap: "ت", variants: ["ت"] },
  { key: "tha", tap: "ث", variants: ["ث"] },
  { key: "jim", tap: "ج", variants: ["ج"] },
  { key: "ha", tap: "ح", variants: ["ح"] },
  { key: "kha", tap: "خ", variants: ["خ"] },
  { key: "dal", tap: "د", variants: ["د"] },
  { key: "dhal", tap: "ذ", variants: ["ذ"] },
  { key: "ra", tap: "ر", variants: ["ر"] },
  { key: "zay", tap: "ز", variants: ["ز"] },
  { key: "sin", tap: "س", variants: ["س"] },
  { key: "shin", tap: "ش", variants: ["ش"] },
  { key: "sad", tap: "ص", variants: ["ص"] },
  { key: "dad", tap: "ض", variants: ["ض"] },
  { key: "taa", tap: "ط", variants: ["ط"] },
  { key: "zaa", tap: "ظ", variants: ["ظ"] },
  { key: "ain", tap: "ع", variants: ["ع"] },
  { key: "ghain", tap: "غ", variants: ["غ"] },
  { key: "fa", tap: "ف", variants: ["ف"] },
  { key: "qaf", tap: "ق", variants: ["ق"] },
  { key: "kaf", tap: "ك", variants: ["ك"] },
  { key: "lam", tap: "ل", variants: ["ل"] },
  { key: "mim", tap: "م", variants: ["م"] },
  { key: "nun", tap: "ن", variants: ["ن"] },
  { key: "ha2", tap: "ه", variants: ["ه"] },
  { key: "waw", tap: "و", variants: ["و"] },
  { key: "ya", tap: "ي", variants: ["ي"] },
  { key: "hamza", tap: "ء", variants: ["ء"] },
  { key: "alif_hamza_above", tap: "أ", variants: ["أ"] },
  { key: "alif_hamza_below", tap: "إ", variants: ["إ"] },
  { key: "waw_hamza", tap: "ؤ", variants: ["ؤ"] },
  { key: "ya_hamza", tap: "ئ", variants: ["ئ"] },
  { key: "alif_madda", tap: "آ", variants: ["آ"] },
  { key: "ta_marbuta", tap: "ة", variants: ["ة"] },
  { key: "alif_maksura", tap: "ى", variants: ["ى"] },
  { key: "fatha", tap: "َ", variants: ["َ"] },
  { key: "damma", tap: "ُ", variants: ["ُ"] },
  { key: "kasra", tap: "ِ", variants: ["ِ"] },
  { key: "shadda", tap: "ّ", variants: ["ّ"] },
  { key: "sukun", tap: "ْ", variants: ["ْ"] },
];

export const ACCENT_LANGUAGES = [
  { id: "yoruba", label: "Yorùbá", groups: YORUBA_GROUPS },
  { id: "french", label: "Français", groups: FRENCH_GROUPS },
  { id: "arabic", label: "العربية", dir: "rtl", groups: ARABIC_GROUPS },
];

// Standard, codepoint-verified Unicode case mapping (each Yorùbá/French letter
// here uppercases to its correct precomposed capital; combining tone marks are
// case-invariant and pass through unchanged) — safe to derive rather than
// duplicate every group as a second hardcoded uppercase literal.
export function applyCase(char, upper) {
  return upper ? char.toUpperCase() : char;
}
