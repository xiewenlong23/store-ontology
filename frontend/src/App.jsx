const API_BASE = "http://localhost:8000/api";

function App() {
  return (
    <div className="flex h-screen">
      {/* Left: Dashboard (60%) */}
      <div className="w-3/5 p-4 overflow-auto">
        <h1 className="text-xl font-bold mb-4">商品健康度总览</h1>
        <Dashboard />
      </div>
      {/* Right: Chat (40%) */}
      <div className="w-2/5 bg-white p-4 flex flex-col border-l border-gray-200">
        <h2 className="text-lg font-semibold mb-4">对话助手</h2>
        <ChatAssistant />
      </div>
    </div>
  );
}

function Dashboard() {
  const [products, setProducts] = React.useState([]);
  const [tasks, setTasks] = React.useState([]);

  React.useEffect(() => {
    fetch(`${API_BASE}/tasks/`).then(r => r.json()).then(setTasks);
    setProducts([
      {product_id: "P001", name: "嫩豆腐", category: "daily_fresh", expiry_date: "2026-04-21", stock: 50, in_reduction: false},
      {product_id: "P002", name: "现烤法式面包", category: "bakery", expiry_date: "2026-04-20", stock: 30, in_reduction: false},
      {product_id: "P003", name: "红富士苹果", category: "fresh", expiry_date: "2026-04-22", stock: 80, in_reduction: false},
    ]);
  }, []);

  const grouped = products.reduce((acc, p) => {
    if (!acc[p.category]) acc[p.category] = [];
    acc[p.category].push(p);
    return acc;
  }, {});

  const categoryNames = {
    daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜", meat_poultry: "肉禽",
    seafood: "水产", dairy: "乳品", frozen: "冷冻食品", beverage: "饮品",
    snack: "休闲食品", grain_oil: "米面粮油"
  };

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([cat, prods]) => (
        <div key={cat} className="bg-white rounded-lg p-4 shadow">
          <h3 className="font-semibold text-gray-700 mb-2">{categoryNames[cat] || cat}</h3>
          <div className="space-y-2">
            {prods.map(p => <ProductCard key={p.product_id} product={p} />)}
          </div>
        </div>
      ))}
    </div>
  );
}

function ProductCard({product}) {
  const today = new Date("2026-04-20");
  const expiry = new Date(product.expiry_date);
  const daysLeft = Math.ceil((expiry - today) / (1000*60*60*24));
  const urgency = daysLeft <= 1 ? "🔴" : daysLeft <= 3 ? "🟡" : "🟢";

  return (
    <div className={`flex items-center justify-between p-3 rounded border ${daysLeft <= 1 ? "bg-red-50 border-red-200" : daysLeft <= 3 ? "bg-yellow-50 border-yellow-200" : "bg-green-50 border-green-200"}`}>
      <div>
        <div className="font-medium">{product.name}</div>
        <div className="text-sm text-gray-500">库存: {product.stock}</div>
      </div>
      <div className="text-right">
        <div className="text-lg">{urgency}</div>
        <div className="text-sm text-gray-500">{daysLeft}天</div>
      </div>
    </div>
  );
}

function ChatAssistant() {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");

  const send = async () => {
    if (!input.trim()) return;
    const userMsg = { role: "user", text: input };
    setMessages(m => [...m, userMsg]);
    setInput("");

    // Simple mock responses for MVP
    const resp = { role: "assistant", text: `收到: "${input}" - 正在处理...` };
    setMessages(m => [...m, resp]);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto space-y-3 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`p-3 rounded-lg ${m.role === "user" ? "bg-blue-100 self-end ml-auto" : "bg-gray-100"} max-w-[80%]}`}>
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

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
