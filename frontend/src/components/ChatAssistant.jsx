import React from "react";
import { unifiedChat } from "../api";

// 状态标签颜色
const STATUS_LABEL = {
  pending: { text: "待确认", cls: "bg-yellow-100 text-yellow-700" },
  confirmed: { text: "已确认", cls: "bg-blue-100 text-blue-700" },
  executed: { text: "已执行", cls: "bg-purple-100 text-purple-700" },
  reviewed: { text: "已复核", cls: "bg-green-100 text-green-700" },
  completed: { text: "已完成", cls: "bg-gray-100 text-gray-600" },
};

function TaskCard({ task }) {
  const status = STATUS_LABEL[task.status] || { text: task.status, cls: "bg-gray-100" };
  return (
    <div className="bg-gray-50 rounded p-3 text-sm border">
      <div className="flex justify-between items-start mb-1">
        <span className="font-medium">{task.product_name}</span>
        <span className={`text-xs px-2 py-0.5 rounded ${status.cls}`}>{status.text}</span>
      </div>
      <div className="text-gray-500 text-xs space-y-0.5">
        <div>门店: {task.store_id} | 商品: {task.product_id}</div>
        <div>折扣率: {task.discount_rate != null ? Math.round(task.discount_rate * 100) : "-"}%</div>
        <div>原价库存: {task.original_stock} | 截止: {task.expiry_date}</div>
        {task.task_id && <div className="text-gray-400">ID: {task.task_id.slice(0, 8)}...</div>}
      </div>
    </div>
  );
}

function TaskList({ tasks, title }) {
  if (!tasks || tasks.length === 0) {
    return <div className="text-gray-500 text-sm py-2">暂无数据</div>;
  }
  return (
    <div className="space-y-2 mt-2">
      {title && <div className="text-sm font-medium text-gray-600">{title}</div>}
      {tasks.map((t) => (
        <TaskCard key={t.task_id} task={t} />
      ))}
    </div>
  );
}

function ProductList({ products }) {
  if (!products || products.length === 0) {
    return <div className="text-gray-500 text-sm py-2">暂无临期商品</div>;
  }
  return (
    <div className="space-y-2 mt-2">
      {products.map((p) => (
        <div key={p.product_id} className="bg-gray-50 rounded p-2 text-sm">
          <div className="font-medium">{p.name}</div>
          <div className="text-gray-500 text-xs">
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
      <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-sm">
        <div className="font-medium text-yellow-700">⚠️ {result.exemption_reason || "该商品豁免出清"}</div>
      </div>
    );
  }
  return (
    <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold text-blue-700">{Math.round((rate || 0) * 100)}%</span>
        <span className="text-gray-500 text-xs">建议折扣率</span>
      </div>
      <div className="text-gray-600 text-xs">推荐等级: {tier} | {reason}</div>
    </div>
  );
}

export default function ChatAssistant() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  // 辅助：追加消息（text 或 React 组件）
  const addMsg = (content, intent = null) =>
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content, intent }]);

  // 渲染消息内容：自动识别字符串 / React 组件 / {text, component} 结构
  const renderContent = (content) => {
    if (typeof content === "string") return content;
    if (content === null || content === undefined) return "（无内容）";
    // { text: string, component: ReactNode }
    if (typeof content === "object" && "text" in content) {
      return (
        <>
          {content.text && <span>{content.text}</span>}
          {content.component && <div className="mt-1">{content.component}</div>}
        </>
      );
    }
    // React 组件
    return content;
  };

  // ========== 发送消息 ==========

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", content: input };
    setMessages((m) => [...m, userMsg]);
    const sentInput = input;
    setInput("");
    setLoading(true);

    try {
      const data = await unifiedChat(sentInput);
      const response = data.response || "（无响应）";

      // 根据返回内容类型决定渲染方式
      // tool_result 里可能包含结构化数据（商品列表 / 任务列表 / 折扣结果）
      const toolResult = data.tool_result;

      if (toolResult) {
        // 有结构化数据：渲染文本 + 对应组件
        const parts = [];

        // 商品列表
        if (toolResult.products) {
          const prods = Array.isArray(toolResult.products) ? toolResult.products : [];
          parts.push({ component: <ProductList products={prods} /> });
        } else if (toolResult.pending_products) {
          const prods = Array.isArray(toolResult.pending_products) ? toolResult.pending_products : [];
          parts.push({ component: <ProductList products={prods} /> });
        } else if (toolResult.items) {
          const prods = Array.isArray(toolResult.items) ? toolResult.items : [];
          parts.push({ component: <ProductList products={prods} /> });
        }

        // 折扣结果
        if (toolResult.recommended_discount != null || toolResult.discount_rate != null) {
          parts.push({ component: <DiscountResult result={toolResult} /> });
        }

        // 任务列表
        if (toolResult.tasks) {
          const tasks = Array.isArray(toolResult.tasks) ? toolResult.tasks : [];
          if (tasks.length > 0) {
            parts.push({ component: <TaskList tasks={tasks} /> });
          }
        }

        if (parts.length > 0) {
          // 文本 + 结构化组件
          addMsg({ text: response, component: parts.map((p, i) => <div key={i}>{p.component}</div>) }, data.tool_name);
        } else {
          // 只有文本
          addMsg(response, data.tool_name);
        }
      } else {
        // 纯自然语言响应
        addMsg(response, data.tool_name);
      }

      // 需要确认（human-in-the-loop）
      if (data.needs_confirmation) {
        addMsg("（请确认以上信息是否正确）", "confirm");
      }
    } catch (err) {
      addMsg(`请求失败：${err.message || "请检查网络连接后重试"}`, "error");
    } finally {
      setLoading(false);
    }
  };

  // ========== 渲染 ==========

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 */}
      <div className="flex-1 overflow-auto space-y-3 mb-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-3 rounded-lg ${m.role === "user" ? "bg-blue-100 self-end ml-auto" : "bg-gray-100"} max-w-[90%]`}
          >
            {m.intent && m.intent !== "error" && (
              <div className="text-xs text-gray-400 mb-1">
                {m.intent === "confirm" ? "" : `操作: ${m.intent}`}
              </div>
            )}
            <div className="text-sm text-gray-800 whitespace-pre-wrap">
              {renderContent(m.content)}
            </div>
          </div>
        ))}

        {loading && (
          <div className="p-3 rounded-lg bg-gray-100 max-w-[80%] text-gray-400 text-sm">
            正在处理...
          </div>
        )}
      </div>

      {/* 输入框 */}
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="输入问题或指令，如：帮我创建任务、查询待确认任务"
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          发送
        </button>
      </div>

      {/* 快捷提示 */}
      <div className="flex flex-wrap gap-1 mt-2 text-xs text-gray-400">
        <span className="bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200" onClick={() => setInput("帮我创建任务")}>创建任务</span>
        <span className="bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200" onClick={() => setInput("查询任务状态")}>查询任务</span>
        <span className="bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200" onClick={() => setInput("有哪些临期商品")}>临期商品</span>
        <span className="bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200" onClick={() => setInput("确认任务")}>确认任务</span>
        <span className="bg-gray-100 px-2 py-0.5 rounded cursor-pointer hover:bg-gray-200" onClick={() => setInput("查询折扣建议")}>折扣建议</span>
      </div>
    </div>
  );
}
