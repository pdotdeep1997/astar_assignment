// Collapsible view of the tools the agent called — makes the agentic workflow
// transparent (useful for the demo and for trust).
import { useState } from "react";

export default function ToolTrace({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace || trace.length === 0) return null;

  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} Evidence trail ({trace.length} tool calls)
      </button>
      {open && (
        <ol>
          {trace.map((step, i) => (
            <li key={i}>
              <code>{step.tool}</code>
              <span className="args">({JSON.stringify(step.args)})</span>
              <pre>{JSON.stringify(step.result, null, 2)}</pre>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
