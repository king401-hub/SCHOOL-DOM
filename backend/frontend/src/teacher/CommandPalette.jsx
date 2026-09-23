// Ctrl/⌘+K palette: jump to any teacher page or start a common task.
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CornerDownLeft, Search } from "lucide-react";
import { Kbd } from "./TeacherKit";

function scoreItem(item, tokens) {
  const haystack = `${item.label} ${item.section || ""} ${item.keywords || ""}`.toLowerCase();
  let score = 0;
  for (const token of tokens) {
    const at = haystack.indexOf(token);
    if (at === -1) return -1;
    score += at === 0 ? 3 : haystack.includes(` ${token}`) ? 2 : 1;
  }
  return score;
}

export default function CommandPalette({ open, onClose, items }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const returnFocusTo = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    returnFocusTo.current = document.activeElement;
    setQuery("");
    setActive(0);
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      cancelAnimationFrame(frame);
      const node = returnFocusTo.current;
      if (node instanceof HTMLElement && document.contains(node)) node.focus();
    };
  }, [open]);

  const results = useMemo(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!tokens.length) return items;
    return items
      .map((item) => ({ item, score: scoreItem(item, tokens) }))
      .filter((entry) => entry.score >= 0)
      .sort((a, b) => b.score - a.score)
      .map((entry) => entry.item);
  }, [items, query]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    listRef.current?.querySelector("[aria-selected='true']")?.scrollIntoView?.({ block: "nearest" });
  }, [active, results]);

  if (!open) return null;

  const choose = (item) => {
    if (!item) return;
    onClose();
    // Let the palette unmount (and focus return) before the page swaps.
    window.setTimeout(() => item.run?.(), 0);
  };

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => (results.length ? (current + 1) % results.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => (results.length ? (current - 1 + results.length) % results.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Tab") {
      // Keep focus inside the dialog.
      event.preventDefault();
    }
  };

  let lastSection = "";
  return createPortal(
    <div className="ts-palette-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="ts-palette" role="dialog" aria-modal="true" aria-label="Search and jump" onKeyDown={onKeyDown}>
        <label className="ts-palette__search">
          <Search size={18} aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search pages and actions…"
            role="combobox"
            aria-expanded="true"
            aria-controls="ts-palette-list"
            aria-activedescendant={results[active] ? `ts-palette-${results[active].id}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
          <Kbd>Esc</Kbd>
        </label>
        <ul className="ts-palette__list" id="ts-palette-list" role="listbox" ref={listRef}>
          {results.length === 0 ? (
            <li className="ts-palette__empty">Nothing matches “{query}”. Try a page name like “results” or “timetable”.</li>
          ) : (
            results.map((item, index) => {
              const heading = item.section && item.section !== lastSection && !query ? item.section : "";
              lastSection = item.section || "";
              const Icon = item.icon;
              return (
                <li key={item.id} role="presentation">
                  {heading ? <p className="ts-palette__heading">{heading}</p> : null}
                  <button
                    type="button"
                    id={`ts-palette-${item.id}`}
                    role="option"
                    aria-selected={index === active}
                    className={index === active ? "is-active" : ""}
                    onMouseMove={() => setActive(index)}
                    onClick={() => choose(item)}
                  >
                    <span className="ts-palette__icon" aria-hidden="true">{Icon ? <Icon size={17} strokeWidth={1.9} /> : null}</span>
                    <span className="ts-palette__label">
                      {item.label}
                      {item.hint ? <small>{item.hint}</small> : null}
                    </span>
                    {index === active ? <CornerDownLeft size={15} aria-hidden="true" /> : null}
                  </button>
                </li>
              );
            })
          )}
        </ul>
        <footer className="ts-palette__foot">
          <span><Kbd>↑</Kbd><Kbd>↓</Kbd> move</span>
          <span><Kbd>↵</Kbd> open</span>
          <span><Kbd>Esc</Kbd> close</span>
        </footer>
      </div>
    </div>,
    document.body
  );
}
