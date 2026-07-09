import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./appConstants";
import { refreshAccessToken } from "./AppShared";

const WIDGET_NAME = "Schooldom Secretary";
const HISTORY_KEY = "secretary_chat_history";
const MAX_SAVED = 30;
const MAX_HISTORY_TURNS = 20;

const ADMIN_ROLES = new Set([
  "school_admin", "principal", "accountant",
  "school_superadmin", "super_admin",
]);

const QUICK_PROMPTS = [
  "Add a new student",
  "Mark attendance for a class",
  "Schedule an exam",
  "Send fee reminder to parents",
];

// ── localStorage ─────────────────────────────────────────────────────────────

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); } catch { return []; }
}
function saveHistory(msgs) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(msgs.slice(-MAX_SAVED * 2)));
}
function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SecretaryWidget({ session }) {
  const role = session?.user?.role || "";
  if (!session || !ADMIN_ROLES.has(role)) return null;

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {id, role, content, tools}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [busySeconds, setBusySeconds] = useState(0);
  const [error, setError] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [savedChats, setSavedChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(() => makeId());
  const timerRef = useRef(null);

  const listRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    setSavedChats(loadHistory());
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, open]);

  useEffect(() => {
    if (open && !showHistory) {
      window.requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }, [open, showHistory]);

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 100) + "px";
    }
  }

  function startNewChat() {
    setCurrentChatId(makeId());
    setMessages([]);
    setInput("");
    setError(null);
    setShowHistory(false);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function persistCurrentChat(msgs) {
    if (!msgs.length) return;
    const title = msgs.find((m) => m.role === "user")?.content?.slice(0, 55) || "Chat";
    setSavedChats((prev) => {
      const updated = [
        { id: currentChatId, title, messages: msgs, createdAt: Date.now() },
        ...prev.filter((c) => c.id !== currentChatId),
      ].slice(0, MAX_SAVED);
      saveHistory(updated);
      return updated;
    });
  }

  function loadChat(chat) {
    setCurrentChatId(chat.id);
    setMessages(chat.messages);
    setInput("");
    setError(null);
    setShowHistory(false);
  }

  function deleteChat(id, e) {
    e.stopPropagation();
    setSavedChats((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      saveHistory(updated);
      return updated;
    });
    if (id === currentChatId) startNewChat();
  }

  // Build the API history payload (role + content only, last N turns)
  function buildHistory(msgs) {
    return msgs
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-MAX_HISTORY_TURNS * 2)
      .map(({ role, content }) => ({ role, content }));
  }

  async function handleSend(quickText, retried = false) {
    const text = (quickText ?? input).trim();
    if (!text || busy) return;

    const userMsg = { id: makeId(), role: "user", content: text };
    const thinkingMsg = { id: makeId(), role: "assistant", content: "", thinking: true };
    const nextMessages = [...messages, userMsg, thinkingMsg];

    setMessages(nextMessages);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setError(null);
    setBusy(true);
    setBusySeconds(0);
    timerRef.current = setInterval(() => setBusySeconds((s) => s + 1), 1000);

    const headers = { "Content-Type": "application/json" };
    if (session?.access) headers.Authorization = `Bearer ${session.access}`;

    try {
      const res = await fetch(`${API_BASE_URL}/api/secretary/chat/`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: text,
          history: buildHistory(messages),
        }),
      });

      if (res.status === 401 && !retried) {
        await refreshAccessToken(session);
        setMessages(messages); // restore pre-send state
        return handleSend(quickText, true);
      }

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Secretary could not respond.");
      }

      const data = await res.json();
      const assistantMsg = {
        id: makeId(),
        role: "assistant",
        content: data.reply || "Done ✅",
        tools: data.tools_called || [],
      };

      setMessages((prev) => {
        const updated = [...prev.filter((m) => !m.thinking), assistantMsg];
        persistCurrentChat(updated);
        return updated;
      });
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.thinking));
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
      setBusySeconds(0);
      clearInterval(timerRef.current);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const userInitial = (session?.user?.first_name?.[0] || "A").toUpperCase();

  return (
    <div className="sec-shell">
      {open && (
        <div className="sec-panel" role="dialog" aria-label="Schooldom Secretary">

          {/* Header */}
          <header className="sec-header">
            <div className="sec-header-left">
              <div className="sec-logo">🗂️</div>
              <div>
                <strong>{WIDGET_NAME}</strong>
                <span className="sec-subtitle">Admin assistant</span>
              </div>
            </div>
            <div className="sec-header-actions">
              <button
                type="button"
                className={`sec-icon-btn ${showHistory ? "active" : ""}`}
                onClick={() => setShowHistory((v) => !v)}
                title="Chat history"
              >
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                </svg>
              </button>
              <button type="button" className="sec-icon-btn" onClick={startNewChat} title="New chat">
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
              <button type="button" className="sec-close" onClick={() => setOpen(false)} aria-label="Close">
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </header>

          {/* History panel */}
          {showHistory ? (
            <div className="sec-history">
              <div className="sec-history-head">
                <span>Recent sessions</span>
                <span>{new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
              </div>
              {savedChats.length === 0 ? (
                <p className="sec-history-empty">No previous sessions yet.</p>
              ) : (
                <ul className="sec-history-list">
                  {savedChats.map((c) => (
                    <li
                      key={c.id}
                      className={`sec-history-item ${c.id === currentChatId ? "active" : ""}`}
                      onClick={() => loadChat(c)}
                    >
                      <div className="sec-history-title">{c.title}</div>
                      <div className="sec-history-meta">
                        {new Date(c.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        {" · "}{c.messages.length} msgs
                      </div>
                      <button
                        type="button"
                        className="sec-history-delete"
                        onClick={(e) => deleteChat(c.id, e)}
                        title="Delete"
                      >×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <>
              {/* Messages */}
              <div className="sec-messages" ref={listRef}>
                {messages.length === 0 && (
                  <div className="sec-welcome">
                    <div className="sec-welcome-icon">🗂️</div>
                    <h3>Hello! How can I assist?</h3>
                    <p>I manage students, attendance, exams & parent messages. Responses take 15–30s on first use.</p>
                    <div className="sec-quick-prompts">
                      {QUICK_PROMPTS.map((q) => (
                        <button
                          key={q}
                          type="button"
                          className="sec-quick-btn"
                          onClick={() => handleSend(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((msg) => (
                  <div key={msg.id} className={`sec-message sec-message-${msg.role}`}>
                    {msg.role === "assistant" && (
                      <div className="sec-avatar sec-avatar-ai">🗂️</div>
                    )}
                    <div className="sec-bubble">
                      {msg.thinking ? (
                        <span className="sec-thinking">
                          <span />
                          <span />
                          <span />
                          <span className="sec-thinking-label">
                            {busySeconds < 5
                              ? "Thinking…"
                              : busySeconds < 20
                              ? `Working on it… (${busySeconds}s)`
                              : `Almost there… (${busySeconds}s)`}
                          </span>
                        </span>
                      ) : (
                        <span style={{ whiteSpace: "pre-wrap" }}>{msg.content}</span>
                      )}
                      {msg.tools?.length > 0 && (
                        <div className="sec-tools-badge">
                          {msg.tools.map((t) => (
                            <span key={t} className="sec-tool-chip">{t.replace(/_/g, " ")}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    {msg.role === "user" && (
                      <div className="sec-avatar sec-avatar-user">{userInitial}</div>
                    )}
                  </div>
                ))}

                {error && <div className="sec-error">{error}</div>}
              </div>

              {/* Input */}
              <div className="sec-input-area">
                <div className="sec-input-row">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Tell me what you need…"
                    rows={1}
                    disabled={busy}
                  />
                  <button
                    type="button"
                    className="sec-send"
                    onClick={() => handleSend()}
                    disabled={!input.trim() || busy}
                    title="Send (Enter)"
                  >
                    <svg width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* FAB toggle */}
      <button
        type="button"
        className={`sec-toggle ${open ? "is-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close Secretary" : "Open Secretary"}
        title="Schooldom Secretary"
      >
        {open ? (
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <span className="sec-toggle-icon">🗂️</span>
        )}
      </button>
    </div>
  );
}
