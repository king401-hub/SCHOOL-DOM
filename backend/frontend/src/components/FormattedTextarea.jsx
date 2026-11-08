import { useEffect, useRef, useState } from "react";

function normalizeEditorHtml(html) {
  return String(html || "")
    .replace(/<div><br><\/div>/gi, "<br>")
    .replace(/<div>/gi, "<br>")
    .replace(/<\/div>/gi, "")
    .replace(/<p>/gi, "")
    .replace(/<\/p>/gi, "<br>")
    .replace(/<b(\s[^>]*)?>/gi, "<strong>")
    .replace(/<\/b>/gi, "</strong>")
    .replace(/<i(\s[^>]*)?>/gi, "<em>")
    .replace(/<\/i>/gi, "</em>")
    .replace(/<span[^>]*style=\"[^\"]*font-weight:\s*(?:bold|700|800|900)[^\"]*\"[^>]*>/gi, "<strong>")
    .replace(/<span[^>]*style=\"[^\"]*font-style:\s*italic[^\"]*\"[^>]*>/gi, "<em>")
    .replace(/<span[^>]*style=\"[^\"]*text-decoration[^;]*underline[^\"]*\"[^>]*>/gi, "<u>")
    .replace(/<\/span>/gi, "")
    .replace(/<(?!\/?(?:strong|em|u|sub|sup|br)\b)[^>]+>/gi, "")
    .replace(/(?:<br>\s*){4,}/gi, "<br><br><br>");
}

export default function FormattedTextarea({ value = "", onChange, className = "", rows = 3, ...props }) {
  const editorRef = useRef(null);
  // The B/I/U toolbar stays hidden until the editor has focus, then slides
  // out from underneath it - keeps a page with many of these (lesson plans,
  // report card remarks, exam questions) from showing a formatting toolbar
  // on every single field all the time.
  const [toolbarOpen, setToolbarOpen] = useState(false);

  const emitChange = (nextValue) => {
    onChange?.({ target: { value: nextValue } });
  };

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const nextHtml = normalizeEditorHtml(value);
    if (editor.innerHTML !== nextHtml) {
      editor.innerHTML = nextHtml;
    }
  }, [value]);

  const syncValue = () => {
    const editor = editorRef.current;
    emitChange(normalizeEditorHtml(editor?.innerHTML || ""));
  };

  const format = (command) => {
    editorRef.current?.focus();
    document.execCommand(command, false, null);
    syncValue();
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const text = event.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
    syncValue();
  };

  return (
    <div className={`formatted-textarea${toolbarOpen ? " is-focused" : ""}`}>
      <div
        {...props}
        ref={editorRef}
        className={`formatted-textarea-editor ${className}`.trim()}
        contentEditable
        data-placeholder={props.placeholder || ""}
        onInput={syncValue}
        onFocus={() => setToolbarOpen(true)}
        onBlur={() => {
          syncValue();
          setToolbarOpen(false);
        }}
        onPaste={handlePaste}
        role="textbox"
        aria-multiline="true"
        style={{ minHeight: `${Math.max(Number(rows) || 3, 2) * 1.7}rem` }}
      />
      <div className="formatted-textarea-toolbar" aria-label="Text formatting controls" aria-hidden={!toolbarOpen}>
        <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => format("bold")} title="Bold selected text">
          <strong>B</strong>
        </button>
        <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => format("italic")} title="Italic selected text">
          <em>I</em>
        </button>
        <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => format("underline")} title="Underline selected text">
          <span className="underline-format">U</span>
        </button>
      </div>
    </div>
  );
}
