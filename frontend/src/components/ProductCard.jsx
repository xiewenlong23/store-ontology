import React from "react";

export default function ProductCard({product}) {
  const today = new Date();
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