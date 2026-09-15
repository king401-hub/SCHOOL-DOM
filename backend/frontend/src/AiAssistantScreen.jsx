import { useEffect, useRef, useState } from "react";
import { ArrowUp, BarChart2, CalendarCheck, ChevronRight, DollarSign, FileCheck, Mic, Paperclip, School, Sparkles, MessageSquare } from "lucide-react";
import { API_BASE_URL } from "./appConstants";
import { refreshAccessToken } from "./AppShared";

const MAX_HISTORY_TURNS = 20;

// A small curated accent set (teal/cyan/emerald - the brand family - plus
// the orange/indigo already used elsewhere in this app, e.g. AiChatWidget's
// user-avatar orange and the sidebar's indigo active state) so the six
// cards stay visually distinct without reaching for an unrelated palette.
const QUICK_ACTIONS = [
  { icon: CalendarCheck, tone: "teal", label: "Show me today's attendance summary" },
  { icon: DollarSign, tone: "cyan", label: "How many fees are outstanding?" },
  { icon: MessageSquare, tone: "indigo", label: "Create a message for parents" },
  { icon: BarChart2, tone: "emerald", label: "Generate a class performance report" },
  { icon: FileCheck, tone: "amber", label: "Help me set up an exam" },
  { icon: School, tone: "orange", label: "Tell me something about my school" },
];

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function buildHistoryForApi(msgs) {
  return msgs
    .filter((m) => m.role === "user" || m.role === "assistant")
    .slice(-MAX_HISTORY_TURNS * 2)
    .map(({ role, content }) => ({ role, content }));
}

