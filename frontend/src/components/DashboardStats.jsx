import React, { useState, useEffect } from "react";
import AlertList from "./AlertList";
import { fetchTasks } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜",
  meat_poultry: "肉禽", seafood: "水产", dairy: "乳品",
  frozen: "冷冻", beverage: "饮品", snack: "休闲食品", grain_oil: "米面粮油",
};

const CATEGORY_COLORS = {
  daily_fresh:  { accent: "#0d9488", bg: "rgba(13,148,136,0.10)", text: "#0d9488" },
  bakery:       { accent: "#0d9488", bg: "rgba(13,148,136,0.10)", text: "#0d9488" },
  fresh:       { accent: "#dc2626", bg: "rgba(220,38,38,0.10)", text: "#dc2626" },
  meat_poultry: { accent: "#d97706", bg: "rgba(217,119,6,0.10)", text: "#d97706" },
  seafood:     { accent: "#0369a1", bg: "rgba(3,105,161,0.10)", text: "#0369a1" },
  dairy:       { accent: "#16a34a", bg: "rgba(22,163,74,0.10)", text: "#16a34a" },
  frozen:      { accent: "#7c3aed", bg: "rgba(124,58,237,0.10)", text: "#7c3aed" },
  beverage:    { accent: "#16a34a", bg: "rgba(22,163,74,0.10)", text: "#16a34a" },
  snack:       { accent: "#d97706", bg: "rgba(217,119,6,0.10)", text: "#d97706" },
  grain_oil:   { accent: "#92400e", bg: "rgba(146,64,14,0.10)", text: "#92400e" },
};

function ProgressRing({ percent }) {
  const [animated, setAnimated] = useState(0);
  const radius = 32;
  const circ = 2 * Math.PI * radius;
  const offset = circ * (1 - animated / 100);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(percent), 300);
    return () => clearTimeout(timer);
  }, [percent]);

  return (
    <div style={{ position: "relative", width: 80, height: 80, flexShrink: 0 }}>
      <svg width="80" height="80" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="40" cy="40" r={radius} fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="6" />
        <circle
          cx="40" cy="40" r={radius} fill="none"
          stroke="var(--accent)" strokeWidth="6"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.34,1.56,0.64,1)" }}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span className="stat-num" style={{ fontSize: 20, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{animated}%</span>
      </div>
    </div>
  );
}

function CategoryCard({ name, count, color, bg }) {
  return (
    <div style={{ borderRadius: 10, border: "1px solid var(--border)", background: bg, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "var(--text-3)", fontWeight: 500 }}>{name}</span>
        <span style={{ width: 5, height: 5, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />
      </div>
      <span className="stat-num" style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{count}</span>
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
        items.push({ type: "warn", emoji: "📦", title: "库存告急", detail: `${inv.product_id} 仅剩 ${inv.quantity} 件` });
      }
      for (const inv of nearExpiry) {
        items.push({ type: "danger", emoji: "⏰", title: "临期预警", detail: `${inv.product_id} · ${inv.location || "未知库位"}` });
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
      const meta = CATEGORY_COLORS[cat] || { accent: "#6b7280", bg: "rgba(0,0,0,0.04)", text: "#6b7280" };
      return { cat, count, name: CATEGORY_NAMES[cat] || cat, ...meta };
    });

  while (topCats.length < 4) {
    topCats.push({ cat: "empty", count: 0, name: "—", accent: "var(--text-3)", bg: "rgba(0,0,0,0.03)", text: "var(--text-3)" });
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "160px 1fr 200px", gap: 12, alignItems: "stretch" }}>

      {/* Left: Progress + stats */}
      <div className="card" style={{ padding: "16px 18px", display: "flex", alignItems: "center", gap: 14 }}>
        <ProgressRing percent={percent} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
            <span className="stat-num" style={{ fontSize: 26, fontWeight: 700, color: "var(--text)" }}>{completed}</span>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>/ {total} 件</span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: "rgba(0,0,0,0.06)", overflow: "hidden", marginBottom: 10 }}>
            <div style={{ height: "100%", width: `${percent}%`, background: "var(--accent)", borderRadius: 2, transition: "width 1s cubic-bezier(0.34,1.56,0.64,1)" }} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--warn)", display: "inline-block" }} />
              <span className="stat-num" style={{ fontSize: 12, color: "var(--warn)" }}>{pending}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
              <span className="stat-num" style={{ fontSize: 12, color: "var(--accent)" }}>{inProgress}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Center: Category breakdown */}
      <div className="card" style={{ padding: "14px 16px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {topCats.map((c, i) => (
          <CategoryCard key={c.cat} name={c.name} count={loading ? "—" : c.count} color={c.accent} bg={c.bg} />
        ))}
      </div>

      {/* Right: Alerts */}
      <div className="card" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 6, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="section-label">紧急提醒</span>
          {alerts.length > 0 && (
            <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(220,38,38,0.08)", color: "var(--danger)", fontWeight: 600 }}>
              {alerts.length} 条
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