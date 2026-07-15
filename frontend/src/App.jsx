// Chat container. Owns conversation state and delegates rendering to
// ReportCard / ToolTrace (single responsibility per component).
import { useState, useRef, useEffect } from "react";
import { investigate } from "./api.js";
import ReportCard from "./components/ReportCard.jsx";
import ToolTrace from "./components/ToolTrace.jsx";

const SAMPLES = [
  "Etcher-03 triggered RF Power Instability at 10:35. Tool down 45 minutes. Lot LOT1055 running. Similar alarm twice last week.",
  "CMP-02 pressure alarm. Downtime 18 minutes. Lot LOT1056.",
  "CVD-05 has gas flow deviation, MFC actual flow below setpoint. Downtime 35 min.",
  "Unknown tool ALPHA-99 has alarm ZX999.",
];

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text) {
    const incident = (text ?? input).trim();
    if (!incident || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: incident }]);
    setLoading(true);
    try {
      const data = await investigate(incident);
      setMessages((m) => [...m, { role: "agent", data }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "error", text: err.message }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Incident Investigation Assistant</h1>
        <p>Describe a machine-downtime incident in plain language.</p>
      </header>

      <div className="chat">
        {messages.length === 0 && (
          <div className="samples">
            <p className="muted">Try an example:</p>
            {SAMPLES.map((s, i) => (
              <button key={i} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}

        {messages.map((m, i) => {
          if (m.role === "user")
            return <div key={i} className="msg user">{m.text}</div>;
          if (m.role === "error")
            return <div key={i} className="msg error">⚠ {m.text}</div>;
          return (
            <div key={i} className="msg agent">
              {m.data.report ? (
                <ReportCard report={m.data.report} />
              ) : (
                <p>{m.data.raw_text || "No structured report was produced."}</p>
              )}
              <ToolTrace trace={m.data.trace} />
            </div>
          );
        })}

        {loading && <div className="msg agent muted">Investigating…</div>}
        <div ref={endRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Etcher-03 RF Power Instability, 45 min, LOT1055…"
          disabled={loading}
        />
        <button type="submit" disabled={loading}>Send</button>
      </form>
    </div>
  );
}
