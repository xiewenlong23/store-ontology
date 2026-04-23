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
  return <span className="stat-num" style={{ fontSize: 13, color: "var(--text-2)" }}>{time}</span>;
}

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", padding: "16px 20px", gap: 14, position: "relative", zIndex: 1 }}>

      {/* ── Header ── */}
      <header className="animate stagger-1" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Logo mark */}
          <div style={{ width: 38, height: 38, borderRadius: 10, background: "var(--card)", border: "1px solid var(--border-strong)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 20px var(--accent-glow)" }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em", margin: 0, lineHeight: 1.2 }}>门店大脑</h1>
            <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0", fontFamily: "var(--mono)" }}>万达广场店 · 实时运营</p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Status badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "6px 14px", borderRadius: 20, background: "var(--card)", border: "1px solid var(--border-strong)", fontSize: 12 }}>
            <span className="live-dot" style={{ width: 7, height: 7, borderRadius: "50%", background: "#34d399", display: "inline-block" }} />
            <span style={{ color: "#34d399", fontWeight: 600, fontSize: 11 }}>营业中</span>
            <span style={{ color: "var(--text-3)" }}>09:00 – 22:00</span>
          </div>

          {/* Clock */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 20, background: "var(--card)", border: "1px solid var(--border)", fontSize: 12 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <LiveClock />
          </div>

          {/* New task */}
          <button className="btn" style={{ padding: "8px 18px", borderRadius: 10, background: "var(--accent)", color: "#0a1614", fontWeight: 700, fontSize: 13, border: "none", letterSpacing: "-0.01em" }}>
            + 新建任务
          </button>
        </div>
      </header>

      {/* ── Stats strip ── */}
      <div className="animate stagger-2">
        <DashboardStats />
      </div>

      {/* ── Bottom: Task Board | AI ── */}
      <div className="animate stagger-3" style={{ display: "flex", gap: 14, flex: 1, overflow: "hidden", minHeight: 0 }}>
        {/* Task Board */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 4px 10px", flexShrink: 0 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", letterSpacing: "0.02em" }}>任务看板</span>
          </div>
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <TaskBoard />
          </div>
        </div>

        {/* AI Assistant */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 4px 10px", flexShrink: 0 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", letterSpacing: "0.02em" }}>AI 助手</span>
          </div>
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <ChatAssistant />
          </div>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
