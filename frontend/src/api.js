export async function fetchTasks(status) {
  const qs = status && status !== "all" ? `?status=${status}` : "";
  const res = await fetch(`/api/tasks/${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.status}`);
  return res.json();
}

export async function fetchProducts() {
  const res = await fetch(`/api/reasoning/products`);
  if (!res.ok) throw new Error(`Failed to fetch products: ${res.status}`);
  return res.json();
}

export async function createTask(taskData) {
  const res = await fetch(`/api/tasks/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(taskData),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.status}`);
  return res.json();
}

export async function interpretIntent(message) {
  const res = await fetch(`/api/agent/intent/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, use_llm_fallback: true }),
  });
  if (!res.ok) throw new Error(`Failed to interpret intent: ${res.status}`);
  const data = await res.json();
  // 统一字段名：后端返回 action_type，前端使用 intent
  return { intent: data.action_type, confidence: data.confidence };
}

export async function confirmTask(taskId, confirmedDiscountRate, confirmedBy = "店长") {
  const res = await fetch(`/api/tasks/${taskId}/confirm`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_discount_rate: confirmedDiscountRate, confirmed_by: confirmedBy }),
  });
  if (!res.ok) throw new Error(`Failed to confirm task: ${res.status}`);
  return res.json();
}

export async function executeTask(taskId, executedBy, scanBarcode = "") {
  const res = await fetch(`/api/tasks/${taskId}/execute`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ executed_by: executedBy, scan_barcode: scanBarcode, price_label_printed: true }),
  });
  if (!res.ok) throw new Error(`Failed to execute task: ${res.status}`);
  return res.json();
}

export async function reviewTask(taskId, reviewedBy, sellThroughRate, reviewNotes = "") {
  const res = await fetch(`/api/tasks/${taskId}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewed_by: reviewedBy, sell_through_rate: sellThroughRate, review_notes: reviewNotes }),
  });
  if (!res.ok) throw new Error(`Failed to review task: ${res.status}`);
  return res.json();
}

export async function queryDiscount(productId, category, expiryDate = "", stock = 0) {
  const res = await fetch(`/api/reasoning/discount`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: productId,
      product_name: "",  // 后端当前未使用，留空
      category,
      expiry_date: expiryDate || new Date().toISOString().split("T")[0],
      stock: parseInt(stock) || 0,
    }),
  });
  if (!res.ok) throw new Error(`Failed to query discount: ${res.status}`);
  return res.json();
}

export async function triggerScan() {
  const res = await fetch(`/api/agent/scan-and-reason`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to trigger scan: ${res.status}`);
  return res.json();
}

/**
 * 统一人机协作入口 — TTL + LLM 分层协同
 * @param {string} message - 店长的自然语言输入
 * @param {object} productContext - 可选，商品上下文（用于折扣推理）
 * @param {string} productContext.product_id
 * @param {string} productContext.product_name
 * @param {string} productContext.category
 * @param {string} productContext.expiry_date
 * @param {number} productContext.stock
 * @param {boolean} skipLl - 强制走 Layer 1（调试用）
 */
export async function unifiedChat(message, productContext = {}, skipLl = false) {
  const res = await fetch(`/api/agent/unified-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      product_id: productContext.productId || null,
      product_name: productContext.productName || null,
      category: productContext.category || null,
      expiry_date: productContext.expiryDate || null,
      stock: productContext.stock != null ? parseInt(productContext.stock) : null,
      skip_llm: skipLl,
    }),
  });
  if (!res.ok) throw new Error(`Failed unified chat: ${res.status}`);
  return res.json();
}
