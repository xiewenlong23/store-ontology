import React from "react";

const ALERTS = [
  {
    type: "danger",
    emoji: "🚨",
    title: "鲜食过期预警",
    detail: "三明治区 5件 · 10:30前",
  },
  {
    type: "warn",
    emoji: "⚡",
    title: "价签不一致",
    detail: "生鲜区 3件 · 11:00前",
  },
  {
    type: "warn",
    emoji: "📋",
    title: "库存告急",
    detail: "矿泉水低于 20%",
  },
];

export default function AlertList() {
  return (
    <div className="space-y-2 flex-1 overflow-auto">
      {ALERTS.map((alert, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 p-2 rounded-lg border-l-2 ${
            alert.type === "danger"
              ? "bg-red-500/10 border-red-500"
              : "bg-amber-500/10 border-amber-500"
          }`}
        >
          <span className={`text-sm ${alert.type === "danger" ? "text-red-400" : "text-amber-400"}`}>
            {alert.emoji}
          </span>
          <div className="flex-1 min-w-0">
            <p className={`text-xs font-medium truncate ${alert.type === "danger" ? "text-red-400" : "text-amber-400"}`}>
              {alert.title}
            </p>
            <p className="text-xs text-white/40">{alert.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