// Renders as the admin home page ("/dashboard" in App.jsx, admin-tier only
// - see App.jsx's isAdmin gate around AdminShell, so this never mounts for
// a non-admin role). Talks to the same /api/secretary/chat/ endpoint
// AiChatWidget's admin turn uses - a deliberately separate, simpler
// implementation (no streaming path, since only admin roles ever reach
// this screen) rather than a shared hook, to avoid touching the already-
// shipped floating widget for this page's sake.
export default function AiAssistantScreen({ session }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [busySeconds, setBusySeconds] = useState(0);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const abortRef = useRef(null);
  const busyTimerRef = useRef(null);

  const firstName = session?.user?.first_name || "there";
  const userInitial = (session?.user?.first_name?.[0] || "U").toUpperCase();

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => () => clearInterval(busyTimerRef.current), []);

  async function sendTurn(text, priorMessages, retried = false) {
    const headers = { "Content-Type": "application/json" };
    if (session?.access) headers.Authorization = `Bearer ${session.access}`;

    try {
      const res = await fetch(`${API_BASE_URL}/api/secretary/chat/`, {
        method: "POST",
        headers,
        signal: abortRef.current?.signal,
        body: JSON.stringify({
          message: text,
          history: buildHistoryForApi(priorMessages),
        }),
      });

      if (res.status === 401 && !retried) {
        await refreshAccessToken(session);
        return sendTurn(text, priorMessages, true);
      }

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "SchoolDom AI could not respond.");
      }

      const data = await res.json();
      const assistantMsg = {
        id: makeId(),
        role: "assistant",
        content: data.reply || "Done ✅",
        tools: data.tools_called || [],
        route: data.route || null,
      };

      if (assistantMsg.route && typeof window !== "undefined") {
        const normalizedRoute = assistantMsg.route.startsWith("/") ? assistantMsg.route : `/${assistantMsg.route}`;
        try {
          window.dispatchEvent(new CustomEvent("schooldom:assistant-navigate", { detail: { route: normalizedRoute } }));
        } catch (err) {
          console.warn("Assistant navigation dispatch failed", err);
        }
      }

      setMessages((prev) => [...prev.filter((m) => !m.thinking), assistantMsg]);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.thinking));
      if (err?.name !== "AbortError") {
        setError(err.message || "Something went wrong.");
      }
    }
  }

  async function handleSend(quickText) {
    const trimmed = (quickText ?? input).trim();
    if (!trimmed || busy) return;

    const priorMessages = messages;
    const userMsg = { id: makeId(), role: "user", content: trimmed };
    const thinkingMsg = { id: makeId(), role: "assistant", content: "", thinking: true };

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setError(null);
    setMessages((prev) => [...prev, userMsg, thinkingMsg]);
    setBusy(true);
    setBusySeconds(0);
    abortRef.current = new AbortController();
    busyTimerRef.current = setInterval(() => setBusySeconds((s) => s + 1), 1000);

    try {
      await sendTurn(trimmed, priorMessages);
    } finally {
      setBusy(false);
      setBusySeconds(0);
      clearInterval(busyTimerRef.current);
      abortRef.current = null;
    }
  }

  function stopResponse() {
    abortRef.current?.abort();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <section className="ai-assistant-page">
      <div className="ai-assistant-scroll" ref={scrollRef}>
        {!hasMessages ? (
          <div className="ai-assistant-hero">
            <div className="ai-assistant-hero-icon">
              <img src="/phoenix-ai.png" alt="SchoolDom AI" />
            </div>
            <h1>
              Hello, {firstName}. I&rsquo;m your <span className="ai-assistant-brand-text">SchoolDom AI</span>
            </h1>
            <p>
              Ask me anything about your school, students, classes, reports, or get help with tasks.
              I&rsquo;m here to make your work easier.
            </p>

            <div className="ai-assistant-quick-grid">
              {QUICK_ACTIONS.map(({ icon: Icon, tone, label }) => (
                <button
                  key={label}
                  type="button"
                  className={`ai-assistant-quick-card tone-${tone}`}
                  onClick={() => handleSend(label)}
                >
                  <span className="ai-assistant-quick-icon">
                    <Icon size={18} strokeWidth={1.8} />
                  </span>
                  <span className="ai-assistant-quick-label">{label}</span>
                  <ChevronRight size={16} className="ai-assistant-quick-chevron" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="ai-assistant-messages">
            {messages.map((msg, i) => (
              <div key={msg.id ?? i} className={`ai-assistant-message ai-assistant-message-${msg.role}`}>
                {msg.role === "assistant" && (
                  <div className="ai-assistant-avatar ai-assistant-avatar-ai">
                    <img src="/phoenix-ai.png" alt="" />
                  </div>
                )}
                <div className="sec-msg-wrap">
                  <div className="ai-assistant-bubble">
                    {msg.thinking ? (
                      <span className="ai-typing"><span /><span /><span /></span>
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
                      {busySeconds < 5
                        ? "Thinking…"
                        : busySeconds < 20
                        ? `Working on it… (${busySeconds}s)`
                        : `Almost there… (${busySeconds}s)`}
                    </span>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="ai-assistant-avatar ai-assistant-avatar-user">{userInitial}</div>
                )}
              </div>
            ))}
            {error && <div className="ai-chat-error">{error}</div>}
          </div>
        )}
      </div>

      <div className="ai-assistant-input-area">
        <div className="ai-assistant-input-row">
          <Sparkles size={16} className="ai-assistant-input-icon" />
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything…"
            rows={1}
            disabled={busy}
          />
          <button type="button" className="ai-assistant-input-btn" title="Attachments coming soon" disabled>
            <Paperclip size={16} />
          </button>
          <button type="button" className="ai-assistant-input-btn" title="Voice input coming soon" disabled>
            <Mic size={16} />
          </button>
          {busy ? (
            <button type="button" className="ai-assistant-send is-stop" onClick={stopResponse} title="Stop response" aria-label="Stop response">
              <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="2.5" />
              </svg>
            </button>
          ) : (
            <button
              type="button"
              className="ai-assistant-send"
              onClick={() => handleSend()}
              disabled={!input.trim()}
              title="Send"
              aria-label="Send"
            >
              <ArrowUp size={17} />
            </button>
          )}
        </div>
      </div>

      <p className="ai-assistant-footer">
        <Sparkles size={12} /> Powered by SchoolDom AI &middot; Always here to help
      </p>
    </section>
  );
}
