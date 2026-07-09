import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./appConstants";
import { refreshAccessToken } from "./AppShared";

const AI_NAME = "Phoenix AI";
const HISTORY_KEY = "phoenix_ai_history";
const LIMIT_KEY = "phoenix_ai_daily_limit";
const TASKS_KEY = "phoenix_ai_tasks";
const SEC_HISTORY_KEY = "secretary_chat_history";
const DAILY_LIMIT = 30;
const MAX_SAVED_CONVOS = 50;
const SEC_MAX_SAVED = 30;
const SEC_MAX_HISTORY_TURNS = 20;

const POS_KEY = "phoenix_ai_pos";

function loadPos() {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      if (typeof p.right === "number" && typeof p.bottom === "number") return p;
    }
  } catch {}
  return { right: 16, bottom: 16 };
}

const QUICK_PROMPTS = [
  "What can you do?",
  "Help me understand a topic",
  "Write a report template",
  "Explain exam results to parents",
];

const ADMIN_ROLES = new Set([
  "school_admin", "principal", "accountant",
  "school_superadmin", "super_admin",
]);

const SEC_QUICK_PROMPTS = [
  "Add a new student",
  "Mark attendance for a class",
  "Schedule an exam",
  "Send fee reminder to parents",
];

// ── localStorage helpers ──────────────────────────────────────────────────────

function getTodayStr() {
  return new Date().toISOString().slice(0, 10);
}

function getDailyUsage() {
  try {
    const raw = localStorage.getItem(LIMIT_KEY);
    if (!raw) return 0;
    const { date, count } = JSON.parse(raw);
    return date === getTodayStr() ? count || 0 : 0;
  } catch {
    return 0;
  }
}

function incrementDailyUsage() {
  const count = getDailyUsage() + 1;
  localStorage.setItem(LIMIT_KEY, JSON.stringify({ date: getTodayStr(), count }));
  return count;
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function persistHistory(conversations) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(conversations.slice(0, MAX_SAVED_CONVOS)));
}

function loadTasks() {
  try {
    return JSON.parse(localStorage.getItem(TASKS_KEY) || "[]");
  } catch {
    return [];
  }
}

function persistTasks(tasks) {
  localStorage.setItem(TASKS_KEY, JSON.stringify(tasks));
}

