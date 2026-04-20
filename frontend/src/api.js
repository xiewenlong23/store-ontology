export const API_BASE = "http://localhost:8000/api";

export async function fetchTasks() {
  const res = await fetch(`${API_BASE}/tasks/`);
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.status}`);
  return res.json();
}

export async function fetchProducts() {
  const res = await fetch(`${API_BASE}/reasoning/products`);
  if (!res.ok) throw new Error(`Failed to fetch products: ${res.status}`);
  return res.json();
}