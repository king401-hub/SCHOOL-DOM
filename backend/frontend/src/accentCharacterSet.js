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

export const ACCENT_LANGUAGES = [
  { id: "yoruba", label: "Yorùbá", groups: YORUBA_GROUPS },
  { id: "french", label: "Français", groups: FRENCH_GROUPS },
];

// Standard, codepoint-verified Unicode case mapping (each Yorùbá/French letter
// here uppercases to its correct precomposed capital; combining tone marks are
// case-invariant and pass through unchanged) — safe to derive rather than
// duplicate every group as a second hardcoded uppercase literal.
export function applyCase(char, upper) {
  return upper ? char.toUpperCase() : char;
}