function loadSecHistory() {
  try { return JSON.parse(localStorage.getItem(SEC_HISTORY_KEY) || "[]"); } catch { return []; }
}
function saveSecHistory(chats) {
  localStorage.setItem(SEC_HISTORY_KEY, JSON.stringify(chats.slice(0, SEC_MAX_SAVED)));
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

// ── Streaming helper ──────────────────────────────────────────────────────────

function appendChunk(prev, chunk) {
  if (!prev.length) return prev;
  const next = prev.slice();
  const i = next.length - 1;
  next[i] = { ...next[i], content: next[i].content + chunk };
  return next;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AiChatWidget({ session }) {
  const isAdmin = ADMIN_ROLES.has(session?.user?.role || "");

  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("chat"); // "chat" | "history" | "tasks" | "secretary"
  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);
  const [dailyUsed, setDailyUsed] = useState(0);
  const [tasks, setTasks] = useState([]);
  const [taskInput, setTaskInput] = useState("");
  const [taskFilter, setTaskFilter] = useState("all");
  const [pos, setPos] = useState(loadPos);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef(null);

  // Secretary state
  const [secMessages, setSecMessages] = useState([]);
  const [secInput, setSecInput] = useState("");
  const [secBusy, setSecBusy] = useState(false);
  const [secBusySeconds, setSecBusySeconds] = useState(0);
  const [secError, setSecError] = useState(null);
  const [secSavedChats, setSecSavedChats] = useState([]);
  const [secCurrentId, setSecCurrentId] = useState(() => makeId());
  const [secShowHistory, setSecShowHistory] = useState(false);
  const secTimerRef = useRef(null);
  const secTextareaRef = useRef(null);
  const secListRef = useRef(null);

  const listRef = useRef(null);
  const textareaRef = useRef(null);
  const taskInputRef = useRef(null);

  useEffect(() => {
    setConversations(loadHistory());
    setDailyUsed(getDailyUsage());
    setCurrentId(makeId());
    setTasks(loadTasks());
    if (isAdmin) setSecSavedChats(loadSecHistory());
  }, []);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, open]);

  useEffect(() => {
    if (secListRef.current) secListRef.current.scrollTop = secListRef.current.scrollHeight;
  }, [secMessages, open]);

  useEffect(() => {
    if (!open) return;
    if (mode === "chat") window.requestAnimationFrame(() => textareaRef.current?.focus());
    if (mode === "tasks") window.requestAnimationFrame(() => taskInputRef.current?.focus());
    if (mode === "secretary") window.requestAnimationFrame(() => secTextareaRef.current?.focus());
  }, [open, mode]);

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 100) + "px";
    }
  }

  function saveConversation(msgs, id) {
    if (!msgs.length) return;
    const title = msgs.find((m) => m.role === "user")?.content?.slice(0, 60) || "Chat";
    setConversations((prev) => {
      const updated = [
        { id, title, messages: msgs, createdAt: Date.now() },
        ...prev.filter((c) => c.id !== id),
      ];
      persistHistory(updated);
      return updated;
    });
  }

  function startNewChat() {
    setCurrentId(makeId());
    setMessages([]);
    setInput("");
    setError(null);
    setMode("chat");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function loadConversation(conv) {
    setCurrentId(conv.id);
    setMessages(conv.messages);
    setInput("");
    setError(null);
    setMode("chat");
  }

  function deleteConversation(id, e) {
    e.stopPropagation();
    setConversations((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      persistHistory(updated);
      return updated;
    });
    if (id === currentId) startNewChat();
  }

  async function copyMessage(content, index) {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(index);
      setTimeout(() => setCopied(null), 1500);
    } catch {}
  }

  // ── Task manager ──────────────────────────────────────────────────────────────

  function addTask() {
    const text = taskInput.trim();
    if (!text) return;
    const task = { id: makeId(), text, done: false, createdAt: Date.now() };
    setTasks((prev) => {
      const updated = [task, ...prev];
      persistTasks(updated);
      return updated;
    });
    setTaskInput("");
    taskInputRef.current?.focus();
  }

  function toggleTask(id) {
    setTasks((prev) => {
      const updated = prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t));
      persistTasks(updated);
      return updated;
    });
  }

  function deleteTask(id) {
    setTasks((prev) => {
      const updated = prev.filter((t) => t.id !== id);
      persistTasks(updated);
      return updated;
    });
  }

  function clearDoneTasks() {
    setTasks((prev) => {
      const updated = prev.filter((t) => !t.done);
      persistTasks(updated);
      return updated;
    });
  }

  // ── Secretary ─────────────────────────────────────────────────────────────────

  function startNewSecChat() {
    setSecCurrentId(makeId());
    setSecMessages([]);
    setSecInput("");
    setSecError(null);
    setSecShowHistory(false);
  }

  function persistSecChat(msgs) {
    if (!msgs.length) return;
    const title = msgs.find((m) => m.role === "user")?.content?.slice(0, 55) || "Chat";
    setSecSavedChats((prev) => {
      const updated = [
        { id: secCurrentId, title, messages: msgs, createdAt: Date.now() },
        ...prev.filter((c) => c.id !== secCurrentId),
      ].slice(0, SEC_MAX_SAVED);
      saveSecHistory(updated);
      return updated;
    });
  }

  function loadSecChat(chat) {
    setSecCurrentId(chat.id);
    setSecMessages(chat.messages);
    setSecInput("");
    setSecError(null);
    setSecShowHistory(false);
  }

  function deleteSecChat(id, e) {
    e.stopPropagation();
    setSecSavedChats((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      saveSecHistory(updated);
      return updated;
    });
    if (id === secCurrentId) startNewSecChat();
  }

  function buildSecHistory(msgs) {
    return msgs
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-SEC_MAX_HISTORY_TURNS * 2)
      .map(({ role, content }) => ({ role, content }));
  }

  async function handleSecSend(quickText, retried = false) {
    const text = (quickText ?? secInput).trim();
    if (!text || secBusy) return;

    const userMsg = { id: makeId(), role: "user", content: text };
    const thinkingMsg = { id: makeId(), role: "assistant", content: "", thinking: true };

    setSecMessages((prev) => [...prev, userMsg, thinkingMsg]);
    setSecInput("");
    setSecError(null);
    setSecBusy(true);
    setSecBusySeconds(0);
    secTimerRef.current = setInterval(() => setSecBusySeconds((s) => s + 1), 1000);

    const headers = { "Content-Type": "application/json" };
    if (session?.access) headers.Authorization = `Bearer ${session.access}`;

    try {
      const res = await fetch(`${API_BASE_URL}/api/secretary/chat/`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: text,
          history: buildSecHistory(secMessages),
        }),
      });

      if (res.status === 401 && !retried) {
        await refreshAccessToken(session);
        setSecMessages((prev) => prev.filter((m) => !m.thinking));
        return handleSecSend(quickText, true);
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

      setSecMessages((prev) => {
        const updated = [...prev.filter((m) => !m.thinking), assistantMsg];
        persistSecChat(updated);
        return updated;
      });
    } catch (err) {
      setSecMessages((prev) => prev.filter((m) => !m.thinking));
      setSecError(err.message || "Something went wrong.");
    } finally {
      setSecBusy(false);
      setSecBusySeconds(0);
      clearInterval(secTimerRef.current);
    }
  }

  function handleSecKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSecSend();
    }
  }

  // ── AI chat ───────────────────────────────────────────────────────────────────

  async function streamChat(history, retried = false) {
    const headers = { "Content-Type": "application/json" };
    if (session?.access) headers.Authorization = `Bearer ${session.access}`;

    let response;
    try {
      response = await fetch(`${API_BASE_URL}/api/ai/chat/`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
      });
    } catch {
      throw new Error("Network error. Check your connection.");
    }

    if (response.status === 401 && !retried) {
      await refreshAccessToken(session);
      return streamChat(history, true);
    }

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || "Phoenix AI could not respond.");
    }

    const reader = response.body?.getReader();
    if (!reader) {
      const text = await response.text();
      setMessages((prev) => appendChunk(prev, text));
      return;
    }

    const decoder = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (chunk) setMessages((prev) => appendChunk(prev, chunk));
    }
  }

  async function handleSend(quickText) {
    const trimmed = (quickText ?? input).trim();
    if (!trimmed || busy) return;

    const remaining = DAILY_LIMIT - dailyUsed;
    if (remaining <= 0) {
      setError(`You've reached today's limit of ${DAILY_LIMIT} messages. Come back tomorrow!`);
      return;
    }

    const userMsg = { role: "user", content: trimmed };
    const history = [...messages, userMsg];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setError(null);
    setBusy(true);
    setDailyUsed(incrementDailyUsage());

    const savedId = currentId;
    try {
      await streamChat(history);
      setMessages((prev) => {
        saveConversation(prev, savedId);
        return prev;
      });
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1));
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleTaskKeyDown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      addTask();
    }
  }

  // ── Header action helpers ─────────────────────────────────────────────────────

  function handleHistoryToggle() {
    if (mode === "secretary") {
      setSecShowHistory((v) => !v);
    } else {
      setMode((m) => (m === "history" ? "chat" : "history"));
    }
  }

  function handleNewChat() {
    if (mode === "secretary") startNewSecChat();
    else startNewChat();
  }

  // ── Drag-to-move ─────────────────────────────────────────────────────────────

  function handleTogglePointerDown(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      originRight: pos.right,
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
        right: Math.max(0, Math.min(dragRef.current.originRight - dx, window.innerWidth - 70)),
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
      setOpen((v) => !v);
    } else {
      setPos((p) => {
        try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch {}
        return p;
      });
    }
  }

  if (!session) return null;

  const remaining = DAILY_LIMIT - dailyUsed;
  const userInitial = (session?.user?.first_name?.[0] || "U").toUpperCase();
  const canSend = input.trim() && !busy && remaining > 0;

  const activeTasks = tasks.filter((t) => !t.done);
  const doneTasks = tasks.filter((t) => t.done);
  const filteredTasks = tasks.filter((t) => {
    if (taskFilter === "active") return !t.done;
    if (taskFilter === "done") return t.done;
    return true;
  });

  const historyActive = mode === "secretary" ? secShowHistory : mode === "history";

  return (
    <div className="ai-chat-shell" style={{ right: pos.right, bottom: pos.bottom }}>
      {open && (
        <div className="ai-chat-panel" role="dialog" aria-label="Phoenix AI">

          {/* Header */}
          <header className="ai-chat-header">
            <div className="ai-chat-header-left">
              <div className="ai-chat-logo">{mode === "secretary" ? "🗂️" : "⚡"}</div>
              <div>
                <strong>{mode === "secretary" ? "Schooldom Secretary" : AI_NAME}</strong>
                <span className="ai-chat-subtitle">
                  {mode === "secretary" ? "Admin assistant" : "Your personal assistant"}
                </span>
              </div>
            </div>
            <div className="ai-chat-header-actions">
              {isAdmin && (
                <button
                  type="button"
                  className={`ai-chat-icon-btn sec-tab-btn ${mode === "secretary" ? "active" : ""}`}
                  onClick={() => setMode((m) => (m === "secretary" ? "chat" : "secretary"))}
                  title="Schooldom Secretary (Admin)"
                >
                  🗂️
                </button>
              )}
              <button
                type="button"
                className={`ai-chat-icon-btn ${mode === "tasks" ? "active" : ""}`}
                onClick={() => setMode((m) => (m === "tasks" ? "chat" : "tasks"))}
                title="Task manager"
              >
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
                </svg>
              </button>
              <button
                type="button"
                className={`ai-chat-icon-btn ${historyActive ? "active" : ""}`}
                onClick={handleHistoryToggle}
                title="Chat history"
              >
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </button>
              <button
                type="button"
                className="ai-chat-icon-btn"
                onClick={handleNewChat}
                title="New chat"
              >
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
              <button
                type="button"
                className="ai-chat-close"
                onClick={() => setOpen(false)}
                aria-label="Close"
              >
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </header>

          {/* ── Secretary mode ─────────────────────────────────────────────── */}
          {mode === "secretary" ? (
            secShowHistory ? (
              <div className="sec-history">
                <div className="sec-history-head">
                  <span>Recent sessions</span>
                  <span>{new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
                </div>
                {secSavedChats.length === 0 ? (
                  <p className="sec-history-empty">No previous sessions yet.</p>
                ) : (
                  <ul className="sec-history-list">
                    {secSavedChats.map((c) => (
                      <li
                        key={c.id}
                        className={`sec-history-item ${c.id === secCurrentId ? "active" : ""}`}
                        onClick={() => loadSecChat(c)}
                      >
                        <div className="sec-history-title">{c.title}</div>
                        <div className="sec-history-meta">
                          {new Date(c.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                          {" · "}{c.messages.length} msgs
                        </div>
                        <button
                          type="button"
                          className="sec-history-delete"
                          onClick={(e) => deleteSecChat(c.id, e)}
                          title="Delete"
                        >×</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <>
                <div className="sec-messages" ref={secListRef}>
                  {secMessages.length === 0 && (
                    <div className="sec-welcome">
                      <div className="sec-welcome-icon">🗂️</div>
                      <h3>Hello! How can I assist?</h3>
                      <p>I manage students, attendance, exams &amp; parent messages. Responses take 15–30s on first use.</p>
                      <div className="sec-quick-prompts">
                        {SEC_QUICK_PROMPTS.map((q) => (
                          <button
                            key={q}
                            type="button"
                            className="sec-quick-btn"
                            onClick={() => handleSecSend(q)}
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {secMessages.map((msg) => (
                    <div key={msg.id} className={`sec-message sec-message-${msg.role}`}>
                      {msg.role === "assistant" && (
                        <div className="sec-avatar sec-avatar-ai">🗂️</div>
                      )}
                      <div className="sec-msg-wrap">
                        <div className="sec-bubble">
                          {msg.thinking ? (
                            <span className="sec-thinking">
                              <span /><span /><span />
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
                        {msg.thinking && (
                          <span className="sec-thinking-label">
                            {secBusySeconds < 5
                              ? "Thinking…"
                              : secBusySeconds < 20
                              ? `Working on it… (${secBusySeconds}s)`
                              : `Almost there… (${secBusySeconds}s)`}
                          </span>
                        )}
                      </div>
                      {msg.role === "user" && (
                        <div className="sec-avatar sec-avatar-user">{userInitial}</div>
                      )}
                    </div>
                  ))}

                  {secError && <div className="sec-error">{secError}</div>}
                </div>

                <div className="sec-input-area">
                  <div className="sec-input-row">
                    <textarea
                      ref={secTextareaRef}
                      value={secInput}
                      onChange={(e) => setSecInput(e.target.value)}
                      onKeyDown={handleSecKeyDown}
                      placeholder="Tell me what you need…"
                      rows={1}
                      disabled={secBusy}
                    />
                    <button
                      type="button"
                      className="sec-send"
                      onClick={() => handleSecSend()}
                      disabled={!secInput.trim() || secBusy}
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
            )

          /* ── History panel (chat mode) ─────────────────────────────────── */
          ) : mode === "history" ? (
            <div className="ai-chat-history">
              <div className="ai-chat-history-head">
                <span>Recent chats</span>
                <span className="ai-chat-history-date">
                  {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              </div>
              {conversations.length === 0 ? (
                <p className="ai-chat-history-empty">No previous chats yet.</p>
              ) : (
                <ul className="ai-chat-history-list">
                  {conversations.map((c) => (
                    <li
                      key={c.id}
                      className={`ai-chat-history-item ${c.id === currentId ? "active" : ""}`}
                      onClick={() => loadConversation(c)}
                    >
                      <div className="ai-chat-history-item-title">{c.title || "Chat"}</div>
                      <div className="ai-chat-history-item-meta">
                        {new Date(c.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        {" · "}{c.messages.length} msgs
                      </div>
                      <button
                        type="button"
                        className="ai-chat-history-delete"
                        onClick={(e) => deleteConversation(c.id, e)}
                        title="Delete"
                      >×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

          /* ── Task Manager ─────────────────────────────────────────────── */
          ) : mode === "tasks" ? (
            <div className="ai-task-panel">
              <div className="ai-task-add-row">
                <input
                  ref={taskInputRef}
                  type="text"
                  className="ai-task-input"
                  placeholder="Add a new task…"
                  value={taskInput}
                  onChange={(e) => setTaskInput(e.target.value)}
                  onKeyDown={handleTaskKeyDown}
                />
                <button
                  type="button"
                  className="ai-task-add-btn"
                  onClick={addTask}
                  disabled={!taskInput.trim()}
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </button>
              </div>

              <div className="ai-task-filters">
                {[
                  { key: "all", label: `All (${tasks.length})` },
                  { key: "active", label: `Active (${activeTasks.length})` },
                  { key: "done", label: `Done (${doneTasks.length})` },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    className={`ai-task-filter-btn ${taskFilter === key ? "active" : ""}`}
                    onClick={() => setTaskFilter(key)}
                  >
                    {label}
                  </button>
                ))}
                {doneTasks.length > 0 && (
                  <button type="button" className="ai-task-clear-btn" onClick={clearDoneTasks}>
                    Clear done
                  </button>
                )}
              </div>

              <div className="ai-task-list-wrap">
                {filteredTasks.length === 0 ? (
                  <div className="ai-task-empty">
                    {taskFilter === "done"
                      ? "No completed tasks yet."
                      : taskFilter === "active"
                      ? "All tasks done! 🎉"
                      : "No tasks yet. Add one above!"}
                  </div>
                ) : (
                  <ul className="ai-task-list">
                    {filteredTasks.map((task) => (
                      <li key={task.id} className={`ai-task-item ${task.done ? "done" : ""}`}>
                        <button
                          type="button"
                          className="ai-task-check"
                          onClick={() => toggleTask(task.id)}
                          title={task.done ? "Mark undone" : "Mark done"}
                        >
                          {task.done && (
                            <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </button>
                        <span className="ai-task-text">{task.text}</span>
                        <button
                          type="button"
                          className="ai-task-delete"
                          onClick={() => deleteTask(task.id)}
                          title="Delete task"
                        >×</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

          /* ── Chat ─────────────────────────────────────────────────────── */
          ) : (
            <>
              <div className="ai-chat-messages" ref={listRef}>
                {messages.length === 0 && (
                  <div className="ai-chat-welcome">
                    <div className="ai-chat-welcome-icon">⚡</div>
                    <h3>Hello! How can I help you?</h3>
                    <p>Ask me anything about Schooldom or school management.</p>
                    <div className="ai-chat-quick-prompts">
                      {QUICK_PROMPTS.map((q) => (
                        <button
                          key={q}
                          type="button"
                          className="ai-chat-quick-btn"
                          onClick={() => handleSend(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <div key={i} className={`ai-chat-message ai-chat-message-${msg.role}`}>
                    {msg.role === "assistant" && (
                      <div className="ai-chat-avatar ai-chat-avatar-ai">⚡</div>
                    )}
                    <div className="ai-chat-bubble">
                      {msg.content ? (
                        <span>{msg.content}</span>
                      ) : busy && i === messages.length - 1 ? (
                        <span className="ai-typing"><span /><span /><span /></span>
                      ) : null}
                      {msg.role === "assistant" && msg.content && (
                        <button
                          type="button"
                          className="ai-chat-copy"
                          onClick={() => copyMessage(msg.content, i)}
                          title={copied === i ? "Copied!" : "Copy"}
                        >
                          {copied === i ? "✓" : "⧉"}
                        </button>
                      )}
                    </div>
                    {msg.role === "user" && (
                      <div className="ai-chat-avatar ai-chat-avatar-user">{userInitial}</div>
                    )}
                  </div>
                ))}

                {error && <div className="ai-chat-error">{error}</div>}
              </div>

              <div className="ai-chat-input-area">
                {remaining <= 5 && remaining > 0 && (
                  <div className="ai-chat-limit-warn">
                    {remaining} message{remaining !== 1 ? "s" : ""} left today
                  </div>
                )}
                <div className="ai-chat-input-row">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask Phoenix AI anything…"
                    rows={1}
                    disabled={busy || remaining <= 0}
                  />
                  <button
                    type="button"
                    className="ai-chat-send"
                    onClick={() => handleSend()}
                    disabled={!canSend}
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

      {/* Floating toggle button — drag to reposition */}
      <button
        type="button"
        className={`ai-chat-toggle ${open ? "is-open" : ""} ${isDragging ? "is-dragging" : ""}`}
        onPointerDown={handleTogglePointerDown}
        onPointerMove={handleTogglePointerMove}
        onPointerUp={handleTogglePointerUp}
        onPointerCancel={() => { dragRef.current = null; setIsDragging(false); }}
        aria-label={open ? "Close Phoenix AI" : "Open Phoenix AI"}
        title="Phoenix AI — drag to move"
      >
        {open ? (
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <span className="ai-toggle-icon">⚡</span>
        )}
      </button>
    </div>
  );
}
