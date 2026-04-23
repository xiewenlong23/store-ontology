import React from "react";

const DEFAULT_ALERTS = [
  { type: "success", emoji: "✓", title: "系统正常", detail: "暂无紧急提醒" },
];

export default function AlertList({ alerts = DEFAULT_ALERTS }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {DEFAULT_ALERTS.map((a, i) => (
          <div key={i} style={{ padding: "8px 10px", borderRadius: 8, background: "rgba(92,184,92,0.06)", border: "1px solid rgba(92,184,92,0.12)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#5cb85c" }}>{a.emoji}</span>
            <div>
              <p style={{ fontSize: 11, fontWeight: 600, color: "#5cb85c", margin: 0 }}>{a.title}</p>
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
              ? { background: "rgba(217,97,74,0.06)", border: "1px solid rgba(217,97,74,0.1)" }
              : { background: "rgba(230,162,60,0.06)", border: "1px solid rgba(230,162,60,0.1)" }
            )
          }}
        >
          <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>
            {alert.type === "danger" ? "🚨" : "⚡"}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 11, fontWeight: 600, margin: 0, color: alert.type === "danger" ? "#d9614a" : "#e6a23c", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
