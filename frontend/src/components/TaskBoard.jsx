import React, { useState, useEffect } from "react";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜",
  meat_poultry: "肉禽", seafood: "水产", dairy: "乳品",
  frozen: "冷冻", beverage: "饮品", snack: "休闲食品", grain_oil: "米面粮油",
};

const CAT_COLORS = {
  daily_fresh:  { accent: "#f87171", bg: "rgba(248,113,113,0.12)", text: "#f87171" },
  bakery:       { accent: "#60a5fa", bg: "rgba(96,165,250,0.12)", text: "#60a5fa" },
  fresh:       { accent: "#f87171", bg: "rgba(248,113,113,0.12)", text: "#f87171" },
  meat_poultry: { accent: "#c084fc", bg: "rgba(192,132,252,0.12)", text: "#c084fc" },
  seafood:     { accent: "#60a5fa", bg: "rgba(96,165,250,0.12)", text: "#60a5fa" },
  dairy:       { accent: "#34d399", bg: "rgba(52,211,153,0.12)", text: "#34d399" },
  frozen:      { accent: "#c084fc", bg: "rgba(192,132,252,0.12)", text: "#c084fc" },
  beverage:    { accent: "#34d399", bg: "rgba(52,211,153,0.12)", text: "#34d399" },
  snack:       { accent: "#60a5fa", bg: "rgba(96,165,250,0.12)", text: "#60a5fa" },
  grain_oil:   { accent: "#c084fc", bg: "rgba(192,132,252,0.12)", text: "#c084fc" },
};

const STATUS_DOT = {
  pending:   { color: "#fbbf24", label: "待处理" },
  confirmed: { color: "#fbbf24", label: "已确认" },
  executed:  { color: "#60a5fa", label: "执行中" },
  reviewed:  { color: "#34d399", label: "已复核" },
  completed: { color: "#34d399", label: "已完成" },
};

function TaskCard({ task, isDone }) {
  const cat = task.category || "daily_fresh";
  const catMeta = CAT_COLORS[cat] || CAT_COLORS.daily_fresh;
  const urgent = task.priority === "urgent" || task.risk_level === "high";
  const isExecuting = task.status === "executed";

  return (
    <div
      className="task-card"
      style={{
        padding: "12px 14px",
        borderRadius: 10,
        background: "var(--card-alt)",
        border: `1px solid ${isDone ? "rgba(255,255,255,0.04)" : isExecuting ? "rgba(96,165,250,0.2)" : "var(--border)"}`,
        borderLeft: isExecuting ? `2px solid ${catMeta.accent}` : undefined,
        opacity: isDone ? 0.55 : 1,
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 6, fontWeight: 600, background: catMeta.bg, color: catMeta.text }}>
            {CATEGORY_NAMES[cat] || cat}
          </span>
          {urgent && !isDone && (
            <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 5, background: "rgba(248,113,113,0.12)", color: "#f87171", fontWeight: 600 }} className="blink">
              紧急
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: STATUS_DOT[task.status]?.color || "#666", display: "inline-block", flexShrink: 0 }} />
          <span style={{ fontSize: 9, color: "var(--text-3)" }}>{STATUS_DOT[task.status]?.label || task.status}</span>
        </div>
      </div>

      {/* Product name */}
      <p style={{ fontSize: 13, fontWeight: 600, margin: "0 0 6px", color: isDone ? "var(--text-3)" : "var(--text)", textDecoration: isDone ? "line-through" : "none", textDecorationColor: "#34d399", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 8)}`}
      </p>

      {/* Meta row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {task.expiry_date && (
            <span style={{ fontSize: 10, color: "var(--text-3)" }}>
              📅 {task.expiry_date}
            </span>
          )}
          {task.original_stock && (
            <span style={{ fontSize: 10, color: "var(--text-3)" }}>
              📦 {task.original_stock}件
            </span>
          )}
        </div>
        {task.discount_rate != null && (
          <span className="stat-num" style={{ fontSize: 11, color: catMeta.text, fontWeight: 700 }}>
            {Math.round(task.discount_rate * 100)}%
          </span>
        )}
      </div>
    </div>
  );
}

function KanbanColumn({ label, color, tasks, isDone }) {
  if (tasks.length === 0) {
    return (
      <div style={{ padding: "12px", borderRadius: 10, border: "1px dashed rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "center", height: 80 }}>
        <span style={{ fontSize: 11, color: "var(--text-3)" }}>暂无任务</span>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {tasks.map((t, i) => (
        <div key={t.task_id} className="animate" style={{ animationDelay: `${i * 0.04}s` }}>
          <TaskCard task={t} isDone={isDone} />
        </div>
      ))}
    </div>
  );
}

export default function TaskBoard() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks().then(setTasks).catch(() => setTasks([])).finally(() => setLoading(false));
  }, []);

  const availableCategories = [...new Set(tasks.map(t => t.category).filter(Boolean))];
  const filtered = filter === "all" ? tasks : tasks.filter(t => t.category === filter);

  const todo       = filtered.filter(t => ["pending", "confirmed"].includes(t.status));
  const inProgress = filtered.filter(t => t.status === "executed");
  const done       = filtered.filter(t => ["reviewed", "completed"].includes(t.status));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", padding: "4px 2px" }}>
      {/* Filter chips */}
      <div style={{ display: "flex", gap: 6, flexWrap: "nowrap", overflowX: "auto", paddingBottom: 10, flexShrink: 0 }}>
        <button onClick={() => setFilter("all")} className={`chip ${filter === "all" ? "active" : ""}`}>全部</button>
        {availableCategories.map(cat => {
          const count = tasks.filter(t => t.category === cat).length;
          return (
            <button key={cat} onClick={() => setFilter(cat)} className={`chip ${filter === cat ? "active" : ""}`}>
              {CATEGORY_NAMES[cat] || cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Kanban grid */}
      {loading ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>加载中...</span>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, flex: 1, overflow: "auto", alignItems: "start" }}>
          {/* To Do */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10, padding: "0 2px" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#fbbf24", display: "inline-block", boxShadow: "0 0 6px #fbbf2480" }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: "#fbbf24" }}>待处理</span>
              <span className="stat-num" style={{ fontSize: 11, background: "rgba(251,191,36,0.1)", color: "#fbbf24", padding: "1px 7px", borderRadius: 8, fontWeight: 700 }}>{todo.length}</span>
            </div>
            <KanbanColumn tasks={todo} isDone={false} />
          </div>

          {/* In Progress */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10, padding: "0 2px" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#60a5fa", display: "inline-block", boxShadow: "0 0 6px #60a5fa80" }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: "#60a5fa" }}>进行中</span>
              <span className="stat-num" style={{ fontSize: 11, background: "rgba(96,165,250,0.1)", color: "#60a5fa", padding: "1px 7px", borderRadius: 8, fontWeight: 700 }}>{inProgress.length}</span>
            </div>
            <KanbanColumn tasks={inProgress} isDone={false} />
          </div>

          {/* Done */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10, padding: "0 2px" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#34d399", display: "inline-block", boxShadow: "0 0 6px #34d39980" }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: "#34d399" }}>已完成</span>
              <span className="stat-num" style={{ fontSize: 11, background: "rgba(52,211,153,0.1)", color: "#34d399", padding: "1px 7px", borderRadius: 8, fontWeight: 700 }}>{done.length}</span>
            </div>
            <KanbanColumn tasks={done} isDone={true} />
          </div>
        </div>
      )}
    </div>
  );
}
