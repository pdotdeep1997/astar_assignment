// Thin API client. Single place that knows the endpoint (separation of
// concerns) so components never hard-code URLs.
const BASE = import.meta.env.VITE_API_BASE || "/api";

export async function investigate(incident) {
  const res = await fetch(`${BASE}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident }),
  });
  if (!res.ok) {
    throw new Error(`Server error ${res.status}`);
  }
  return res.json();
}
