import React from "react";

const INTENT_RESPONSES = {
  create_task: "检测到创建任务意图。请提供门店ID、目标售罄率和截止日期，我将为您创建任务。",
  query_status: "检测到查询状态意图。正在为您查询当前任务列表...",
  report_result: "检测到结果报告意图。正在为您获取售罄率分析结果...",
  unknown: "抱歉，我暂时无法理解您的意图。您可以尝试：「帮我创建任务」、「查询任务状态」或「查看售罄率结果」。",
};

export default function ChatAssistant() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", text: input };
    setMessages(m => [...m, userMsg]);
    const sentInput = input;
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/tasks/chat/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: sentInput }),
      });
      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }
      const data = await res.json();
      const intent = data.intent;
      const replyText = INTENT_RESPONSES[intent] || INTENT_RESPONSES.unknown;
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: replyText,
        intent,
      };
      setMessages(m => [...m, assistantMsg]);
    } catch {
      setMessages(m => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", text: "请求失败，请检查网络连接后重试。" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-col flex-1 overflow-auto space-y-3 mb-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-3 rounded-lg ${m.role === "user" ? "bg-blue-100 self-end ml-auto" : "bg-gray-100"} max-w-[80%]`}
          >
            {m.intent && m.intent !== "unknown" && (
              <div className="text-xs text-gray-400 mb-1">意图: {m.intent}</div>
            )}
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="p-3 rounded-lg bg-gray-100 max-w-[80%] text-gray-400">
            正在识别意图...
          </div>
        )}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder="输入问题或指令..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className="bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          发送
        </button>
      </div>
    </div>
  );
}
