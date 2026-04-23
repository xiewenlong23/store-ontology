import React from "react";
import AlertList from "./AlertList";

const CATEGORIES = [
  { emoji: "⏰", label: "临期出清", count: 5, style: "oklch(0.7 0.18 25 / 0.5)", textColor: "oklch(0.9 0.15 25)" },
  { emoji: "🏷️", label: "价签更新", count: 3, style: "oklch(0.7 0.15 200 / 0.5)", textColor: "oklch(0.9 0.12 200)" },
  { emoji: "📦", label: "上货补货", count: 8, style: "oklch(0.7 0.15 160 / 0.5)", textColor: "oklch(0.9 0.12 160)" },
  { emoji: "🍳", label: "食品加工", count: 4, style: "oklch(0.7 0.15 340 / 0.5)", textColor: "oklch(0.9 0.15 340)" },
];

export default function DashboardStats({ completed = 15, total = 20, yesterdayDelta = 12 }) {
  const percent = Math.round((completed / total) * 100);
  const circumference = 2 * Math.PI * 40; // r=40
  const dashoffset = circumference * (1 - percent / 100);

  return (
    <div className="grid grid-cols-12 gap-4 mb-4" style={{ height: "33vh", minHeight: 200 }}>
      {/* Left: Overall Progress */}
      <div className="col-span-3 card p-4 flex flex-col">
        <p className="text-xs text-white/50 mb-3">今日完成率</p>
        <div className="flex items-center gap-4 flex-1">
          <div className="relative w-24 h-24">
            <svg className="w-24 h-24 progress-ring" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="40" fill="none" stroke="oklch(1 0 0 / 0.1)" strokeWidth="8" />
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="var(--accent)"
                strokeWidth="8"
                strokeDasharray={circumference}
                strokeDashoffset={dashoffset}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold">{percent}%</span>
            </div>
          </div>
          <div>
            <p className="text-3xl font-bold">
              {completed}
              <span className="text-base text-white/50">/{total}</span>
            </p>
            <p className="text-xs text-white/50">任务已完成</p>
            <p className="text-xs text-emerald-400 mt-2">↑ {yesterdayDelta}% 较昨日</p>
          </div>
        </div>
      </div>

      {/* Center: Task Categories */}
      <div className="col-span-5 card p-4">
        <p className="text-xs text-white/50 mb-3">作业分类</p>
        <div className="grid grid-cols-4 gap-3 h-[calc(100%-1.5rem)]">
          {CATEGORIES.map((cat) => (
            <div
              key={cat.label}
              className="p-3 rounded-lg flex flex-col justify-center"
              style={{ background: cat.style }}
            >
              <span className="text-lg mb-1">{cat.emoji}</span>
              <span className="text-2xl font-bold" style={{ color: cat.textColor }}>
                {cat.count}
              </span>
              <span className="text-xs text-white/50">{cat.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Alerts */}
      <div className="col-span-4 card p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs text-white/50">紧急提醒</p>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400">3条</span>
        </div>
        <AlertList />
      </div>
    </div>
  );
}
