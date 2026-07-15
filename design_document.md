# Design Document — Incident Investigation Agentic AI Assistant

*A plain-language walkthrough of how the assistant is built, how it thinks, and why the main decisions were made.*

---

## What this system is

Imagine an equipment engineer on a semiconductor fab floor. A tool has gone down, an alarm is flashing, and a production lot is waiting. Today they'd open five different systems — equipment records, alarm references, past incident logs, maintenance history, standard operating procedures — piece the story together by hand, and decide whether to fix it themselves or escalate.

This assistant collapses that scramble into a single conversation. The engineer types what they see in plain English:

> *"Etcher-03 triggered RF Power Instability at 10:35. Tool down 45 minutes. Lot LOT1055 running. Similar alarm twice last week."*

The assistant then does what the engineer would do — but in seconds. It looks up the tool, checks the alarm, searches for similar incidents in the history, reviews recent maintenance, inspects sensor traces, pulls the relevant SOP, and applies the plant's escalation rules. Finally it hands back a structured investigation report: what's likely wrong, what to do, and who (if anyone) to escalate to — with every claim backed by data it actually retrieved.

The key word is **agentic**: the assistant isn't following a fixed script. A large language model (Anthropic's Claude) decides, step by step, which information to fetch next, using a set of tools we give it.

---

## 1. Overall solution architecture

The system is built in four clean layers, each with one job. This separation is deliberate: it keeps every piece testable, and it means you can replace any single layer without disturbing the others.

```
   ┌──────────────────────────────────────────────────────────┐
   │  React + Vite chat UI                                     │   The face
   │  (engineer types an incident, reads the report)          │
   └───────────────────────────┬──────────────────────────────┘
                               │  HTTP  POST /investigate
   ┌───────────────────────────▼──────────────────────────────┐
   │  FastAPI  (transport layer)                              │   The door
   │  validates the request, hands it to the agent            │
   └───────────────────────────┬──────────────────────────────┘
                               │
   ┌───────────────────────────▼──────────────────────────────┐
   │  InvestigationAgent  (orchestration)                     │   The brain
   │  runs the tool-calling loop with Claude                  │
   │            │                         ▲                    │
   │            │ "call this tool"        │ evidence           │
   │            ▼                         │                    │
   │  ToolRegistry ── 7 tools ────────────┘                    │   The hands
   └───────────────────────────┬──────────────────────────────┘
                               │
   ┌───────────────┬───────────┴───────────┬──────────────────┐
   │  SQLite       │                       │  ChromaDB        │   The memory
   │  structured   │                       │  semantic search │
   │  lookups      │                       │  (incidents,SOPs)│
   └───────────────┴───────────────────────┴──────────────────┘
                               ▲
                               │  loaded once at startup
                    ┌──────────┴───────────┐
                    │  Excel dataset (.xlsx)│
                    └───────────────────────┘
```

**The face — React + Vite chat UI.** A lightweight single-page chat app. The engineer types an incident or clicks a sample; the app posts it to the backend and renders the returned report as a clean card, plus a collapsible "evidence trail" showing exactly which tools the agent called and what they returned. That transparency is intentional — engineers trust a recommendation more when they can see the reasoning behind it.

**The door — FastAPI.** A thin HTTP layer exposing `POST /investigate` (run an investigation), `GET /tools` (list available tools), and `GET /health`. It does nothing clever: it validates input, calls the agent, returns the result. All the intelligence lives deeper.

**The brain — the InvestigationAgent.** This is the orchestrator. It manages the back-and-forth conversation between Claude and the tools until a final report is ready. Crucially, it knows nothing about SQLite, ChromaDB, or even which LLM is being used — it works purely through abstractions.

**The hands — the seven tools.** Each tool is a small, single-purpose capability the model can invoke: look up equipment, look up an alarm, find similar past incidents, and so on. They're the only way the agent touches real data.

**The memory — SQLite + ChromaDB.** Two stores with complementary strengths. SQLite answers precise, structured questions ("give me the maintenance records for EQ001"). ChromaDB answers fuzzy, meaning-based questions ("find past incidents that resemble this description"). Both are populated once at startup from the provided Excel dataset.

### How the data gets in

On first launch, a loader reads the Excel workbook and mirrors each sheet into a SQLite table (equipment, alarms, incident history, maintenance, sensors, SOPs, escalation rules, and so on). It then builds two ChromaDB collections by embedding the natural-language descriptions of past incidents and SOPs so they can be searched by meaning. This step is **idempotent** — it detects work already done and skips it — so the app is safe to restart and genuinely works out of the box. The generated database and vector index are treated as disposable artefacts, rebuilt any time from the source spreadsheet.

---

## 2. Agent workflow and orchestration

This is the heart of the system: the loop that lets the model investigate rather than just answer.

### The loop, step by step

