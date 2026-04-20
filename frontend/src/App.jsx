import Dashboard from "./components/Dashboard";
import ChatAssistant from "./components/ChatAssistant";

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

ReactDOM.createRoot(document.getElementById("root")).render(<App />);