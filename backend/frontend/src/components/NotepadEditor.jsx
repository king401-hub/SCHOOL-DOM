import { useEffect, useRef, useCallback } from "react";

/* ── Toolbar definition ──────────────────────────────────────────────────── */
const SEPARATOR = "sep";

const TOOLBAR = [
  { cmd: "bold",        label: "B",   title: "Bold",         style: { fontWeight: 700 } },
  { cmd: "italic",      label: "I",   title: "Italic",       style: { fontStyle: "italic" } },
  { cmd: "underline",   label: "U",   title: "Underline",    style: { textDecoration: "underline" } },
  { cmd: "strikeThrough", label: "S", title: "Strikethrough", style: { textDecoration: "line-through" } },
  SEPARATOR,
  { cmd: "h1", label: "H1", title: "Heading 1", block: "H1" },
  { cmd: "h2", label: "H2", title: "Heading 2", block: "H2" },
  { cmd: "h3", label: "H3", title: "Heading 3", block: "H3" },
  SEPARATOR,
  { cmd: "insertUnorderedList", label: "≡•", title: "Bullet list" },
  { cmd: "insertOrderedList",   label: "≡1", title: "Numbered list" },
  { cmd: "blockquote", label: "❝",   title: "Blockquote",  block: "BLOCKQUOTE" },
  { cmd: "pre",        label: "</>", title: "Code block",  block: "PRE" },
  SEPARATOR,
  { cmd: "justifyLeft",   label: "⫠",  title: "Align left" },
  { cmd: "justifyCenter", label: "≡",  title: "Align center" },
  { cmd: "justifyRight",  label: "⫣",  title: "Align right" },
  SEPARATOR,
  { cmd: "undo", label: "↩", title: "Undo" },
  { cmd: "redo", label: "↪", title: "Redo" },
];

function normalizeHtml(html) {
  return String(html || "")
    .replace(/<div><br><\/div>/gi, "<br>")
    .replace(/<div>/gi, "<br>")
    .replace(/<\/div>/gi, "")
    .replace(/<b(\s[^>]*)?>/gi, "<strong>")
    .replace(/<\/b>/gi, "</strong>")
    .replace(/<i(\s[^>]*)?>/gi, "<em>")
    .replace(/<\/i>/gi, "</em>")
    .replace(/(?:<br>\s*){5,}/gi, "<br><br><br>");
}

export default function NotepadEditor({ value = "", onChange, placeholder = "Start writing..." }) {
  const editorRef = useRef(null);

  const emitChange = useCallback((html) => {
    onChange?.({ target: { value: normalizeHtml(html) } });
  }, [onChange]);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    const next = normalizeHtml(value);
    if (el.innerHTML !== next) el.innerHTML = next;
  }, [value]);

  const syncValue = useCallback(() => {
    emitChange(editorRef.current?.innerHTML || "");
  }, [emitChange]);

  const exec = useCallback((item) => {
    editorRef.current?.focus();
    if (item.block) {
      document.execCommand("formatBlock", false, item.block);
    } else {
      document.execCommand(item.cmd, false, null);
    }
    syncValue();
  }, [syncValue]);

  const handlePaste = (e) => {
    e.preventDefault();
    document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
    syncValue();
  };

  return (
    <div className="nped-wrap">
      <div className="nped-toolbar" aria-label="Formatting toolbar">
        {TOOLBAR.map((item, idx) =>
          item === SEPARATOR
            ? <span key={idx} className="nped-sep" aria-hidden="true" />
            : (
              <button
                key={item.cmd}
                type="button"
                className="nped-tool-btn"
                title={item.title}
                style={item.style}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => exec(item)}
              >
                {item.label}
              </button>
            )
        )}
      </div>
      <div
        ref={editorRef}
        className="nped-editor"
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onInput={syncValue}
        onBlur={syncValue}
        onPaste={handlePaste}
        role="textbox"
        aria-multiline="true"
        aria-label="Note editor"
      />
    </div>
  );
}