1. **Set the stage.** The agent opens the conversation with a *system prompt* (the assistant's operating procedure and rules) and the engineer's incident text.
2. **Offer the tools.** It presents Claude with the seven tools plus one special tool, `submit_report`, used to finish.
3. **Let the model drive.** Claude reads the situation and decides what it needs first — usually the equipment details, then the alarm, then similar incidents, and so on. It requests a tool by name with arguments.
4. **Execute and feed back.** The agent runs the requested tool against SQLite or ChromaDB, then feeds the result back into the conversation so the model can use it in its next decision. Every call is recorded in a **trace**.
5. **Repeat.** Steps 3–4 loop. Each turn, the model has more evidence and asks for the next piece — exactly how a human investigator narrows things down.
6. **Finish deliberately.** When Claude has enough, it calls `submit_report` with the finished, structured report. The agent validates it and returns it.

```
   incident text
        │
        ▼
   ┌─────────────────────────────────────────────┐
   │  Claude: "What do I need to know next?"     │◀────────────┐
   └───────────────┬─────────────────────────────┘             │
                   │ requests a tool                           │ evidence
                   ▼                                           │ appended to
   ┌─────────────────────────────────────────────┐             │ the conversation
   │  Agent runs the tool → SQLite / ChromaDB    │─────────────┘
   └───────────────┬─────────────────────────────┘
                   │  (when confident)
                   ▼
   ┌─────────────────────────────────────────────┐
   │  Claude calls submit_report                 │
   │  → validated → returned to the engineer     │
   └─────────────────────────────────────────────┘
```

### Why finish with a `submit_report` tool?

A naive design asks the model to "reply with JSON" and then parses that text — brittle, because models occasionally add prose, miss a field, or malform the JSON. Instead we make finishing *itself* a tool call whose parameter schema **is** the report structure. The model fills in the fields the same way it fills in any tool's arguments, and we validate them against a strict schema. If validation fails, the agent tells the model what was wrong and lets it try again. The result: the API always returns a well-formed report or a clear error, never messy free text.

### Guardrails

The loop is defensive by design, because real LLM calls and real tools can misbehave:

- **Iteration cap.** The loop runs at most N turns (default 8), so it can never spin forever.
- **A gentle nudge.** If the model replies without calling a tool and without submitting, the agent reminds it to finalise, rather than stalling.
- **Tool errors are contained.** If a tool throws, the agent catches it and passes the error back as data. One failing lookup never crashes the whole investigation.
- **Graceful "not found."** Tools return a structured *"nothing here"* rather than raising, so the model can reason about missing information (central to the unknown-alarm case below).

### What comes back

Every investigation returns two things: the **structured report** (summary, equipment, alarm, evidence, probable root causes, recommended actions, escalation decision, confidence, and any missing information), and the **trace** — the ordered list of tools called, their arguments, and their results. The report is the answer; the trace is the receipt.

---

## 3. Tool design

Tools are how the agent touches the world. The design goal was consistency and safety: every tool looks the same from the outside, so the agent can treat them uniformly, and none of them can bring the system down.

### A shared shape

Every tool exposes four things: a **name**, a **description** (written for the model — this is effectively part of the prompt), a **JSON schema** for its parameters, and a `run()` method. They all return a plain dictionary, and — importantly — they **never raise an exception for missing data**. If an alarm code doesn't exist, the tool returns `{"found": false, ...}`. This single convention is what lets the assistant handle unknown equipment or alarms gracefully instead of erroring out.

### The seven tools

| Tool | What it answers | Backed by |
|---|---|---|
| **get_equipment_details** | "What is this tool — vendor, model, line, owner?" (accepts an ID *or* a name like `Etcher-03`) | SQLite |
| **get_alarm_details** | "What does this alarm mean — severity, probable causes?" | SQLite |
| **get_similar_incidents** | "Have we seen something like this before?" (semantic search) | ChromaDB |
| **get_maintenance_history** | "What maintenance happened recently on this tool?" | SQLite |
| **get_sensor_readings** | "What were the sensors doing around this incident?" | SQLite |
| **get_sop** | "What's the official troubleshooting procedure?" (exact match by alarm, semantic fallback by symptom) | SQLite + ChromaDB |
| **check_escalation** | "Does this need escalating, and to whom?" | SQLite (rules engine) |

Two tools deserve special mention.

**get_similar_incidents** is where semantic search earns its keep. Rather than matching exact column values, it compares the *meaning* of the current problem against a hundred past incidents. A description of "unstable RF power on the etcher" will surface historically related cases even if the wording differs — giving the model real precedent (past root causes, what fixed them) to reason from.

**check_escalation is deliberately not powered by the LLM.** Escalation is a business decision with real consequences — pull in a senior engineer, notify a manager, call the vendor. Those decisions must be reliable and auditable, not a matter of model judgement. So this tool is a plain, deterministic rules engine that evaluates the plant's five escalation rules in code:

| Rule | Condition | Escalate to |
|---|---|---|
| R001 | Downtime over 30 minutes | Senior Equipment Engineer |
| R002 | Same alarm on the same tool ≥ 2 times in 7 days | Engineering Manager |
| R003 | High-severity alarm | Process Engineer |
| R004 | Same alarm on the same tool > 3 times in 30 days | Vendor Support |
| R005 | A production lot is affected | Manufacturing Supervisor |

The tool counts recurrences directly from the incident history, evaluates each rule, and resolves the triggered targets to real people from the engineer directory. The model *calls* this tool and reports its verdict — it never invents escalation logic of its own.

### Adding a tool later

Because every tool shares the same shape and is registered in one place, extending the assistant is easy: write a new tool class, register it, and the agent can immediately use it — no changes to the loop or existing tools.

---

## 4. Prompting strategy

The prompt is the assistant's job description. A good one makes the model reliable; a vague one makes it wander. Ours is built around a few firm principles.

**Give it a role and a procedure.** The system prompt casts the model as an incident investigation assistant and lays out a clear method: parse the incident, retrieve evidence with the tools, ground every claim in what was retrieved, decide escalation only via the escalation tool, and avoid over-escalating minor issues. This turns an open-ended chat model into a focused investigator.

**Insist on grounding.** The single most important instruction is: *don't guess what you can look up.* The model is told to use tools for facts and to state plainly when a tool returns nothing, rather than inventing a plausible-sounding detail. This is what keeps reports trustworthy.

**Guide the order, don't hard-code it.** The prompt suggests a sensible sequence (equipment → alarm → similar incidents → maintenance → sensors → SOP → escalation) but lets the model adapt to the specific incident. It's guidance, not a rigid script — which is the whole point of an agent.

**Prevent over-reaction.** The prompt explicitly warns against over-escalating low-severity, low-downtime, non-recurring incidents. Combined with the deterministic escalation tool, this stops the assistant from crying wolf on routine events.

**Make finishing unambiguous.** Rather than hoping for clean JSON, the prompt directs the model to finish by calling `submit_report`, and a short "finalise" reminder nudges it along if it ever stalls. Prompt text lives in its own module, separate from code, so it can be tuned without touching the orchestration logic.

**Keep settings simple and portable.** The client sends the tools and the conversation and lets the model's provider defaults handle the rest. (Notably, we don't force a custom `temperature`, because some newer Claude models reject one — leaving it at the default keeps the assistant compatible across model versions.)

