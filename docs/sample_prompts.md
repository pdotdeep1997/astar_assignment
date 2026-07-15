# Sample Prompts & Test Cases

These map to the four required scenarios and the dataset's `test_cases` sheet.
Paste any of them into the chat UI, or POST to `/investigate`.

## 1. Normal incident (full information)
```
CVD-05 has gas flow deviation, MFC actual flow below setpoint. Downtime 35 min. Lot LOT1057.
```
Expected: retrieves EQ003, GAS012, CVD maintenance and SOP006; escalates on high
severity + downtime > 30 min.

## 2. Missing information
```
CMP-02 pressure alarm. Downtime 18 minutes. Lot LOT1056.
```
Expected: no explicit alarm code — the agent should infer/ask, retrieve CMP205
context if matched, and flag the missing alarm code. Avoids over-escalation.

## 3. Repeated incident (recurrence → escalation)
```
Etcher-03 triggered RF Power Instability at 10:35. Tool down 45 minutes. Lot LOT1055 running. Similar alarm occurred twice last week.
```
Expected: retrieves EQ001, RF101, similar incidents H101–H103, SOP001; the
`check_escalation` tool detects ≥2 same-alarm incidents within 7 days (rule R002)
→ escalate to Engineering Manager. Also R001 (downtime) and R003 (high severity).

## 4. Unknown alarm / equipment
```
Unknown tool ALPHA-99 has alarm ZX999.
```
Expected: tools return `found: false` gracefully; the agent asks for clarification
with low confidence and does not fabricate a diagnosis.

## curl example
```bash
curl -s http://localhost:8003/investigate \
  -H "Content-Type: application/json" \
  -d '{"incident":"Etcher-03 RF Power Instability, 45 min, LOT1055, twice last week."}' | jq
```
