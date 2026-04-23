import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import DashboardStats from "./components/DashboardStats";
import TaskBoard from "./components/TaskBoard";
import ChatAssistant from "./components/ChatAssistant";
import "./index.css";

function LiveClock() {
  const [time, setTime] = useState(() => {
    const now = new Date();
    return now.toLocaleTimeString("zh-CN", { hour12: false });
  });

  useEffect(() => {
    const id = setInterval(() => {
      setTime(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return <span className="font-mono text-white/60">{time}</span>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState("board");
  const [filterType, setFilterType] = useState("all");

  return (
    <div className="flex flex-col min-h-screen p-4 md:p-6 text-white">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "var(--accent)" }}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold">门店本体AI</h1>
              <p className="text-xs text-white/50">万达广场店 · 今日运营</p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full text-xs" style={{ background: "oklch(0.25 0.08 160 / 0.5)" }}>
            <span className="w-2 h-2 rounded-full bg-emerald-400 live-dot" />
            <span className="text-emerald-400">营业中</span>
            <span className="text-white/50">·</span>
            <span className="text-white/70">9:00 - 22:00</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-white/60">
            <LiveClock />
          </div>
          <button
            className="btn px-4 py-2 rounded-lg text-sm font-medium"
            style={{ background: "var(--accent)" }}
          >
            + 新建任务
          </button>
        </div>
      </header>

      {/* Top Dashboard */}
      <DashboardStats />

      {/* Bottom Tabs */}
      <div className="card flex-1 overflow-hidden" style={{ height: "67vh" }}>
        {/* Tab Bar */}
        <div className="flex border-b border-white/10">
          <button
            onClick={() => setActiveTab("board")}
            className={`px-6 py-3 text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === "board" ? "tab-active" : "text-white/60 hover:text-white"
            }`}
          >
            <span>📋</span> 任务看板
          </button>
          <button
            onClick={() => setActiveTab("ai")}
            className={`px-6 py-3 text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === "ai" ? "tab-active" : "text-white/60 hover:text-white"
            }`}
          >
            <span>🤖</span> AI 助手
          </button>
          <div className="flex-1" />
          <div className="flex items-center px-4 text-xs text-white/50">
            <span className="mr-2">筛选:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-transparent text-white/70 text-xs focus:outline-none cursor-pointer"
            >
              <option value="all">全部任务</option>
              <option value="expiry">临期出清</option>
              <option value="price">价签更新</option>
              <option value="stock">上货补货</option>
              <option value="food">食品加工</option>
            </select>
          </div>
        </div>

        {/* Tab Content */}
        <div className="h-full overflow-hidden">
          {activeTab === "board" ? (
            <TaskBoard filter={filterType} />
          ) : (
            <div className="p-4 h-full flex flex-col">
              <div className="flex-1 overflow-auto">
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
