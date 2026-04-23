import React from "react";

const DEFAULT_ALERTS = [
  { type: "warn", emoji: "✓", title: "系统正常", detail: "暂无紧急提醒" },
];

export default function AlertList({ alerts = DEFAULT_ALERTS }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {DEFAULT_ALERTS.map((a, i) => (
          <div key={i} style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(52,211,153,0.06)", border: "1px solid rgba(52,211,153,0.12)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#34d399" }}>{a.emoji}</span>
            <div>
              <p style={{ fontSize: 11, fontWeight: 600, color: "#34d399", margin: 0 }}>{a.title}</p>
              <p style={{ fontSize: 9, color: "var(--text-3)", margin: "1px 0 0" }}>{a.detail}</p>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {alerts.map((alert, i) => (
        <div
          key={i}
          className="animate"
          style={{ animationDelay: `${i * 0.06}s`, padding: "8px 10px", borderRadius: 8, display: "flex", alignItems: "flex-start", gap: 9,
            ...(alert.type === "danger"
              ? { background: "rgba(248,113,113,0.06)", border: "1px solid rgba(248,113,113,0.1)" }
              : { background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.1)" }
            )
          }}
        >
          <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>
            {alert.type === "danger" ? "🚨" : "⚡"}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: alert.type === "danger" ? "#f87171" : "#fbbf24", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {alert.title}
            </p>
            <p style={{ fontSize: 9, color: "var(--text-3)", margin: "2px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {alert.detail}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
