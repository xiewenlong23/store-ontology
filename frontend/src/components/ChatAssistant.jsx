import React from "react";
import { unifiedChat } from "../api";

// 状态标签颜色
const STATUS_LABEL = {
  pending: { text: "待确认", cls: "bg-yellow-500/20 text-yellow-400" },
  confirmed: { text: "已确认", cls: "bg-blue-500/20 text-blue-400" },
  executed: { text: "已执行", cls: "bg-purple-500/20 text-purple-400" },
  reviewed: { text: "已复核", cls: "bg-green-500/20 text-green-400" },
  completed: { text: "已完成", cls: "bg-gray-500/20 text-gray-400" },
};

function TaskCard({ task }) {
  const status = STATUS_LABEL[task.status] || { text: task.status, cls: "bg-white/10 text-white/70" };
  return (
    <div className="card p-3 text-sm">
      <div className="flex justify-between items-start mb-1">
        <span className="font-medium">{task.product_name}</span>
        <span className={`text-xs px-2 py-0.5 rounded ${status.cls}`}>{status.text}</span>
      </div>
      <div className="text-white/50 text-xs space-y-0.5">
        <div>门店: {task.store_id} | 商品: {task.product_id}</div>
        <div>折扣率: {task.discount_rate != null ? Math.round(task.discount_rate * 100) : "-"}%</div>
        <div>原价库存: {task.original_stock} | 截止: {task.expiry_date}</div>
        {task.task_id && <div className="text-white/30">ID: {task.task_id.slice(0, 8)}...</div>}
      </div>
    </div>
  );
}

function TaskList({ tasks, title }) {
  if (!tasks || tasks.length === 0) {
    return <div className="text-white/40 text-sm py-2">暂无数据</div>;
  }
  return (
    <div className="space-y-2 mt-2">
      {title && <div className="text-sm font-medium text-white/70">{title}</div>}
      {tasks.map((t) => (
        <TaskCard key={t.task_id} task={t} />
      ))}
    </div>
  );
}

function ProductList({ products }) {
  if (!products || products.length === 0) {
    return <div className="text-white/40 text-sm py-2">暂无临期商品</div>;
  }
  return (
    <div className="space-y-2 mt-2">
      {products.map((p) => (
        <div key={p.product_id} className="card p-2 text-sm">
          <div className="font-medium">{p.name}</div>
          <div className="text-white/50 text-xs">
            品类: {p.category} | 库存: {p.stock} | 到期: {p.expiry_date}
          </div>
        </div>
      ))}
    </div>
  );
}

function DiscountResult({ result }) {
  const rate = result.recommended_discount;
  const tier = result.tier ?? "-";
  const reason = result.reasoning || "";
  const exempt = result.exemption_type != null;
  if (exempt) {
    return (
      <div className="bg-amber-500/10 border border-amber-500/30 rounded p-3 text-sm">
        <div className="font-medium text-amber-400">⚠️ {result.exemption_reason || "该商品豁免出清"}</div>
      </div>
    );
  }
  return (
    <div className="card p-3 text-sm space-y-1" style={{ border: "1px solid oklch(0.35 0.12 160 / 0.3)" }}>
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold" style={{ color: "var(--accent)" }}>
          {Math.round((rate || 0) * 100)}%
        </span>
        <span className="text-white/50 text-xs">建议折扣率</span>
      </div>
      <div className="text-white/60 text-xs">推荐等级: {tier} | {reason}</div>
    </div>
  );
}

function WelcomeMessage() {
  return (
    <div className="flex gap-3 animate">
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: "var(--accent)" }}
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
      <div className="card p-4 max-w-xl">
        <p className="text-sm mb-2">👋 你好！我是门店AI助手，我可以帮你：</p>
        <ul className="text-sm text-white/70 space-y-1 ml-4">
          <li>• 分析今日任务完成情况</li>
          <li>• 预警临期商品和处理建议</li>
          <li>• 优化员工排班和任务分配</li>
          <li>• 生成运营日报和周报</li>
        </ul>
      </div>
    </div>
  );
}

export { TaskList, ProductList, DiscountResult };

