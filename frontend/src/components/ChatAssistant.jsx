import React from "react";

export default function ChatAssistant() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");

  const send = async () => {
    if (!input.trim()) return;
    const userMsg = { id: crypto.randomUUID(), role: "user", text: input };
    setMessages(m => [...m, userMsg]);
    setInput("");

    // Simple mock responses for MVP
    const resp = { id: crypto.randomUUID(), role: "assistant", text: `收到: "${input}" - 正在处理...` };
    setMessages(m => [...m, resp]);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto space-y-3 mb-4">
        {messages.map((m) => (
          <div key={m.id} className={`p-3 rounded-lg ${m.role === "user" ? "bg-blue-100 self-end ml-auto" : "bg-gray-100"} max-w-[80%]`}>
            {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder="输入问题或指令..."
        />
        <button onClick={send} className="bg-blue-500 text-white px-4 py-2 rounded">发送</button>
      </div>
    </div>
  );
}