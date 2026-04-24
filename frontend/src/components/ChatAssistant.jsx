import React, { useState, useRef, useEffect } from "react";
import { unifiedChat } from "../api";

const STATUS_COLOR = {
  pending: "var(--warn)", confirmed: "var(--warn)", executed: "var(--accent)", reviewed: "var(--success)", completed: "var(--success)"
};

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", padding: "8px 0" }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", animation: "pulse-dot 1s ease-in-out infinite", opacity: 0.4 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", animation: "pulse-dot 1s ease-in-out infinite 0.15s", opacity: 0.6 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", animation: "pulse-dot 1s ease-in-out infinite 0.3s", opacity: 0.8 }} />
    </div>
  );
}

function TaskItem({ task }) {
  const color = STATUS_COLOR[task.status] || "#9ca3af";
  return (
    <div style={{ padding: "10px 12px", borderRadius: 10, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 6)}`}
        </p>
        <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>
          {task.category} · {task.original_stock}件 · {task.discount_rate != null ? `${Math.round(task.discount_rate * 100)}%折扣` : "—"}
        </p>
      </div>
      <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 8, background: `${color}12`, color, fontWeight: 600, whiteSpace: "nowrap" }}>
        {STATUS_COLOR[task.status] ? ["pending","confirmed"].includes(task.status) ? "待确认" : task.status === "executed" ? "执行中" : ["reviewed","completed"].includes(task.status) ? "已完成" : task.status : task.status}
      </span>
    </div>
  );
}

function ProductItem({ product }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 10, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", marginBottom: 6 }}>
      <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", margin: 0 }}>{product.name || product.product_id}</p>
      <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>
        {product.category} · 库存 {product.stock} · 到期 {product.expiry_date || "—"}
      </p>
    </div>
  );
}

function DiscountCard({ result }) {
  const rate = result.recommended_discount || result.discount_rate || 0;
  const exempt = result.exemption_type != null;
  if (exempt) {
    return (
      <div style={{ padding: "12px 14px", borderRadius: 12, background: "var(--warn)", border: "1px solid var(--warn)", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 18 }}>⚠️</span>
        <div>
          <p style={{ fontSize: 13, fontWeight: 700, color: "var(--warn)", margin: 0 }}>{result.exemption_reason || "豁免商品"}</p>
          <p style={{ fontSize: 11, color: "var(--text-3)", margin: "2px 0 0" }}>该商品不参与临期打折</p>
        </div>
      </div>
    );
  }
  return (
    <div style={{ padding: "12px 14px", borderRadius: 12, background: "var(--accent)", border: "1px solid var(--accent)", display: "flex", alignItems: "center", gap: 12 }}>
      <span className="stat-num" style={{ fontSize: 30, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{Math.round(rate * 100)}%</span>
      <div>
        <p style={{ fontSize: 12, color: "var(--text-2)", margin: "0 0 2px" }}>建议折扣率</p>
        <p style={{ fontSize: 11, color: "var(--text-3)", margin: 0 }}>等级 {result.tier || "—"} · {result.reasoning || "—"}</p>
      </div>
    </div>
  );
}

function WelcomeMessage({ onSend }) {
  const quickPrompts = [
    { label: "今日临期商品", icon: "📅", prompt: "帮我看看最近7天有哪些临期商品" },
    { label: "查询折扣规则", icon: "📋", prompt: "日配类的折扣规则是什么" },
    { label: "创建出清任务", icon: "✨", prompt: "帮我创建一个出清任务" },
    { label: "任务完成情况", icon: "📊", prompt: "今天任务完成情况怎么样" },
  ];

  return (
    <div style={{ paddingBottom: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 14 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", margin: "0 0 2px" }}>门店大脑 AI</p>
          <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0 }}>你好！有什么可以帮你的？</p>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {quickPrompts.map((p) => (
          <button
            key={p.label}
            onClick={() => onSend(p.prompt)}
            style={{ padding: "10px 12px", borderRadius: 10, background: "rgba(0,0,0,0.03)", border: "1px solid var(--border)", cursor: "pointer", textAlign: "left", display: "flex", alignItems: "center", gap: 8, transition: "all 0.15s" }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.background = "rgba(13,148,136,0.06)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "rgba(0,0,0,0.03)"; }}
          >
            <span style={{ fontSize: 15 }}>{p.icon}</span>
            <span style={{ fontSize: 12, color: "var(--text-2)" }}>{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

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

      const toolResult = data.tool_result;
      const parts = [];
      if (toolResult) {
        if (toolResult.products || toolResult.pending_products || toolResult.items) {
          parts.push({ type: "products", items: toolResult.products || toolResult.pending_products || toolResult.items || [] });
        }
        if (toolResult.recommended_discount != null || toolResult.discount_rate != null) {
          parts.push({ type: "discount", data: toolResult });
        }
        if (toolResult.tasks) {
          parts.push({ type: "tasks", items: toolResult.tasks });
        }
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

  const renderContent = (content) => {
    if (typeof content === "string") return <span style={{ fontSize: 14, lineHeight: 1.7 }}>{content}</span>;
    if (!content) return null;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {content.text && <span style={{ fontSize: 14, lineHeight: 1.7 }}>{content.text}</span>}
        {content.parts?.map((part, i) => {
          if (part.type === "products") return part.items.map((p, j) => <ProductItem key={j} product={p} />);
          if (part.type === "tasks") return part.items.slice(0, 5).map((t, j) => <TaskItem key={j} task={t} />);
          if (part.type === "discount") return <DiscountCard key={i} result={part.data} />;
          return null;
        })}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", padding: "12px 16px" }}>
      <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: 12, paddingBottom: 8 }}>
        <WelcomeMessage onSend={send} />
        {messages.map(m => (
          <div key={m.id} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            {m.role === "user" ? (
              <div className="msg-user">{m.content}</div>
            ) : (
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start", maxWidth: "92%" }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "rgba(13,148,136,0.10)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0d9488" strokeWidth="2" strokeLinecap="round">
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
      <div style={{ display: "flex", gap: 8, alignItems: "center", paddingTop: 10, borderTop: "1px solid var(--border)" }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="输入问题..."
          disabled={loading}
          className="ai-input"
          style={{ flex: 1, padding: "10px 14px" }}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="btn"
          style={{
            padding: "10px 18px", borderRadius: 10, fontSize: 13, fontWeight: 700,
            background: input.trim() ? "var(--accent)" : "rgba(0,0,0,0.06)",
            color: input.trim() ? "#ffffff" : "var(--text-3)",
            border: "none", cursor: input.trim() ? "pointer" : "default",
          }}
        >
          发送
        </button>
      </div>
    </div>
  );
}