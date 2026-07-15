// Renders a structured InvestigationReport. Presentation only — no data
// fetching here (separation of concerns / single responsibility).

function List({ items }) {
  if (!items || items.length === 0) return <p className="muted">None</p>;
  return (
    <ul>
      {items.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  );
}

export default function ReportCard({ report }) {
  const esc = report.escalation || {};
  return (
    <div className="report">
      <h3>Investigation Report</h3>
      <p className="summary">{report.summary}</p>

      <div className="meta">
        <span><strong>Equipment:</strong> {report.equipment || "—"}</span>
        <span><strong>Alarm:</strong> {report.alarm || "—"}</span>
        <span><strong>Confidence:</strong> {report.confidence}</span>
      </div>

      <h4>Probable root causes</h4>
      <List items={report.probable_root_causes} />

      <h4>Recommended actions</h4>
      <List items={report.recommended_actions} />

      <h4>Evidence</h4>
      <List items={report.evidence} />

      <div className={`escalation ${esc.required ? "on" : "off"}`}>
        <h4>Escalation</h4>
        {esc.required ? (
          <p>
            <strong>Required →</strong> {esc.target || "—"}
            {esc.contact ? ` (${esc.contact})` : ""}
            {esc.rationale ? ` — ${esc.rationale}` : ""}
          </p>
        ) : (
          <p className="muted">Not required</p>
        )}
      </div>

      {report.missing_information && report.missing_information.length > 0 && (
        <div className="missing">
          <h4>Needs clarification</h4>
          <List items={report.missing_information} />
        </div>
      )}
    </div>
  );
}
