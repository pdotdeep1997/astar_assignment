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

// Streaming variant: consumes the Server-Sent Events endpoint and invokes
// callbacks as events arrive. `onStatus(message)` fires for each intermediate
// step; `onFinal(data)` fires once with the report + trace.
export async function investigateStream(incident, { onStatus, onFinal }) {
  const res = await fetch(`${BASE}/investigate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`Server error ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop(); // keep the trailing partial frame for next read
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const evt = JSON.parse(line.slice(5).trim());
      if (evt.type === "final") onFinal(evt);
      else if (evt.type === "status") onStatus(evt.message);
    }
  }
}
