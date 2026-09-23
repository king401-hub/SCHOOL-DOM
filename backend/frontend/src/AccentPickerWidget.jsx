import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ACCENT_LANGUAGES, applyCase } from "./accentCharacterSet";
import { insertCharacterIntoActiveElement, hasInsertTarget } from "./utils/insertCharacterAtCursor";

const POS_KEY = "accent_picker_pos";
const LONG_PRESS_MS = 400;

// null until the user has dragged the button somewhere; until then the default
// position is worked out from the page (see defaultLeftFor below).
function loadPos() {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      if (typeof p.left === "number" && typeof p.bottom === "number") return p;
    }
  } catch {}
  return null;
}

// The old fixed default (16px from the left) landed on top of the pinned
// sidebar's footer - the teacher / student "Sign out" button - on every page
// that has one. When a sidebar is actually on screen and reaches the bottom of
// the viewport, start just to the right of it instead. The phone drawer sits
// off-canvas (right <= 0) until opened, so it doesn't count.
function defaultLeftFor() {
  try {
    const sidebar = document.querySelector(".teacher-sidebar, .ts-sidebar, .student-sidebar, .app-sidebar");
    if (!sidebar) return 16;
    const rect = sidebar.getBoundingClientRect();
    const onScreen = rect.width > 0 && rect.left >= 0 && rect.right > 0;
    const reachesBottom = rect.bottom > window.innerHeight - 90;
    return onScreen && reachesBottom ? Math.round(rect.right) + 16 : 16;
  } catch {
    return 16;
  }
}

