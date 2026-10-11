/* ═══════════════════════════════════════════
   components/Sidebar.js
   Left sidebar: branding, estimate card,
   journey stages with topics, progress bar.
   ═══════════════════════════════════════════ */

function Sidebar({
  show,
  onClose,
  onNewChat,
  estimate,
  stagesData,
  activeStage,
  setActiveStage,
  onTopicClick,
}) {
  // Unlock logic: stage unlocks if previous stage has >= 50% covered
  const isUnlocked = (stageId) => {
    if (stageId === 1) return true;
    const prev = stagesData.find((s) => s.id === stageId - 1);
    if (!prev) return false;
    const prevCovered = prev.topics.filter((t) => t.covered).length;
    return prevCovered >= Math.ceil(prev.topics.length * 0.5);
  };

  const stageStatus = (st) => {
    const c = st.topics.filter((t) => t.covered).length;
    if (c === st.topics.length) return "done";
    if (c > 0) return "partial";
    return "new";
  };

  // Progress calculation
  const totalTopics = stagesData.reduce((a, s) => a + s.topics.length, 0);
  const coveredTopics = stagesData.reduce((a, s) => a + s.topics.filter((t) => t.covered).length, 0);
  const progressPct = Math.round((coveredTopics / totalTopics) * 100);

  return (
    <aside className={`side ${show ? "" : "hide"}`}>
      <div className="side-head" style={{ position: "relative" }}>
        <div className="side-brand">own-ly</div>
        <div className="side-sub">own your dream</div>
        <button className="side-x" onClick={onClose}>
          <CloseIcon />
        </button>
      </div>

      <button className="side-newchat" onClick={onNewChat}>
        New Conversation
      </button>

      {estimate && (
        <div className="side-est">
          <div className="est-card">
            <div className="est-label">Estimated Max Price</div>
            <div className="est-val">
              ${Number(estimate.estimated_max_price || 0).toLocaleString()}
            </div>
            {estimate.monthly_debts > 0 && (
              <div className="est-detail">
                Monthly debts: <span>${Number(estimate.monthly_debts).toLocaleString()}</span>
              </div>
            )}
            {estimate.limited_by && (
              <div className="est-detail" style={{ color: "var(--text-3)" }}>
                Limited by: {estimate.limited_by}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="journey">
        <div className="journey-label">Your Journey</div>
        {stagesData.map((st, i) => {
          const unlocked = isUnlocked(st.id);
          const isActive = st.id === activeStage;
          const status = stageStatus(st);
          const covCount = st.topics.filter((t) => t.covered).length;

          // Connector line styling
          const prevDoneLine =
            i > 0 &&
            stagesData[i - 1].topics.filter((t) => t.covered).length >=
              Math.ceil(stagesData[i - 1].topics.length * 0.5);

          return (
            <div className="stg" key={st.id}>
              {i > 0 && (
                <div className={`stg-connector ${prevDoneLine ? "done-line" : ""}`} />
              )}
              <div
                className={[
                  "stg-row",
                  isActive ? "active" : "",
                  status === "done" ? "done" : "",
                  status === "partial" ? "partial" : "",
                  !unlocked ? "locked" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => unlocked && setActiveStage(st.id)}
              >
                <div
                  className="stg-icon"
                  style={
                    isActive
                      ? { borderColor: st.color, color: st.color, background: st.bg }
                      : status === "done"
                      ? { borderColor: "var(--teal)", background: "var(--teal)", color: "#fff" }
                      : status === "partial"
                      ? { borderColor: st.color, color: st.color, background: st.bg }
                      : {}
                  }
                >
                  {st.id}
                </div>
                <div className="stg-info">
                  <div className="stg-name">{st.name}</div>
                  <div className="stg-desc">{st.desc}</div>
                </div>
                <div
                  className={`stg-badge ${
                    status === "done"
                      ? "done"
                      : status === "partial"
                      ? "partial"
                      : !unlocked
                      ? "locked"
                      : "new"
                  }`}
                >
                  {status === "done"
                    ? "Done"
                    : status === "partial"
                    ? `${covCount}/${st.topics.length}`
                    : !unlocked
                    ? "Locked"
                    : `0/${st.topics.length}`}
                </div>
              </div>

              {isActive && unlocked && (
                <div className="topics">
                  {st.topics.map((t) => (
                    <div
                      key={t.id}
                      className={`topic ${t.covered ? "covered" : ""}`}
                      onClick={() => onTopicClick(t.title)}
                    >
                      <div className="topic-dot" />
                      <span>{t.title}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="side-progress">
        <div className="prog-head">
          <span>Overall Progress</span>
          <span>{coveredTopics}/{totalTopics}</span>
        </div>
        <div className="prog-track">
          <div className="prog-fill" style={{ width: progressPct + "%" }} />
        </div>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;