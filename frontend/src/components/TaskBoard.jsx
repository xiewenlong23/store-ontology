import React, { useState, useEffect } from "react";
import { fetchTasks } from "../api";

const TYPE_STYLE = {
  expiry: { bg: "oklch(0.7 0.18 25 / 0.3)", color: "oklch(0.9 0.15 25)" },
  price: { bg: "oklch(0.7 0.15 200 / 0.3)", color: "oklch(0.9 0.12 200)" },
  stock: { bg: "oklch(0.7 0.15 160 / 0.3)", color: "oklch(0.9 0.12 160)" },
  food: { bg: "oklch(0.7 0.18 340 / 0.3)", color: "oklch(0.9 0.15 340)" },
};

const TYPE_NAME = {
  expiry: "临期出清",
  price: "价签更新",
  stock: "上货补货",
  food: "食品加工",
};

function TaskCard({ task, isDone }) {
  const typeStyle = TYPE_STYLE[task.task_type] || TYPE_STYLE.stock;
  const urgent = task.priority === "urgent";

  return (
    <div
      className={`task-card card p-3 ${isDone ? "opacity-70" : ""}`}
      style={!isDone && task.status === "executed" ? { borderLeft: "3px solid var(--accent)" } : {}}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="text-xs px-2 py-0.5 rounded"
          style={{ background: typeStyle.bg, color: typeStyle.color }}
        >
          {TYPE_NAME[task.task_type] || task.task_type}
        </span>
        {urgent && !isDone && <span className="text-xs text-red-400 blink">紧急</span>}
      </div>
      <p className={`text-sm font-medium mb-2 ${isDone ? "line-through decoration-emerald-400" : ""}`}>
        {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 8)}`}
      </p>
      {task.status === "executed" && task.executed_by && (
        <div className="w-full bg-white/10 rounded-full h-1.5 mb-2">
          <div className="h-full rounded-full bg-emerald-400" style={{ width: "70%" }} />
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-white/40">
        <span>
          {task.expiry_date ? `🕙 ${task.expiry_date} 截止` : task.updated_at ? `🕙 ${task.updated_at}` : "全天"}
        </span>
        <span>👤 {task.assigned_to_name || task.assigned_to || "未分配"}</span>
      </div>
    </div>
  );
}

export default function TaskBoard({ filter: externalFilter = "all" }) {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState(externalFilter);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks()
      .then(setTasks)
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  // Sync external filter changes
  useEffect(() => {
    setFilter(externalFilter);
  }, [externalFilter]);

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.task_type === filter);

  const todo = filtered.filter((t) => ["pending", "confirmed"].includes(t.status));
  const inProgress = filtered.filter((t) => t.status === "executed");
  const done = filtered.filter((t) => ["reviewed", "completed"].includes(t.status));

  if (loading) {
    return <div className="text-center py-8 text-white/50">加载中...</div>;
  }

  return (
    <div className="p-4 h-full overflow-auto">
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
            {todo.map((t) => (
              <TaskCard key={t.task_id} task={t} isDone={false} />
            ))}
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
            {inProgress.map((t) => (
              <TaskCard key={t.task_id} task={t} isDone={false} />
            ))}
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
            {done.map((t) => (
              <TaskCard key={t.task_id} task={t} isDone={true} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export { TaskBoard as TaskBoardComponent };
