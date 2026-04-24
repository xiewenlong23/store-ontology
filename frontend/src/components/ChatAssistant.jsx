import React, { useState, useRef, useEffect } from "react";
import { unifiedChat } from "../api";

const STATUS_COLOR = {
  pending: "#d97706", confirmed: "#d97706", executed: "#e07b39", reviewed: "#16a34a", completed: "#16a34a"
};

/* ════════════════════════════════════════════════════════════
   Chart Components
════════════════════════════════════════════════════════════ */

/* ── BarChart ─────────────────────────────────────── */
function BarChart({ title, data }) {
  if (!data || data.length === 0) return null;
  const maxVal = Math.max(...data.map(d => d.value), 1);
  const chartH = 110;
  const barW = 32;
  const gap = 16;
  const colors = ["#e07b39", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0369a1"];

  return (
    <div style={{ padding: "14px 16px", borderRadius: 14, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginTop: 4 }}>
      {title && <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-2)", margin: "0 0 14px", letterSpacing: "0.02em" }}>{title}</p>}
      <div style={{ display: "flex", alignItems: "flex-end", gap: gap, height: chartH }}>
        {data.map((d, i) => {
          const barH = Math.max((d.value / maxVal) * chartH, 4);
          const color = d.color || colors[i % colors.length];
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, flex: 1 }}>
              <span className="stat-num" style={{ fontSize: 12, fontWeight: 700, color }}>{d.value}</span>
              <div style={{ width: barW, height: barH, background: `linear-gradient(180deg, ${color}cc, ${color}55)`, borderRadius: "5px 5px 3px 3px", minHeight: 4, transition: "height 0.7s cubic-bezier(0.34,1.56,0.64,1)" }} />
              <span style={{ fontSize: 11, color: "var(--text-3)", textAlign: "center", whiteSpace: "nowrap" }}>{d.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── PieChart ─────────────────────────────────────── */
function PieChart({ title, data }) {
  if (!data || data.length === 0) return null;
  const total = data.reduce((s, d) => s + d.value, 0);
  const size = 120;
  const cx = size / 2;
  const cy = size / 2;
  const r = 48;
  const innerR = 28;

  let startAngle = -90;
  const slices = data.map((d, i) => {
    const angle = (d.value / total) * 360;
    const start = startAngle;
    startAngle += angle;
    const endAngle = startAngle;
    const largeArc = angle > 180 ? 1 : 0;
    const toRad = v => (v * Math.PI) / 180;

    const x1 = cx + r * Math.cos(toRad(start));
    const y1 = cy + r * Math.sin(toRad(start));
    const x2 = cx + r * Math.cos(toRad(endAngle));
    const y2 = cy + r * Math.sin(toRad(endAngle));
    const ix1 = cx + innerR * Math.cos(toRad(start));
    const iy1 = cy + innerR * Math.sin(toRad(start));
    const ix2 = cx + innerR * Math.cos(toRad(endAngle));
    const iy2 = cy + innerR * Math.sin(toRad(endAngle));

    const path = [
      `M ${x1} ${y1}`,
      `A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix2} ${iy2}`,
      `A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix1} ${iy1}`,
      "Z",
    ].join(" ");

    return { ...d, path, startAngle: start, endAngle };
  });

  return (
    <div style={{ padding: "14px 16px", borderRadius: 14, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginTop: 4 }}>
      {title && <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-2)", margin: "0 0 12px", letterSpacing: "0.02em" }}>{title}</p>}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {slices.map((s, i) => (
            <path key={i} d={s.path} fill={s.color || "#9ca3af"} stroke="var(--surface)" strokeWidth="2" />
          ))}
          <circle cx={cx} cy={cy} r={innerR - 4} fill="var(--surface)" />
          <text x={cx} y={cy - 4} textAnchor="middle" fontSize="14" fontWeight="700" fill="var(--text)" fontFamily="DM Sans, sans-serif">{total}</text>
          <text x={cx} y={cy + 12} textAnchor="middle" fontSize="10" fill="var(--text-3)">总计</text>
        </svg>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          {slices.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: s.color || "#9ca3af", flexShrink: 0, display: "inline-block" }} />
              <span style={{ fontSize: 12, color: "var(--text-2)", flex: 1 }}>{s.label}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>{s.value}</span>
              <span style={{ fontSize: 11, color: "var(--text-3)" }}>{total > 0 ? `${Math.round((s.value / total) * 100)}%` : "0%"}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── ScatterPlot ─────────────────────────────────── */
function ScatterPlot({ title, data, config }) {
  if (!data || data.length === 0) return null;
  const W = 280, H = 180, pad = { top: 16, right: 16, bottom: 36, left: 44 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const xMin = 0, xMax = Math.max(...data.map(d => d.x), 1) * 1.1;
  const yMin = 0, yMax = Math.max(...data.map(d => d.y), 1) * 1.1;

  const toX = x => pad.left + (x - xMin) / (xMax - xMin) * plotW;
  const toY = y => pad.top + plotH - (y - yMin) / (yMax - yMin) * plotH;

  const xTicks = 5;
  const yTicks = 4;

  return (
    <div style={{ padding: "14px 16px", borderRadius: 14, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginTop: 4 }}>
      {title && <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-2)", margin: "0 0 12px", letterSpacing: "0.02em" }}>{title}</p>}
      <svg width={W} height={H} style={{ display: "block" }}>
        {/* Grid */}
        {[...Array(yTicks + 1)].map((_, i) => {
          const y = pad.top + (i / yTicks) * plotH;
          const val = Math.round(yMax - (i / yTicks) * (yMax - yMin));
          return (
            <g key={i}>
              <line x1={pad.left} y1={y} x2={pad.left + plotW} y2={y} stroke="rgba(0,0,0,0.06)" strokeWidth="1" />
              <text x={pad.left - 6} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-3)">{val}</text>
            </g>
          );
        })}
        {[...Array(xTicks + 1)].map((_, i) => {
          const x = pad.left + (i / xTicks) * plotW;
          const val = Math.round(xMin + (i / xTicks) * (xMax - xMin));
          return (
            <g key={i}>
              <line x1={x} y1={pad.top} x2={x} y2={pad.top + plotH} stroke="rgba(0,0,0,0.06)" strokeWidth="1" />
              <text x={x} y={pad.top + plotH + 14} textAnchor="middle" fontSize="10" fill="var(--text-3)">{val}</text>
            </g>
          );
        })}
        {/* Axes */}
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + plotH} stroke="rgba(0,0,0,0.12)" strokeWidth="1.5" />
        <line x1={pad.left} y1={pad.top + plotH} x2={pad.left + plotW} y2={pad.top + plotH} stroke="rgba(0,0,0,0.12)" strokeWidth="1.5" />
        {/* Points */}
        {data.map((d, i) => (
          <circle key={i} cx={toX(d.x)} cy={toY(d.y)} r="5" fill="#e07b39" opacity="0.75" stroke="#ffffff" strokeWidth="1.5" />
        ))}
        {/* Labels */}
        <text x={pad.left + plotW / 2} y={H - 4} textAnchor="middle" fontSize="10" fill="var(--text-3)">{config?.xLabel || "X"}</text>
        <text x={10} y={pad.top + plotH / 2} textAnchor="middle" fontSize="10" fill="var(--text-3)" transform={`rotate(-90, 10, ${pad.top + plotH / 2})`}>{config?.yLabel || "Y"}</text>
      </svg>
    </div>
  );
}

/* ── TableChart ────────────────────────────────────── */
function TableChart({ title, columns, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div style={{ borderRadius: 14, border: "1px solid var(--border)", overflow: "hidden", marginTop: 4 }}>
      {title && (
        <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.02)", borderBottom: "1px solid var(--border)" }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: "var(--text-2)", margin: 0 }}>{title}</p>
        </div>
      )}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600, color: "var(--text-3)", background: "rgba(0,0,0,0.02)", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : "rgba(0,0,0,0.015)" }}>
                {row.map((cell, j) => (
                  <td key={j} style={{ padding: "9px 12px", color: "var(--text)", borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : "none", whiteSpace: "nowrap" }}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── ASCII chart detector ──────────────────────────── */
function detectChart(text) {
  if (!text || typeof text !== "string") return null;
  const lines = text.split("\n");
  const chartLines = [];
  let inChart = false;

  for (const line of lines) {
    if (line.includes("┤") || line.includes("├")) {
      inChart = true;
      chartLines.push(line);
    } else if (inChart && (line.includes("█") || line.match(/^\d+\s*[┤├│]/))) {
      chartLines.push(line);
    } else if (inChart && chartLines.length > 0) {
      if (line.match(/[\u4e00-\u9fff]|[0-9]+天/)) {
        chartLines.push(line);
      } else {
        inChart = false;
      }
    }
  }

  if (chartLines.length < 2) return null;

  const bottomLine = chartLines[chartLines.length - 1];
  const labels = bottomLine.trim().split(/\s+/).filter(l => l.length > 0);

  const barPositions = [];
  for (const ln of chartLines) {
    const yMatch = ln.match(/^(\d+)\s*[┤├│]/);
    if (!yMatch) continue;
    const barPart = ln.replace(/^\d+\s*[┤├│]\s*/, "");
    const barGroups = barPart.match(/█+/g) || [];
    barGroups.forEach((bar, i) => {
      if (!barPositions[i]) barPositions[i] = 0;
      barPositions[i] = Math.max(barPositions[i], parseInt(yMatch[1]));
    });
  }

  if (barPositions.length === 0) return null;
  return barPositions.map((val, i) => ({ label: labels[i] || `${i}`, value: val })).filter(d => d.label);
}

/* ════════════════════════════════════════════════════════════
   UI Components
════════════════════════════════════════════════════════════ */

/* ── TypingIndicator ───────────────────────────────── */
function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", padding: "8px 0" }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#e07b39", animation: "pulse-dot 1s ease-in-out infinite", opacity: 0.4 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#e07b39", animation: "pulse-dot 1s ease-in-out infinite 0.15s", opacity: 0.6 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#e07b39", animation: "pulse-dot 1s ease-in-out infinite 0.3s", opacity: 0.8 }} />
    </div>
  );
}

/* ── TaskItem ───────────────────────────────────────── */
function TaskItem({ task }) {
  const color = STATUS_COLOR[task.status] || "#9ca3af";
  return (
    <div style={{ padding: "11px 13px", borderRadius: 10, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 6)}`}
        </p>
        <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>
          {task.category} · {task.original_stock}件 · {task.discount_rate != null ? `${Math.round(task.discount_rate * 100)}%折扣` : "—"}
        </p>
      </div>
      <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 8, background: `${color}15`, color, fontWeight: 600, whiteSpace: "nowrap" }}>
        {["pending","confirmed"].includes(task.status) ? "待确认" : task.status === "executed" ? "执行中" : ["reviewed","completed"].includes(task.status) ? "已完成" : task.status}
      </span>
    </div>
  );
}

/* ── ProductItem ─────────────────────────────────────── */
function ProductItem({ product }) {
  return (
    <div style={{ padding: "11px 13px", borderRadius: 10, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginBottom: 6 }}>
      <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", margin: 0 }}>{product.name || product.product_id}</p>
      <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>
        {product.category} · 库存 {product.stock} · 到期 {product.expiry_date || "—"}
      </p>
    </div>
  );
}

/* ── DiscountCard ────────────────────────────────────── */
function DiscountCard({ result }) {
  const rate = result.recommended_discount || result.discount_rate || 0;
  const exempt = result.exemption_type != null;
  if (exempt) {
    return (
      <div style={{ padding: "14px 16px", borderRadius: 14, background: "rgba(217,119,6,0.08)", border: "1px solid rgba(217,119,6,0.15)", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 20 }}>⚠️</span>
        <div>
          <p style={{ fontSize: 14, fontWeight: 700, color: "#d97706", margin: 0 }}>{result.exemption_reason || "豁免商品"}</p>
          <p style={{ fontSize: 12, color: "var(--text-3)", margin: "2px 0 0" }}>该商品不参与临期打折</p>
        </div>
      </div>
    );
  }
  return (
    <div style={{ padding: "14px 16px", borderRadius: 14, background: "rgba(224,123,57,0.08)", border: "1px solid rgba(224,123,57,0.15)", display: "flex", alignItems: "center", gap: 14 }}>
      <span className="stat-num" style={{ fontSize: 36, fontWeight: 700, color: "#e07b39", lineHeight: 1 }}>{Math.round(rate * 100)}%</span>
      <div>
        <p style={{ fontSize: 13, color: "var(--text-2)", margin: "0 0 2px" }}>建议折扣率</p>
        <p style={{ fontSize: 12, color: "var(--text-3)", margin: 0 }}>等级 {result.tier || "—"} · {result.reasoning || "—"}</p>
      </div>
    </div>
  );
}

/* ── WelcomeMessage ───────────────────────────────────── */
function WelcomeMessage({ onSend }) {
  const quickPrompts = [
    { label: "今日临期商品", icon: "📅", prompt: "帮我看看最近7天有哪些临期商品" },
    { label: "查询折扣规则", icon: "📋", prompt: "日配类的折扣规则是什么" },
    { label: "创建出清任务", icon: "✨", prompt: "帮我创建一个出清任务" },
    { label: "任务完成情况", icon: "📊", prompt: "今天任务完成情况怎么样" },
  ];

  return (
    <div style={{ paddingBottom: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 16 }}>
        <div style={{ width: 38, height: 38, borderRadius: 12, background: "linear-gradient(135deg, #e07b39, #c96a2d)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 2px 8px rgba(224,123,57,0.3)" }}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
        <div>
          <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", margin: "0 0 2px" }}>门店大脑 AI</p>
          <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0 }}>你好！有什么可以帮你的？</p>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {quickPrompts.map((p) => (
          <button
            key={p.label}
            onClick={() => onSend(p.prompt)}
            style={{ padding: "11px 13px", borderRadius: 12, background: "var(--surface)", border: "1px solid var(--border)", cursor: "pointer", textAlign: "left", display: "flex", alignItems: "center", gap: 9, transition: "all 0.15s", boxShadow: "var(--shadow-sm)" }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "#e07b39"; e.currentTarget.style.background = "rgba(224,123,57,0.05)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "var(--surface)"; }}
          >
            <span style={{ fontSize: 16 }}>{p.icon}</span>
            <span style={{ fontSize: 13, color: "var(--text-2)", fontWeight: 500 }}>{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   Main Chat Component
════════════════════════════════════════════════════════════ */
export default function ChatAssistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const msgText = text ?? input.trim();
    if (!msgText || loading) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", content: msgText };
    setMessages(m => [...m, userMsg]);
    if (!text) setInput("");
    setLoading(true);

    try {
      const data = await unifiedChat(msgText);
      const rawResponse = data.response || "（无响应）";

      let response = rawResponse
        .replace(/```json\n?\{[\s\S]*?\}\n?```/g, "")
        .replace(/\{[\s\S]*?"tool"[\s\S]*?\}/g, "")
        .replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, "")
        .replace(/<toolcall>[\s\S]*?<\/toolcall>/gi, "")
        .replace(/<tool name="[^"]*">[\s\S]*?<\/tool>/gi, "")
        .trim();

      const toolResult = data.tool_result || {};
      const parts = [];

      // Chart parts (rendered in priority order)
      const chartType = toolResult.chart_type;
      if (chartType === "pie" && toolResult.pie_data) {
        parts.push({ type: "chart", chartType: "pie", data: toolResult.pie_data });
      } else if (chartType === "scatter" && toolResult.scatter_data) {
        parts.push({ type: "chart", chartType: "scatter", data: toolResult.scatter_data, config: toolResult.scatter_config });
      } else if (toolResult.chart_data) {
        // Bar chart (default, also from ASCII detection in text)
        parts.push({ type: "chart", chartType: "bar", data: toolResult.chart_data });
      }

      // Table
      if (toolResult.table_data) {
        parts.push({ type: "table", ...toolResult.table_data });
      }

      // Products
      if (toolResult.products || toolResult.pending_products || toolResult.items) {
        parts.push({ type: "products", items: toolResult.products || toolResult.pending_products || toolResult.items || [] });
      }

      // Discount
      if (toolResult.recommended_discount != null || toolResult.discount_rate != null) {
        parts.push({ type: "discount", data: toolResult });
      }

      // Tasks
      if (toolResult.tasks) {
        parts.push({ type: "tasks", items: toolResult.tasks });
      }

      const finalContent = parts.length > 0 ? { text: response, parts } : response;
      setMessages(m => [...m, { id: crypto.randomUUID(), role: "assistant", content: finalContent }]);
      if (data.needs_confirmation) {
        setMessages(m => [...m, { id: crypto.randomUUID(), role: "assistant", content: "（请确认以上信息是否正确）" }]);
      }
    } catch (err) {
      setMessages(m => [...m, { id: crypto.randomUUID(), role: "assistant", content: `请求失败：${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { window.__chatSend = send; }, []);

  /* ── Content renderer ── */
  const renderContent = (content) => {
    if (typeof content === "string") {
      // Check for ASCII chart in plain text
      const chartData = detectChart(content);
      if (chartData) {
        const chartIdx = content.search(/[\n\r][\s\S]*?[█┤├│][\s\S]*$/m);
        const textBefore = chartIdx > 0 ? content.slice(0, chartIdx).trim() : "";
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {textBefore && <span style={{ fontSize: 14, lineHeight: 1.7 }}>{textBefore}</span>}
            <BarChart data={chartData} />
          </div>
        );
      }
      return <span style={{ fontSize: 14, lineHeight: 1.7 }}>{content}</span>;
    }

    if (!content) return null;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {content.text && (() => {
          const chartData = detectChart(content.text);
          if (chartData) {
            const chartIdx = content.text.search(/[\n\r][\s\S]*?[█┤├│][\s\S]*$/m);
            const textBefore = chartIdx > 0 ? content.text.slice(0, chartIdx).trim() : "";
            return (
              <>
                {textBefore && <span style={{ fontSize: 14, lineHeight: 1.7 }}>{textBefore}</span>}
                <BarChart data={chartData} />
              </>
            );
          }
          return <span style={{ fontSize: 14, lineHeight: 1.7 }}>{content.text}</span>;
        })()}
        {content.parts?.map((part, i) => {
          if (part.type === "chart") {
            if (part.chartType === "pie") return <PieChart key={i} title={part.data.title} data={part.data} />;
            if (part.chartType === "scatter") return <ScatterPlot key={i} title={part.config?.title} data={part.data} config={part.config} />;
            return <BarChart key={i} data={part.data} />;
          }
          if (part.type === "table") return <TableChart key={i} title={part.title} columns={part.columns} rows={part.rows} />;
          if (part.type === "products") return part.items.map((p, j) => <ProductItem key={j} product={p} />);
          if (part.type === "tasks") return part.items.slice(0, 5).map((t, j) => <TaskItem key={j} task={t} />);
          if (part.type === "discount") return <DiscountCard key={i} result={part.data} />;
          return null;
        })}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", padding: "14px 16px" }}>
      <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: 12, paddingBottom: 8 }}>
        <WelcomeMessage onSend={send} />
        {messages.map(m => (
          <div key={m.id} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            {m.role === "user" ? (
              <div className="msg-user">{m.content}</div>
            ) : (
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start", maxWidth: "92%" }}>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: "rgba(224,123,57,0.10)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#e07b39" strokeWidth="2" strokeLinecap="round">
                    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                  </svg>
                </div>
                <div className="msg-ai" style={{ flex: 1 }}>{renderContent(m.content)}</div>
              </div>
            )}
          </div>
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", paddingTop: 12, borderTop: "1px solid var(--border)" }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="输入问题..."
          disabled={loading}
          className="ai-input"
          style={{ flex: 1, padding: "11px 15px" }}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="btn"
          style={{
            padding: "11px 20px", borderRadius: 12, fontSize: 14, fontWeight: 700,
            background: input.trim() ? "linear-gradient(135deg, #e07b39, #c96a2d)" : "rgba(0,0,0,0.06)",
            color: input.trim() ? "#ffffff" : "var(--text-3)",
            border: "none", cursor: input.trim() ? "pointer" : "default",
            boxShadow: input.trim() ? "0 2px 8px rgba(224,123,57,0.3)" : "none",
          }}
        >
          发送
        </button>
      </div>
    </div>
  );
}
