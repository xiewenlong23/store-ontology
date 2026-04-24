import React, { useState, useRef, useEffect } from "react";
import { unifiedChat } from "../api";

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", padding: "10px 14px" }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#0d9488", animation: "pulse-dot 1.2s ease-in-out infinite", opacity: 0.4 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#0d9488", animation: "pulse-dot 1.2s ease-in-out infinite 0.15s", opacity: 0.6 }} />
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#0d9488", animation: "pulse-dot 1.2s ease-in-out infinite 0.3s", opacity: 0.8 }} />
    </div>
  );
}

function TaskItem({ task }) {
  const STATUS_COLOR = { pending: "#fbbf24", confirmed: "#fbbf24", executed: "#60a5fa", reviewed: "#34d399", completed: "#34d399" };
  const color = STATUS_COLOR[task.status] || "#666";
  return (
    <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(0,0,0,0.04)", border: "1px solid var(--border)", marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {task.product_name || task.description || `任务 ${task.task_id?.slice(0, 6)}`}
        </p>
        <p style={{ fontSize: 10, color: "var(--text-3)", margin: "2px 0 0" }}>
          {task.category} · {task.original_stock}件 · {task.discount_rate != null ? `${Math.round(task.discount_rate * 100)}%折扣` : "—"}
        </p>
      </div>
      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 8, background: "rgba(0,0,0,0.06)", color: "#f59e0b", fontWeight: 700, whiteSpace: "nowrap" }}>
        {task.status === "pending" ? "待确认" : task.status === "confirmed" ? "已确认" : task.status === "executed" ? "执行中" : task.status === "reviewed" ? "已复核" : task.status === "completed" ? "已完成" : task.status}
      </span>
    </div>
  );
}

function ProductItem({ product }) {
  return (
    <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(0,0,0,0.04)", border: "1px solid var(--border)", marginBottom: 6 }}>
      <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", margin: 0 }}>{product.name || product.product_id}</p>
      <p style={{ fontSize: 10, color: "var(--text-3)", margin: "2px 0 0" }}>
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
      <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 18 }}>⚠️</span>
        <div>
          <p style={{ fontSize: 12, fontWeight: 700, color: "#f59e0b", margin: 0 }}>{result.exemption_reason || "豁免商品"}</p>
          <p style={{ fontSize: 10, color: "var(--text-3)", margin: "2px 0 0" }}>该商品不参与临期打折</p>
        </div>
      </div>
    );
  }
  return (
    <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(13,148,136,0.08)", border: "1px solid rgba(13,148,136,0.2)", display: "flex", alignItems: "center", gap: 12 }}>
      <span className="stat-num" style={{ fontSize: 28, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{Math.round(rate * 100)}%</span>
      <div>
        <p style={{ fontSize: 11, color: "var(--text-2)", margin: "0 0 2px" }}>建议折扣率</p>
        <p style={{ fontSize: 10, color: "var(--text-3)", margin: 0 }}>等级 {result.tier || "—"} · {result.reasoning || "—"}</p>
      </div>
    </div>
  );
}

function WelcomeMessage() {
  const QUICK_PROMPTS = [
    { label: "今日临期商品", icon: "📅", prompt: "帮我看看最近7天有哪些临期商品" },
    { label: "查询折扣规则", icon: "📋", prompt: "日配类的折扣规则是什么" },
    { label: "创建出清任务", icon: "✨", prompt: "帮我创建一个出清任务" },
    { label: "任务完成情况", icon: "📊", prompt: "今天任务完成情况怎么样" },
  ];
  const [prompts, setPrompts] = useState(QUICK_PROMPTS);

  return (
    <div>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "flex-start" }}>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: "rgba(13,148,136,0.10)", border: "1px solid rgba(13,148,136,0.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", margin: "0 0 3px" }}>门店大脑 AI</p>
          <p style={{ fontSize: 12, color: "var(--text-3)", margin: 0 }}>你好！有什么可以帮你的？</p>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
        {prompts.map((p) => (
          <button
            key={p.label}
            onClick={() => window.__chatSend && window.__chatSend(p.prompt)}
            style={{ padding: "10px 12px", borderRadius: 10, background: "rgba(0,0,0,0.04)", border: "1px solid var(--border)", cursor: "pointer", textAlign: "left", transition: "all 0.15s ease", display: "flex", alignItems: "center", gap: 8 }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.background = "rgba(13,148,136,0.08)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "rgba(0,0,0,0.04)"; }}
          >
            <span style={{ fontSize: 14 }}>{p.icon}</span>
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
  const [chatLoaded, setChatLoaded] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    setChatLoaded(true);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const msgText = text ?? input.trim();
    if (!msgText || loading) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", content: msgText };
    setMessages(m => [...m, userMsg]);
    const sentInput = msgText;
    if (!text) setInput("");
    setLoading(true);

    try {
      const data = await unifiedChat(sentInput);
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
          const prods = toolResult.products || toolResult.pending_products || toolResult.items || [];
          parts.push({ type: "products", items: prods });
        }
        if (toolResult.recommended_discount != null || toolResult.discount_rate != null) {
          parts.push({ type: "discount", data: toolResult });
        }
        if (toolResult.tasks) {
          parts.push({ type: "tasks", items: toolResult.tasks });
        }
      }

      const finalContent = parts.length > 0
        ? { text: response, parts }
        : response;

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
    if (typeof content === "string") return <span style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text)" }}>{content}</span>;
    if (!content) return null;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {content.text && <span style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text)" }}>{content.text}</span>}
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
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Messages */}
      <div style={{ flex: 1, overflow: "auto", padding: "4px 2px 8px", display: "flex", flexDirection: "column", gap: 10 }}>
        {chatLoaded && <WelcomeMessage />}
        {messages.map(m => (
          <div key={m.id} className="animate" style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            {m.role === "user" ? (
              <div className="msg-user" style={{ maxWidth: "82%", padding: "9px 13px" }}>
                <span style={{ fontSize: 13, color: "var(--accent)", fontWeight: 500 }}>{m.content}</span>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 9, alignItems: "flex-start", maxWidth: "90%" }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "rgba(13,148,136,0.10)", border: "1px solid rgba(13,148,136,0.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
                    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                  </svg>
                </div>
                <div className="msg-ai" style={{ padding: "10px 14px", flex: 1 }}>{renderContent(m.content)}</div>
              </div>
            )}
          </div>
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", paddingTop: 8, borderTop: "1px solid var(--border)", flexShrink: 0 }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="输入问题..."
          disabled={loading}
          className="ai-input"
          style={{ flex: 1, padding: "10px 14px", fontSize: 13 }}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="btn"
          style={{
            padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 700,
            background: input.trim() ? "var(--accent)" : "rgba(255,255,255,0.06)",
            color: input.trim() ? "#0a1614" : "var(--text-3)",
            border: "none", cursor: input.trim() ? "pointer" : "default",
            transition: "all 0.15s ease",
            boxShadow: input.trim() ? "0 0 14px rgba(13,148,136,0.20)" : "none",
          }}
        >
          发送
        </button>
      </div>
    </div>
  );
}
