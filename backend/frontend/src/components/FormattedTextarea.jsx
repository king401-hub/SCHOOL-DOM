import { useRef } from "react";

function applyInlineFormat(textarea, value, before, after = before) {
  const start = textarea?.selectionStart ?? String(value || "").length;
  const end = textarea?.selectionEnd ?? start;
  const current = String(value || "");
  const selected = current.slice(start, end);
  const next = `${current.slice(0, start)}${before}${selected || "text"}${after}${current.slice(end)}`;
  const nextStart = start + before.length;
  const nextEnd = nextStart + (selected || "text").length;
  return { next, nextStart, nextEnd };
}

export default function FormattedTextarea({ value = "", onChange, className = "", rows = 3, ...props }) {
  const textareaRef = useRef(null);

  const emitChange = (nextValue) => {
    onChange?.({ target: { value: nextValue } });
  };

  const format = (before, after = before) => {
    const textarea = textareaRef.current;
    const { next, nextStart, nextEnd } = applyInlineFormat(textarea, value, before, after);
    emitChange(next);
    window.requestAnimationFrame(() => {
      textarea?.focus();
      textarea?.setSelectionRange(nextStart, nextEnd);
    });
  };

  return (
    <div className="formatted-textarea">
      <div className="formatted-textarea-toolbar" aria-label="Text formatting controls">
        <button type="button" onClick={() => format("**")} title="Bold selected text">
          <strong>B</strong>
        </button>
        <button type="button" onClick={() => format("_")} title="Italic selected text">
          <em>I</em>
        </button>
        <button type="button" onClick={() => format("<u>", "</u>")} title="Underline selected text">
          <span className="underline-format">U</span>
        </button>
      </div>
      <textarea
        {...props}
        ref={textareaRef}
        className={className}
        value={value}
        onChange={onChange}
        rows={rows}
      />
    </div>
  );
}