export default function AccentPickerWidget({ session }) {
  const [savedPos, setPos] = useState(loadPos);
  const [defaultLeft, setDefaultLeft] = useState(16);
  const pos = savedPos || { left: defaultLeft, bottom: 16 };

  useEffect(() => {
    // The dashboards mount their sidebar a beat after this widget (they wait on
    // their data first), so re-check when the page structure changes as well as
    // on resize. setState with an unchanged value is a no-op, so this stays cheap.
    const update = () => setDefaultLeft(defaultLeftFor());
    update();
    let timer = null;
    const soon = () => {
      if (timer) return;
      timer = window.setTimeout(() => { timer = null; update(); }, 250);
    };
    const observer = typeof MutationObserver === "function" ? new MutationObserver(soon) : null;
    observer?.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", update);
    return () => {
      observer?.disconnect();
      if (timer) window.clearTimeout(timer);
      window.removeEventListener("resize", update);
    };
  }, [session]);
  const [isDragging, setIsDragging] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeLangId, setActiveLangId] = useState(ACCENT_LANGUAGES[0].id);
  const [shift, setShift] = useState(false);
  const [flyout, setFlyout] = useState(null);

  const dragRef = useRef(null);
  const longPressTimerRef = useRef(null);
  const longPressFiredRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") {
        setFlyout(null);
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // ── Drag-to-move (identical mechanics to AiChatWidget's toggle) ────────────

  function handleTogglePointerDown(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      originLeft: pos.left,
      originBottom: pos.bottom,
      moved: false,
    };
    setIsDragging(true);
  }

  function handleTogglePointerMove(e) {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragRef.current.moved = true;
    if (dragRef.current.moved) {
      setPos({
        left: Math.max(0, Math.min(dragRef.current.originLeft + dx, window.innerWidth - 70)),
        bottom: Math.max(0, Math.min(dragRef.current.originBottom - dy, window.innerHeight - 70)),
      });
    }
  }

  function handleTogglePointerUp() {
    if (!dragRef.current) return;
    const wasDragged = dragRef.current.moved;
    dragRef.current = null;
    setIsDragging(false);
    if (!wasDragged) {
      setOpen((v) => {
        if (v) setFlyout(null);
        return !v;
      });
    } else {
      setPos((p) => {
        try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch {}
        return p;
      });
    }
  }

  // ── Character insertion ─────────────────────────────────────────────────────

  function insertChar(char) {
    insertCharacterIntoActiveElement(applyCase(char, shift));
    setFlyout(null);
  }

  function openFlyout(group, buttonEl) {
    const rect = buttonEl.getBoundingClientRect();
    setFlyout({ group, left: rect.left, bottom: window.innerHeight - rect.top + 6 });
  }

  function handleCharPointerDown(e, group) {
    e.preventDefault();
    longPressFiredRef.current = false;
    longPressTimerRef.current = setTimeout(() => {
      longPressFiredRef.current = true;
      openFlyout(group, e.currentTarget);
    }, LONG_PRESS_MS);
  }

  function handleCharPointerUp(e, group) {
    clearTimeout(longPressTimerRef.current);
    if (!longPressFiredRef.current) {
      insertChar(group.tap);
    }
  }

  function handleCharPointerCancel() {
    clearTimeout(longPressTimerRef.current);
  }

  if (!session) return null;

  const activeLang = ACCENT_LANGUAGES.find((l) => l.id === activeLangId) || ACCENT_LANGUAGES[0];
  const showHint = open && !hasInsertTarget();

  return (
    <div className="accent-picker-shell" style={{ left: pos.left, bottom: pos.bottom }}>
      <button
        type="button"
        className={`accent-picker-toggle ${open ? "is-open" : ""} ${isDragging ? "is-dragging" : ""}`}
        onPointerDown={handleTogglePointerDown}
        onPointerMove={handleTogglePointerMove}
        onPointerUp={handleTogglePointerUp}
        onPointerCancel={() => { dragRef.current = null; setIsDragging(false); }}
        aria-label={open ? "Close accent character picker" : "Open accent character picker"}
        title="Type Yorùbá & French accents — drag to move"
      >
        {open ? "×" : "Ẹ́"}
      </button>

      {open && createPortal(
        <div className="accent-picker-popup" style={{ left: pos.left, bottom: pos.bottom + 66 }} role="dialog" aria-label="Accent character picker">
          <div className="accent-picker-popup-header">
            <div className="accent-picker-tabs">
              {ACCENT_LANGUAGES.map((lang) => (
                <button
                  key={lang.id}
                  type="button"
                  className={`accent-picker-tab ${activeLangId === lang.id ? "is-active" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { setActiveLangId(lang.id); setFlyout(null); }}
                >
                  {lang.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className={`accent-picker-shift ${shift ? "is-active" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => setShift((v) => !v)}
              aria-pressed={shift}
              title="Uppercase"
            >
              ⇧
            </button>
            <button
              type="button"
              className="accent-picker-close"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { setFlyout(null); setOpen(false); }}
              aria-label="Close accent character picker"
            >
              ×
            </button>
          </div>

          <div className="accent-picker-grid" dir={activeLang.dir || "ltr"}>
            {activeLang.groups.map((group) => (
              <button
                key={group.key}
                type="button"
                className="accent-picker-char-btn"
                onPointerDown={(e) => handleCharPointerDown(e, group)}
                onPointerUp={(e) => handleCharPointerUp(e, group)}
                onPointerLeave={handleCharPointerCancel}
                onPointerCancel={handleCharPointerCancel}
                title={group.variants.length > 1 ? "Tap to insert · hold for more options" : undefined}
              >
                {applyCase(group.tap, shift)}
              </button>
            ))}
          </div>

          {showHint && (
            <div className="accent-picker-hint">Tap into a text field first, then tap a character.</div>
          )}
        </div>,
        document.body
      )}

      {flyout && createPortal(
        <div
          className="accent-picker-flyout"
          style={{ left: flyout.left, bottom: flyout.bottom }}
          onPointerLeave={() => setFlyout(null)}
        >
          {flyout.group.variants.map((variant) => (
            <button
              key={variant}
              type="button"
              className="accent-picker-flyout-btn"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => insertChar(variant)}
            >
              {applyCase(variant, shift)}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}
