import React from "react";
import ProductCard from "./ProductCard";

export default function Dashboard() {
  const [products, setProducts] = React.useState([]);
  const [tasks, setTasks] = React.useState([]);

  React.useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE || "http://localhost:8000/api"}/tasks/`)
      .then(r => r.json())
      .then(setTasks)
      .catch(console.error);
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