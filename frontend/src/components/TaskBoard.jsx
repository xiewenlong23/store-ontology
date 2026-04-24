import React, { useState, useEffect } from "react";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜",
  meat_poultry: "肉禽", seafood: "水产", dairy: "乳品",
  frozen: "冷冻", beverage: "饮品", snack: "休闲食品", grain_oil: "米面粮油",
};

const CAT_COLORS = {
  daily_fresh:  { accent: "var(--accent)", bg: "var(--accent-light)", text: "var(--accent)" },
  bakery:       { accent: "var(--accent)", bg: "var(--accent-light)", text: "var(--accent)" },
  fresh:       { accent: "var(--danger)", bg: "rgba(248,81,73,0.10)", text: "var(--danger)" },
  meat_poultry: { accent: "var(--warn)", bg: "rgba(210,153,34,0.10)", text: "var(--warn)" },
  seafood:     { accent: "#0369a1", bg: "rgba(3,105,161,0.10)", text: "#0369a1" },
  dairy:       { accent: "var(--success)", bg: "rgba(63,185,80,0.10)", text: "var(--success)" },
  frozen:      { accent: "#7c3aed", bg: "rgba(124,58,237,0.10)", text: "#7c3aed" },
  beverage:    { accent: "var(--success)", bg: "rgba(63,185,80,0.10)", text: "var(--success)" },
  snack:       { accent: "var(--warn)", bg: "rgba(210,153,34,0.10)", text: "var(--warn)" },
  grain_oil:   { accent: "#92400e", bg: "rgba(146,64,14,0.10)", text: "#92400e" },
};

const STATUS_CONFIG = {
  pending:   { color: "var(--warn)", label: "待确认" },
  confirmed: { color: "var(--warn)", label: "已确认" },
  executed:  { color: "var(--accent)", label: "执行中" },
  reviewed:  { color: "var(--success)", label: "已复核" },
  completed: { color: "var(--success)", label: "已完成" },
};

function TaskCard({ task }) {
  const cat = task.category || "daily_fresh";
  const catMeta = CAT_COLORS[cat] || CAT_COLORS.daily_fresh;
  const urgent = task.priority === "urgent" || task.risk_level === "high";
  const isDone = ["reviewed", "completed"].includes(task.status);
  const statusCfg = STATUS_CONFIG[task.status] || { color: "#9ca3af", label: task.status };

  return (
    <div
      style={{
        background: "var(--card)",
        border: `1px solid ${isDone ? "rgba(0,0,0,0.04)" : "var(--border)"}`,
        borderRadius: 12,
        padding: "12px 14px",
        marginBottom: 8,
        opacity: isDone ? 0.65 : 1,
        borderLeft: `3px solid ${catMeta.accent}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 6, fontWeight: 600, background: catMeta.bg, color: catMeta.text }}>
            {CATEGORY_NAMES[cat] || cat}
          </span>
          {urgent && (
            <span className="blink" style={{ fontSize: 9, padding: "2px 5px", borderRadius: 4, background: "rgba(220,38,38,0.08)", color: "#dc2626", fontWeight: 600 }}>
              紧急
            </span>
          )}
        </div>
        <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, background: `${statusCfg.color}12`, color: statusCfg.color, fontWeight: 600 }}>
          {statusCfg.label}
        </span>
      </div>

      <p style={{ fontSize: 14, fontWeight: 600, color: isDone ? "var(--text-3)" : "var(--text)", margin: "0 0 8px", textDecoration: isDone ? "line-through" : "none", textDecorationColor: statusCfg.color }}>
        {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 8)}`}
      </p>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 10 }}>
          {task.expiry_date && (
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>📅 {task.expiry_date}</span>
          )}
          {task.original_stock && (
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>📦 {task.original_stock} 件</span>
          )}
        </div>
        {task.discount_rate != null && (
          <span className="stat-num" style={{ fontSize: 13, color: catMeta.text, fontWeight: 700 }}>
            {Math.round(task.discount_rate * 100)}%
          </span>
        )}
      </div>
    </div>
  );
}

function KanbanColumn({ label, count, color, tasks }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, padding: "0 2px" }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{label}</span>
        <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 20, background: `${color}14`, color, fontWeight: 700, marginLeft: 2 }}>
          {count}
        </span>
      </div>
      <div style={{ flex: 1 }}>
        {tasks.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", borderRadius: 12, border: "1px dashed rgba(0,0,0,0.08)", background: "rgba(0,0,0,0.02)" }}>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>暂无任务</span>
          </div>
        ) : (
          tasks.map((t, i) => (
            <div key={t.task_id} className="animate" style={{ animationDelay: `${i * 0.04}s` }}>
              <TaskCard task={t} />
            </div>
          ))
        )}
      </div>
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
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", padding: "12px 16px" }}>
      {/* Filter */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 12, flexShrink: 0 }}>
        <button onClick={() => setFilter("all")} className={`chip ${filter === "all" ? "active" : ""}`}>
          全部 ({tasks.length})
        </button>
        {availableCategories.map(cat => {
          const count = tasks.filter(t => t.category === cat).length;
          return (
            <button key={cat} onClick={() => setFilter(cat)} className={`chip ${filter === cat ? "active" : ""}`}>
              {CATEGORY_NAMES[cat] || cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Kanban */}
      {loading ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 13, color: "var(--text-3)" }}>加载中...</span>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, flex: 1, overflow: "auto", alignItems: "start" }}>
          <KanbanColumn label="待处理" count={todo.length} color="#d97706" tasks={todo} />
          <KanbanColumn label="进行中" count={inProgress.length} color="#0d9488" tasks={inProgress} />
          <KanbanColumn label="已完成" count={done.length} color="#16a34a" tasks={done} />
        </div>
      )}
    </div>
  );
}