export default function ChatAssistant() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const addMsg = (content, intent = null) =>
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content, intent }]);

  const renderContent = (content) => {
    if (typeof content === "string") return content;
    if (content === null || content === undefined) return "（无内容）";
    if (typeof content === "object" && "text" in content) {
      return (
        <>
          {content.text && <span>{content.text}</span>}
          {content.component && <div className="mt-1">{content.component}</div>}
        </>
      );
    }
    return content;
  };

  const send = async (text) => {
    const msgText = text ?? input.trim();
    if (!msgText || loading) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", content: msgText };
    setMessages((m) => [...m, userMsg]);
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

      if (toolResult) {
        const parts = [];

        if (toolResult.products) {
          const prods = Array.isArray(toolResult.products) ? toolResult.products : [];
          response = response
            .replace(/^[^\n品类].*\n品类:\s*(daily_fresh|bakery|fresh|meat_poultry|seafood|dairy|frozen|beverage|snack|grain_oil)[^}\n]*\n?/gm, "")
            .replace(/^[^\n品类][^\n]*\n(?:品类:|库存:|到期:)[^\n]*\n?/gm, "");
          parts.push({ component: <ProductList products={prods} /> });
        } else if (toolResult.pending_products) {
          const prods = Array.isArray(toolResult.pending_products) ? toolResult.pending_products : [];
          parts.push({ component: <ProductList products={prods} /> });
        } else if (toolResult.items) {
          const prods = Array.isArray(toolResult.items) ? toolResult.items : [];
          parts.push({ component: <ProductList products={prods} /> });
        }

        if (toolResult.recommended_discount != null || toolResult.discount_rate != null) {
          parts.push({ component: <DiscountResult result={toolResult} /> });
        }

        if (toolResult.tasks) {
          const tasks = Array.isArray(toolResult.tasks) ? toolResult.tasks : [];
          if (tasks.length > 0) {
            parts.push({ component: <TaskList tasks={tasks} /> });
          }
        }

        if (parts.length > 0) {
          addMsg({ text: response, component: parts.map((p, i) => <div key={i}>{p.component}</div>) }, data.tool_name);
        } else {
          addMsg(response, data.tool_name);
        }
      } else {
        addMsg(response, data.tool_name);
      }

      if (data.needs_confirmation) {
        addMsg("（请确认以上信息是否正确）", "confirm");
      }
    } catch (err) {
      addMsg(`请求失败：${err.message || "请检查网络连接后重试"}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-auto space-y-4 mb-4">
        <WelcomeMessage />
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-3 animate ${m.role === "user" ? "flex-row-reverse" : ""}`}
          >
            {m.role === "user" ? (
              <div
                className="max-w-[80%] rounded-xl px-4 py-3"
                style={{ background: "oklch(0.35 0.12 160 / 0.5)", color: "oklch(0.92 0.08 160)" }}
              >
                <div className="text-sm whitespace-pre-wrap">{renderContent(m.content)}</div>
              </div>
            ) : (
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: "var(--accent)" }}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>
            )}
            {m.role !== "user" && (
              <div className="card p-4 max-w-xl flex-1">
                {m.intent && m.intent !== "error" && (
                  <div className="text-xs text-white/30 mb-1">
                    {m.intent === "confirm" ? "" : `操作: ${m.intent}`}
                  </div>
                )}
                <div className="text-sm text-white/90 whitespace-pre-wrap">{renderContent(m.content)}</div>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="card p-3 max-w-[80%] text-white/40 text-sm">正在处理...</div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="flex gap-2 flex-wrap mb-4">
        <button
          onClick={() => send("分析今日临期商品风险")}
          className="btn px-3 py-1.5 text-xs rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 transition flex items-center gap-1"
        >
          <span>🚨</span> 临期风险分析
        </button>
        <button
          onClick={() => send("今日任务完成情况")}
          className="btn px-3 py-1.5 text-xs rounded-lg bg-white/10 hover:bg-white/20 transition flex items-center gap-1"
        >
          <span>📊</span> 任务分析
        </button>
        <button
          onClick={() => send("生成今日运营日报")}
          className="btn px-3 py-1.5 text-xs rounded-lg bg-white/10 hover:bg-white/20 transition flex items-center gap-1"
        >
          <span>📝</span> 生成日报
        </button>
        <button
          onClick={() => send("任务分配优化建议")}
          className="btn px-3 py-1.5 text-xs rounded-lg bg-white/10 hover:bg-white/20 transition flex items-center gap-1"
        >
          <span>👥</span> 排班优化
        </button>
      </div>

      {/* Input */}
      <div className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="询问门店运营问题..."
          disabled={loading}
          className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[var(--accent)] transition text-white placeholder-white/40"
        />
        <button
          onClick={() => send()}
          disabled={loading}
          className="btn px-4 py-3 rounded-xl text-sm font-medium"
          style={{ background: "var(--accent)", color: "oklch(0.92 0.08 160)" }}
        >
          发送
        </button>
      </div>
    </div>
  );
}