---

## 5. Key implementation decisions and assumptions

Every meaningful choice here traded some flexibility for reliability, simplicity, or the ability to run out of the box.

**Everything important sits behind an interface.** The database, the vector store, the embedder, and the LLM are all accessed through abstract interfaces, and the concrete implementations are wired together in exactly one file (the composition root). This is the promised *"swap the database easily"* property: replacing SQLite with PostgreSQL means writing one new class and changing one line — no tool, agent, or API code moves. It also makes testing painless: the tests inject a scripted fake LLM and an offline embedder, and still exercise the real tools and real database, with no network calls or API keys.

**Anthropic Claude, via LiteLLM.** The assistant talks to Claude through the LiteLLM library. Even though we've settled on Anthropic, routing through a thin `LLMClient` interface (with LiteLLM behind it) is what lets the tests substitute a fake model — and keeps the door open to other providers with a single new adapter rather than a rewrite.

**SQLite and ChromaDB — zero-setup by design.** Both run embedded, in-process, with no separate server and no Docker required. For this dataset's size they're more than fast enough, and they make the "clone it and run it" experience genuinely one step. Both are swappable if the system ever needs to scale.

**Local embeddings by default.** Semantic search needs to turn text into vectors. By default this uses a small local model, so no embedding API key is required and the assistant runs offline after the first model download. A dependency-free hashing embedder is available as a fallback for tests and CI.

**A structured report over free text.** As described above, finishing via a validated schema was chosen over parsing model prose — reliability over cleverness.

**Determinism where it matters.** Escalation logic is code, not prompt. This is the clearest example of a broader principle: let the model handle language, reasoning, and synthesis; keep consequential business rules in deterministic code where they can be tested and trusted.

### Assumptions worth stating

- **The dataset is the ground truth.** Alarm severity comes from the alarm reference; recurrence means the same alarm on the same equipment within a time window, counted from the incident history; escalation targets are resolved against the engineer directory (by role, or by name for the vendor contact).
- **Data is loaded verbatim.** Each spreadsheet sheet becomes a table with the same columns, and all values are stored as text. This keeps loading trivial and works because the date and code fields compare correctly as strings for our queries. If the system grew, typed columns and enforced keys/relationships would be a natural next step.
- **Timestamps are consistently formatted.** Recurrence and time-window logic assume the `YYYY-MM-DD HH:MM` format used throughout the dataset.
- **Scale is modest.** A handful of tools, a hundred-odd historical incidents, a few dozen maintenance and sensor rows — well within what embedded stores handle instantly. The design would need revisiting only at much larger volumes.

### Where it could go next

Natural extensions include a reflection or self-review pass before submitting the report, conversation memory for follow-up questions, streaming responses for a more live feel, Docker packaging for one-command deployment, and evaluation metrics computed against the dataset's built-in test cases. None of these are required for the assistant to work today — they're the road ahead, not gaps in the foundation.

---

*In short: a thin, well-separated stack where a capable model does the reasoning, deterministic code makes the consequential decisions, and every layer can be swapped or tested in isolation.*
