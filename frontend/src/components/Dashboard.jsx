import React from "react";
import ProductCard from "./ProductCard";
import { fetchProducts } from "../api";

const CATEGORY_NAMES = {
  daily_fresh: "日配", bakery: "烘焙", fresh: "生鲜", meat_poultry: "肉禽",
  seafood: "水产", dairy: "乳品", frozen: "冷冻食品", beverage: "饮品",
  snack: "休闲食品", grain_oil: "米面粮油"
};

export default function Dashboard() {
  const [products, setProducts] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const grouped = products.reduce((acc, p) => {
    if (!acc[p.category]) acc[p.category] = [];
    acc[p.category].push(p);
    return acc;
  }, {});

  if (loading) {
    return <div className="text-center py-8 text-gray-500">加载中...</div>;
  }

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([cat, prods]) => (
        <div key={cat} className="bg-white rounded-lg p-4 shadow">
          <h3 className="font-semibold text-gray-700 mb-2">{CATEGORY_NAMES[cat] || cat}</h3>
          <div className="space-y-2">
            {prods.map(p => <ProductCard key={p.product_id} product={p} />)}
          </div>
        </div>
      ))}
    </div>
  );
}