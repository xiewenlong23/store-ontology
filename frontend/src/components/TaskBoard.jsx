import React, { useState, useEffect } from "react";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜",
  meat_poultry: "肉禽", seafood: "水产", dairy: "乳品",
  frozen: "冷冻", beverage: "饮品", snack: "休闲食品", grain_oil: "米面粮油",
};

const CAT_COLORS = {
  daily_fresh:  { accent: "#e07b39", bg: "rgba(224,123,57,0.10)", text: "#c96a2d" },
  bakery:       { accent: "#e07b39", bg: "rgba(224,123,57,0.10)", text: "#c96a2d" },
  fresh:        { accent: "#dc2626", bg: "rgba(220,38,38,0.10)", text: "#dc2626" },
  meat_poultry: { accent: "#d97706", bg: "rgba(217,119,6,0.10)", text: "#d97706" },
  seafood:      { accent: "#0369a1", bg: "rgba(3,105,161,0.10)", text: "#0369a1" },
  dairy:        { accent: "#16a34a", bg: "rgba(22,163,74,0.10)", text: "#16a34a" },
  frozen:       { accent: "#7c3aed", bg: "rgba(124,58,237,0.10)", text: "#7c3aed" },
  beverage:     { accent: "#16a34a", bg: "rgba(22,163,74,0.10)", text: "#16a34a" },
  snack:        { accent: "#d97706", bg: "rgba(217,119,6,0.10)", text: "#d97706" },
  grain_oil:    { accent: "#92400e", bg: "rgba(146,64,14,0.10)", text: "#92400e" },
};

const STATUS_CONFIG = {
  pending:   { color: "#d97706", bg: "rgba(217,119,6,0.10)", label: "待确认" },
  confirmed: { color: "#d97706", bg: "rgba(217,119,6,0.10)", label: "已确认" },
  executed:  { color: "#e07b39", bg: "rgba(224,123,57,0.10)", label: "执行中" },
  reviewed:  { color: "#16a34a", bg: "rgba(22,163,74,0.10)", label: "已复核" },
  completed: { color: "#16a34a", bg: "rgba(22,163,74,0.10)", label: "已完成" },
};

function TaskCard({ task }) {
  const cat = task.category || "daily_fresh";
  const catMeta = CAT_COLORS[cat] || CAT_COLORS.daily_fresh;
  const urgent = task.priority === "urgent" || task.risk_level === "high";
  const isDone = ["reviewed", "completed"].includes(task.status);
  const statusCfg = STATUS_CONFIG[task.status] || { color: "#9ca3af", bg: "rgba(0,0,0,0.06)", label: task.status };

  return (
    <div
      style={{
        background: "var(--surface)",
        border: `1px solid ${isDone ? "rgba(0,0,0,0.05)" : "var(--border)"}`,
        borderRadius: 12,
        padding: "13px 15px",
        marginBottom: 8,
        opacity: isDone ? 0.6 : 1,
        borderLeft: `3px solid ${catMeta.accent}`,
        transition: "all 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, fontWeight: 600, background: catMeta.bg, color: catMeta.text }}>
            {CATEGORY_NAMES[cat] || cat}
          </span>
          {urgent && (
            <span className="blink" style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(220,38,38,0.08)", color: "#dc2626", fontWeight: 700 }}>
              紧急
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, padding: "3px 9px", borderRadius: 6, background: statusCfg.bg, color: statusCfg.color, fontWeight: 600 }}>
          {statusCfg.label}
        </span>
      </div>

      <p style={{
        fontSize: 14, fontWeight: 600,
        color: isDone ? "var(--text-3)" : "var(--text)",
        margin: "0 0 10px",
        textDecoration: isDone ? "line-through" : "none",
        textDecorationColor: statusCfg.color,
        lineHeight: 1.4
      }}>
        {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 8)}`}
      </p>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 10 }}>
          {task.expiry_date && (
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>📅 {task.expiry_date}</span>
          )}
          {task.original_stock && (
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>📦 {task.original_stock} 件</span>
          )}
        </div>
        {task.discount_rate != null && (
          <span className="stat-num" style={{ fontSize: 14, color: catMeta.text, fontWeight: 700 }}>
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
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, padding: "0 2px" }}>
        <span style={{ width: 9, height: 9, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{label}</span>
        <span style={{ fontSize: 12, padding: "2px 9px", borderRadius: 20, background: `${color}15`, color, fontWeight: 700, marginLeft: 2 }}>
          {count}
        </span>
      </div>
      <div style={{ flex: 1 }}>
        {tasks.length === 0 ? (
          <div style={{ padding: 28, textAlign: "center", borderRadius: 12, border: "1px dashed rgba(0,0,0,0.08)", background: "rgba(0,0,0,0.02)" }}>
            <span style={{ fontSize: 13, color: "var(--text-3)" }}>暂无任务</span>
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
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", padding: "14px 16px" }}>
      {/* Filter */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 14, flexShrink: 0 }}>
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
          <span style={{ fontSize: 14, color: "var(--text-3)" }}>加载中...</span>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, flex: 1, overflow: "auto", alignItems: "start" }}>
          <KanbanColumn label="待处理" count={todo.length} color="#d97706" tasks={todo} />
          <KanbanColumn label="进行中" count={inProgress.length} color="#e07b39" tasks={inProgress} />
          <KanbanColumn label="已完成" count={done.length} color="#16a34a" tasks={done} />
        </div>
      )}
    </div>
  );
}
