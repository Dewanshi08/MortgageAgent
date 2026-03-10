/* ═══════════════════════════════════════════
   App.js
   Root component. Owns global state, routes
   API calls, and composes child components.
   ═══════════════════════════════════════════ */

const { useState, useCallback } = React;

const API_BASE = window.location.origin + "/api";

const postAPI = async (path, body) => {
  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(r.status);
  return r.json();
};

function App() {
  // UI state
  const [showSide, setShowSide] = useState(window.innerWidth > 768);
  const [showOnboard, setShowOnboard] = useState(true);

  // Session state
  const [uid, setUid] = useState(null);
  const [sid, setSid] = useState(null);
  const [estimate, setEstimate] = useState(null);

  // Chat state
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Journey state
  const [activeStage, setActiveStage] = useState(1);
  const [stagesData] = useState(window.STAGES_DATA);

  // ── Send message ──
  const send = useCallback(
    async (text) => {
      const m = text || input.trim();
      if (!m || loading) return;
      setInput("");

      setMsgs((prev) => [...prev, { role: "user", content: m, time: new Date() }]);
      setLoading(true);

      try {
        const body = { message: m };
        if (uid) body.user_id = uid;
        if (sid) body.session_id = sid;

        const r = await postAPI("/chat", body);

        if (r.user_id) setUid(r.user_id);
        if (r.session_id) setSid(r.session_id);

        setMsgs((prev) => [
          ...prev,
          {
            role: "assistant",
            content: r.message,
            time: new Date(),
            topics: r.relevant_topics || [],
          },
        ]);
      } catch (e) {
        setMsgs((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Something went wrong. Please try again.",
            time: new Date(),
            topics: [],
          },
        ]);
      }

      setLoading(false);
    },
    [input, loading, uid, sid]
  );

  // ── Handlers ──
  const handleNewChat = () => {
    setMsgs([]);
    setSid(null);
  };

  const handleOnboardDone = (userId, affordabilityEstimate) => {
    setUid(userId);
    setEstimate(affordabilityEstimate);
    setShowOnboard(false);
  };

  const handleTopicClick = (topicTitle) => {
    send("Tell me about: " + topicTitle);
  };

  return (
    <div className="app">
      {/* Onboarding modal */}
      {showOnboard && (
        <Onboarding
          onDone={handleOnboardDone}
          onSkip={() => setShowOnboard(false)}
        />
      )}

      {/* Mobile backdrop */}
      <div
        className={`backdrop ${showSide ? "show" : ""}`}
        onClick={() => setShowSide(false)}
      />

      {/* Sidebar */}
      <Sidebar
        show={showSide}
        onClose={() => setShowSide(false)}
        onNewChat={handleNewChat}
        estimate={estimate}
        stagesData={stagesData}
        activeStage={activeStage}
        setActiveStage={setActiveStage}
        onTopicClick={handleTopicClick}
      />

      {/* Chat area */}
      <ChatArea
        showSide={showSide}
        onToggleSide={() => setShowSide(!showSide)}
        messages={msgs}
        loading={loading}
        input={input}
        setInput={setInput}
        onSend={send}
      />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);