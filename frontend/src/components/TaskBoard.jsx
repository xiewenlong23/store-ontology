import React, { useState, useEffect } from "react";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配",
  bakery: "烘焙",
  fresh: "生鲜",
  meat_poultry: "肉禽",
  seafood: "水产",
  dairy: "乳品",
  frozen: "冷冻",
  beverage: "饮品",
  snack: "休闲食品",
  grain_oil: "米面粮油",
};

const CATEGORY_STYLE = {
  daily_fresh: { bg: "oklch(0.7 0.18 25 / 0.3)", color: "oklch(0.9 0.15 25)" },
  bakery:       { bg: "oklch(0.7 0.15 200 / 0.3)", color: "oklch(0.9 0.12 200)" },
  fresh:       { bg: "oklch(0.7 0.18 25 / 0.3)", color: "oklch(0.9 0.15 25)" },
  meat_poultry: { bg: "oklch(0.7 0.15 340 / 0.3)", color: "oklch(0.9 0.15 340)" },
  seafood:     { bg: "oklch(0.7 0.15 200 / 0.3)", color: "oklch(0.9 0.12 200)" },
  dairy:       { bg: "oklch(0.7 0.15 160 / 0.3)", color: "oklch(0.9 0.12 160)" },
  frozen:      { bg: "oklch(0.7 0.15 340 / 0.3)", color: "oklch(0.9 0.15 340)" },
  beverage:    { bg: "oklch(0.7 0.15 160 / 0.3)", color: "oklch(0.9 0.12 160)" },
  snack:       { bg: "oklch(0.7 0.15 200 / 0.3)", color: "oklch(0.9 0.12 200)" },
  grain_oil:   { bg: "oklch(0.7 0.15 340 / 0.3)", color: "oklch(0.9 0.15 340)" },
};

function TaskCard({ task, isDone }) {
  const cat = task.category || "daily_fresh";
  const style = CATEGORY_STYLE[cat] || CATEGORY_STYLE.daily_fresh;
  const label = CATEGORY_NAMES[cat] || cat;
  const urgent = task.priority === "urgent" || task.risk_level === "high";

  return (
    <div
      className={`task-card card p-3 ${isDone ? "opacity-70" : ""}`}
      style={!isDone && task.status === "executed" ? { borderLeft: "3px solid var(--accent)" } : {}}
    >
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span
          className="text-xs px-2 py-0.5 rounded"
          style={{ background: style.bg, color: style.color }}
        >
          {label}
        </span>
        {urgent && !isDone && <span className="text-xs text-red-400 blink">紧急</span>}
        {task.status === "executed" && (
          <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">执行中</span>
        )}
      </div>
      <p className={`text-sm font-medium mb-2 ${isDone ? "line-through decoration-emerald-400" : ""}`}>
        {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 8)}`}
      </p>
      <div className="flex items-center justify-between text-xs text-white/40">
        <span>
          {task.expiry_date ? `🕙 ${task.expiry_date}` : task.updated_at ? `🕙 ${task.updated_at.slice(0, 10)}` : "全天"}
        </span>
        <span>🏪 {task.store_id || "未知门店"}</span>
      </div>
    </div>
  );
}

export default function TaskBoard({ filter: externalFilter = "all", onFilterChange }) {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState(externalFilter);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks()
      .then(setTasks)
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setFilter(externalFilter);
  }, [externalFilter]);

  // Dynamically derive available categories from data
  const availableCategories = [...new Set(tasks.map((t) => t.category).filter(Boolean))];

  const handleFilterChange = (val) => {
    setFilter(val);
    if (onFilterChange) onFilterChange(val);
  };

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.category === filter);

  const todo = filtered.filter((t) => ["pending", "confirmed"].includes(t.status));
  const inProgress = filtered.filter((t) => t.status === "executed");
  const done = filtered.filter((t) => ["reviewed", "completed"].includes(t.status));

  if (loading) {
    return <div className="text-center py-8 text-white/50">加载中...</div>;
  }

  return (
    <div className="p-4 h-full overflow-auto">
      {/* Category filter chips */}
      <div className="flex gap-2 flex-wrap mb-4">
        <button
          onClick={() => handleFilterChange("all")}
          className={`text-xs px-3 py-1 rounded-full transition ${filter === "all" ? "tab-active" : "bg-white/10 text-white/60 hover:bg-white/20"}`}
        >
          全部 ({tasks.length})
        </button>
        {availableCategories.map((cat) => {
          const count = tasks.filter((t) => t.category === cat).length;
          return (
            <button
              key={cat}
              onClick={() => handleFilterChange(cat)}
              className={`text-xs px-3 py-1 rounded-full transition ${filter === cat ? "tab-active" : "bg-white/10 text-white/60 hover:bg-white/20"}`}
            >
              {CATEGORY_NAMES[cat] || cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Kanban */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-full">
        {/* To Do */}
        <div className="bg-white/5 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-white/70 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              待处理
            </h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400">{todo.length}</span>
          </div>
          <div className="space-y-3">
            {todo.length === 0 && <p className="text-xs text-white/30">暂无</p>}
            {todo.map((t) => <TaskCard key={t.task_id} task={t} isDone={false} />)}
          </div>
        </div>

        {/* In Progress */}
        <div className="bg-white/5 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-white/70 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              进行中
            </h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">{inProgress.length}</span>
          </div>
          <div className="space-y-3">
            {inProgress.length === 0 && <p className="text-xs text-white/30">暂无</p>}
            {inProgress.map((t) => <TaskCard key={t.task_id} task={t} isDone={false} />)}
          </div>
        </div>

        {/* Done */}
        <div className="bg-white/5 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-white/70 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              已完成
            </h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">{done.length}</span>
          </div>
          <div className="space-y-3">
            {done.length === 0 && <p className="text-xs text-white/30">暂无</p>}
            {done.map((t) => <TaskCard key={t.task_id} task={t} isDone={true} />)}
          </div>
        </div>
      </div>
    </div>
  );
}
