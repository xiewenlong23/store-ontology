export async function fetchTasks() {
  const res = await fetch(`/api/tasks/`);
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.status}`);
  return res.json();
}

export async function fetchProducts() {
  const res = await fetch(`/api/reasoning/products`);
  if (!res.ok) throw new Error(`Failed to fetch products: ${res.status}`);
  return res.json();
}
