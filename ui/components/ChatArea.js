/* ═══════════════════════════════════════════
   components/ChatArea.js
   Main chat area: top bar, messages list,
   welcome screen with quick cards, input bar.
   ═══════════════════════════════════════════ */

const { useRef: useRefCA, useEffect: useEffectCA } = React;

// Markdown renderer
marked.setOptions({ breaks: true, gfm: true });
const renderMd = (text) => (text ? marked.parse(text) : "");

function ChatArea({
  showSide,
  onToggleSide,
  messages,
  loading,
  input,
  setInput,
  onSend,
}) {
  const endRef = useRefCA(null);
  const inpRef = useRefCA(null);

  useEffectCA(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const formatTime = (d) =>
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <main className="main">
      {/* Top bar */}
      <div className="top">
        <button className="top-menu" onClick={onToggleSide}>
          <MenuIcon />
        </button>
        <div className="top-title">Mortgage Educator</div>
        <div className="top-status">
          <div className="top-dot" />
          Online
        </div>
      </div>

      {/* Messages */}
      <div className="msgs-wrap">
        <div className="msgs">
          {messages.length === 0 ? (
            <WelcomeScreen onSend={onSend} />
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`mrow ${m.role === "user" ? "usr" : ""}`}>
                <div className={`mav ${m.role === "user" ? "usr" : "ai"}`}>
                  {m.role === "user" ? "You" : "O"}
                </div>
                <div className="mbody">
                  <div
                    className={`mbub ${m.role === "user" ? "usr" : "ai"}`}
                    dangerouslySetInnerHTML={{ __html: renderMd(m.content) }}
                  />
                  {m.topics && m.topics.length > 0 && (
                    <div className="mtags">
                      {m.topics.map((t) => (
                        <span key={t.id} className="mtag">{t.title}</span>
                      ))}
                    </div>
                  )}
                  <div className="mtime">{formatTime(m.time)}</div>
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="typing">
              <div className="mav ai">O</div>
              <div className="tdots">
                <div className="tdot" />
                <div className="tdot" />
                <div className="tdot" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* Input */}
      <div className="inp-area">
        <div className="inp-wrap">
          <textarea
            ref={inpRef}
            className="inp"
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about Canadian mortgages..."
            disabled={loading}
          />
          <button
            className="sendbtn"
            onClick={onSend}
            disabled={!input.trim() || loading}
          >
            <SendIcon />
          </button>
        </div>
        <div className="inp-hint">
          Educational information only -- not financial advice. Enter to send.
        </div>
      </div>
    </main>
  );
}

/* ── Welcome sub-component ── */
function WelcomeScreen({ onSend }) {
  return (
    <div className="welcome">
      <div className="welcome-badge">AI-Powered Mortgage Education</div>
      <h1>
        Your home buying
        <br />
        journey starts <em>here</em>
      </h1>
      <p>
        Personalized Canadian mortgage guidance. No jargon, no pressure,
        just clarity for first-time buyers.
      </p>
      <div className="quick-cards">
        {window.QUICK_CARDS.map((q, i) => (
          <div key={i} className="qcard" onClick={() => onSend(q.text)}>
            <div className="qcard-icon" style={{ color: q.color, background: q.bg }}>
              {q.icon}
            </div>
            <div className="qcard-text">{q.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.ChatArea = ChatArea;