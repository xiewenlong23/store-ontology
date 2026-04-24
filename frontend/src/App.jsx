import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import DashboardStats from "./components/DashboardStats";
import TaskBoard from "./components/TaskBoard";
import ChatAssistant from "./components/ChatAssistant";
import "./index.css";

function LiveClock() {
  const [time, setTime] = useState(() =>
    new Date().toLocaleTimeString("zh-CN", { hour12: false })
  );
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString("zh-CN", { hour12: false })), 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="stat-num" style={{ fontSize: 13, color: "var(--text)" }}>{time}</span>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState("tasks");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg)", overflow: "hidden" }}>

      {/* ── Header ── */}
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 24px", background: "var(--card)", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", margin: 0, lineHeight: 1.2 }}>门店大脑</h1>
            <p style={{ fontSize: 12, color: "var(--text-3)", margin: "3px 0 0" }}>万达广场店 · 实时运营</p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 20, background: "var(--accent-light)", border: "1px solid rgba(88,166,255,0.15)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--success)" }}>营业中</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 20, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)" }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <LiveClock />
          </div>
        </div>
      </header>

      {/* ── Stats strip ── */}
      <div style={{ padding: "14px 24px", flexShrink: 0, background: "var(--bg)" }}>
        <DashboardStats />
      </div>

      {/* ── Bottom panel with tabs ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "0 24px 16px" }}>
        {/* Tab bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, paddingBottom: 12 }}>
          <button onClick={() => setActiveTab("tasks")} className={`tab ${activeTab === "tasks" ? "active" : ""}`}>
            任务看板
          </button>
          <button onClick={() => setActiveTab("ai")} className={`tab ${activeTab === "ai" ? "active" : ""}`}>
            AI 助手
          </button>
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {activeTab === "tasks" ? (
            <div className="card" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
                <span className="section-label">今日任务</span>
              </div>
              <div style={{ flex: 1, overflow: "hidden" }}>
                <TaskBoard />
              </div>
            </div>
          ) : (
            <div className="card" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
                <span className="section-label">AI 助手</span>
              </div>
              <div style={{ flex: 1, overflow: "hidden" }}>
                <ChatAssistant />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);