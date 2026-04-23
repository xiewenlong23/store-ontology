import React, { useState, useEffect, useRef } from "react";
import AlertList from "./AlertList";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜",
  meat_poultry: "肉禽", seafood: "水产", dairy: "乳品",
  frozen: "冷冻", beverage: "饮品", snack: "休闲食品", grain_oil: "米面粮油",
};

const CATEGORY_COLORS = {
  daily_fresh:  { accent: "#f87171", bg: "rgba(248,113,113,0.08)" },
  bakery:       { accent: "#60a5fa", bg: "rgba(96,165,250,0.08)" },
  fresh:       { accent: "#f87171", bg: "rgba(248,113,113,0.08)" },
  meat_poultry: { accent: "#c084fc", bg: "rgba(192,132,252,0.08)" },
  seafood:     { accent: "#60a5fa", bg: "rgba(96,165,250,0.08)" },
  dairy:       { accent: "#34d399", bg: "rgba(52,211,153,0.08)" },
  frozen:      { accent: "#c084fc", bg: "rgba(192,132,252,0.08)" },
  beverage:    { accent: "#34d399", bg: "rgba(52,211,153,0.08)" },
  snack:       { accent: "#60a5fa", bg: "rgba(96,165,250,0.08)" },
  grain_oil:   { accent: "#c084fc", bg: "rgba(192,132,252,0.08)" },
};

function ProgressRing({ percent }) {
  const [animated, setAnimated] = useState(0);
  const radius = 38;
  const circ = 2 * Math.PI * radius;
  const offset = circ * (1 - animated / 100);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(percent), 200);
    return () => clearTimeout(timer);
  }, [percent]);

  return (
    <div style={{ position: "relative", width: 96, height: 96 }}>
      <svg width="96" height="96" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="48" cy="48" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="7" />
        <circle
          cx="48" cy="48" r={radius} fill="none"
          stroke="var(--accent)" strokeWidth="7"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.34,1.56,0.64,1)" }}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 1 }}>
        <span className="stat-num" style={{ fontSize: 22, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{animated}%</span>
        <span style={{ fontSize: 9, color: "var(--text-3)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: 2 }}>完成</span>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color, delay }) {
  return (
    <div className="animate" style={{ animationDelay: `${delay}s`, padding: "14px 16px", borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="section-label">{label}</span>
      <span className="stat-num" style={{ fontSize: 26, fontWeight: 700, color: color || "var(--text)", lineHeight: 1 }}>{value}</span>
      {sub && <span style={{ fontSize: 10, color: "var(--text-3)" }}>{sub}</span>}
    </div>
  );
}

function CategoryCard({ name, count, color, bg }) {
  return (
    <div style={{ borderRadius: 10, border: "1px solid var(--border)", background: bg, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 6, cursor: "default" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "var(--text-3)", letterSpacing: "0.06em", textTransform: "uppercase" }}>{name}</span>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block", opacity: 0.8 }} />
      </div>
      <span className="stat-num" style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1 }}>{count}</span>
      <div style={{ fontSize: 9, color: "var(--text-3)" }}>件商品</div>
    </div>
  );
}

export default function DashboardStats() {
  const [tasks, setTasks] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchTasks().catch(() => []),
      fetch("/api/inventory/inventory/low-stock").then(r => r.json()).catch(() => []),
      fetch("/api/inventory/inventory/near-expiry").then(r => r.json()).catch(() => []),
    ]).then(([taskData, lowStock, nearExpiry]) => {
      setTasks(taskData);

      const items = [];
      for (const inv of lowStock) {
        items.push({ type: "warn", emoji: "⚡", title: "库存告急", detail: `${inv.product_id} 库存 ${inv.quantity} 件` });
      }
      for (const inv of nearExpiry) {
        items.push({ type: "danger", emoji: "🚨", title: "临期预警", detail: `${inv.product_id} · ${inv.location || "未知库位"}` });
      }
      setAlerts(items);
    }).finally(() => setLoading(false));
  }, []);

  const total = tasks.length;
  const completed = tasks.filter(t => ["reviewed", "completed"].includes(t.status)).length;
  const inProgress = tasks.filter(t => t.status === "executed").length;
  const pending = tasks.filter(t => ["pending", "confirmed"].includes(t.status)).length;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  const catCounts = {};
  for (const t of tasks) {
    const c = t.category || "daily_fresh";
    catCounts[c] = (catCounts[c] || 0) + 1;
  }

  const topCats = Object.entries(catCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([cat, count]) => {
      const meta = CATEGORY_COLORS[cat] || { accent: "#60a5fa", bg: "rgba(96,165,250,0.08)" };
      return { cat, count, name: CATEGORY_NAMES[cat] || cat, ...meta };
    });

  // Pad to 4 slots
  while (topCats.length < 4) {
    topCats.push({ cat: "empty", count: 0, name: "—", accent: "var(--text-3)", bg: "rgba(255,255,255,0.02)" });
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 260px", gap: 14, height: 130 }}>
      {/* Left: Progress + stats */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="card animate stagger-1" style={{ flex: 1, padding: "16px 18px", display: "flex", alignItems: "center", gap: 16 }}>
          <ProgressRing percent={percent} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span className="stat-num" style={{ fontSize: 28, fontWeight: 700 }}>{completed}</span>
              <span style={{ fontSize: 11, color: "var(--text-3)" }}>/ {total}</span>
            </div>
            <div style={{ height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${percent}%`, background: "var(--accent)", borderRadius: 2, transition: "width 1s cubic-bezier(0.34,1.56,0.64,1)" }} />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#fbbf24", display: "inline-block" }} />
                <span className="stat-num" style={{ fontSize: 12, color: "#fbbf24" }}>{pending}</span>
                <span style={{ fontSize: 10, color: "var(--text-3)" }}>待处理</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#60a5fa", display: "inline-block" }} />
                <span className="stat-num" style={{ fontSize: 12, color: "#60a5fa" }}>{inProgress}</span>
                <span style={{ fontSize: 10, color: "var(--text-3)" }}>进行中</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Center: Category breakdown */}
      <div className="card animate stagger-2" style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        {topCats.map((c, i) => (
          <div key={c.cat} style={{ animationDelay: `${0.1 + i * 0.05}s` }}>
            <CategoryCard name={c.name} count={loading ? "—" : c.count} color={c.accent} bg={c.bg} />
          </div>
        ))}
      </div>

      {/* Right: Alerts */}
      <div className="card animate stagger-3" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <span className="section-label">紧急提醒</span>
          {alerts.length > 0 && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(248,113,113,0.1)", color: "#f87171", fontWeight: 600 }}>
              {alerts.length}条
            </span>
          )}
        </div>
        <div style={{ flex: 1, overflow: "auto" }}>
          <AlertList alerts={alerts} />
        </div>
      </div>
    </div>
  );
}
