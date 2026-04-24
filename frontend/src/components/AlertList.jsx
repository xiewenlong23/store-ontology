import React from "react";

const DEFAULT_ALERTS = [
  { type: "success", emoji: "✓", title: "系统正常", detail: "暂无紧急提醒" },
];

export default function AlertList({ alerts = DEFAULT_ALERTS }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {DEFAULT_ALERTS.map((a, i) => (
          <div key={i} style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(22,163,74,0.06)", border: "1px solid rgba(22,163,74,0.10)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#16a34a" }}>{a.emoji}</span>
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: "#16a34a", margin: 0 }}>{a.title}</p>
              <p style={{ fontSize: 11, color: "var(--text-3)", margin: "1px 0 0" }}>{a.detail}</p>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {alerts.map((alert, i) => (
        <div
          key={i}
          className="animate"
          style={{
            animationDelay: `${i * 0.05}s`,
            padding: "8px 10px",
            borderRadius: 8,
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            ...(alert.type === "danger"
              ? { background: "rgba(220,38,38,0.06)", borderLeft: "3px solid #dc2626" }
              : { background: "rgba(217,119,6,0.06)", borderLeft: "3px solid #d97706" }
            )
          }}
        >
          <span style={{ fontSize: 13, flexShrink: 0 }}>{alert.type === "danger" ? "🚨" : "📦"}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 12, fontWeight: 600, margin: 0, color: alert.type === "danger" ? "#dc2626" : "#d97706" }}>
              {alert.title}
            </p>
            <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {alert.detail}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
