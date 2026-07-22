// Framework-free DOM utility: tracks whichever text field was last focused
// anywhere on the page, and inserts a character into it on demand. This is
// what lets a single floating widget (mounted once, globally) reach into any
// form field, chat box, or rich-text editor in the app without each one
// needing to know the widget exists.

const TEXTY_INPUT_TYPES = new Set(["text", "search", "tel", "url", "password", "email", ""]);

let lastField = null;

function isEligibleField(el) {
  if (!el) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === "TEXTAREA") return true;
  if (tag === "INPUT") return TEXTY_INPUT_TYPES.has((el.type || "").toLowerCase());
  return false;
}

function handleFocusIn(event) {
  if (isEligibleField(event.target)) {
    lastField = event.target;
  }
}

if (typeof document !== "undefined") {
  // Never cleared on focusout: clicking the picker's own toggle/buttons steals
  // focus away from the real field, and losing track of it there would break
  // the whole point of the widget. It's simply overwritten next time a real
  // field is focused.
  document.addEventListener("focusin", handleFocusIn, true);
}

export function hasInsertTarget() {
  return !!lastField && document.body.contains(lastField);
}

export function insertCharacterIntoActiveElement(char) {
  const el = lastField;
  if (!el || !document.body.contains(el)) return false;

  if (el.isContentEditable) {
    el.focus();
    document.execCommand("insertText", false, char);
    return true;
  }

  const tag = el.tagName;
  if (tag !== "INPUT" && tag !== "TEXTAREA") return false;

  el.focus();
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  const nativeSetter = Object.getOwnPropertyDescriptor(
    tag === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
    "value"
  ).set;

  const newValue = el.value.slice(0, start) + char + el.value.slice(end);
  nativeSetter.call(el, newValue);
  el.dispatchEvent(new Event("input", { bubbles: true }));

  const caret = start + char.length;
  try {
    el.setSelectionRange(caret, caret);
  } catch {
    // Some input types (e.g. email) don't support a selection range at all —
    // the value is already inserted correctly, the caret position is cosmetic.
  }

  return true;
}
