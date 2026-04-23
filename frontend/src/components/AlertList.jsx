import React from "react";

const DEFAULT_ALERTS = [
  { type: "danger", emoji: "🚨", title: "暂无数据", detail: "系统正常" },
];

export default function AlertList({ alerts = DEFAULT_ALERTS }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="space-y-2 flex-1 overflow-auto">
        <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-500/10 border-l-2 border-emerald-500">
          <span className="text-sm text-emerald-400">✅</span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-emerald-400">系统正常</p>
            <p className="text-xs text-white/40">暂无紧急提醒</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2 flex-1 overflow-auto">
      {alerts.map((alert, i) => (
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
