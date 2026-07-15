# Incident Investigation Agentic AI Assistant

An agentic AI assistant that helps semiconductor-fab equipment engineers investigate machine-downtime incidents. An engineer describes an incident in plain language; the assistant uses an LLM that **calls tools** to retrieve real evidence from the plant dataset (equipment, alarms, similar past incidents, maintenance, sensor traces, SOPs, escalation rules), reasons over it, and returns a **structured investigation report** with recommended actions and escalation advice.

> The full design write-up is in [`design_document.md`](design_document.md). Sample prompts and test cases are in [`docs/sample_prompts.md`](docs/sample_prompts.md).

## Highlights

- **Anthropic Claude** via [LiteLLM](https://github.com/BerriAI/litellm), behind an `LLMClient` interface (so tests inject a fake LLM — no network/keys needed).
- **Seven tools** the agent calls to ground every claim in retrieved data.
- **Deterministic escalation engine** — escalation is decided by code from the plant's rules, never guessed by the LLM.
- **Swappable everything** — SQLite, ChromaDB, the embedder and the LLM all sit behind interfaces and are wired in one place (`app/container.py`). Swap the database by changing a single line.
- **Runs offline for tests** — a hashing embedder and a fake LLM make the suite deterministic with no network or API keys.

## Architecture

```
React + Vite chat  ──HTTP──▶  FastAPI /investigate
                                    │
                              InvestigationAgent (tool-calling loop)
                                    │  LiteLLM ──▶ Anthropic Claude
                              ToolRegistry (7 tools)
                              ┌─────┴─────┐
                          SQLiteStore   ChromaVectorStore
                        (structured)   (similar incidents, SOPs)
```

The agent depends only on abstractions (`LLMClient`, `StructuredStore`, `VectorStore`, `EmbeddingProvider`, `Tool`). Concrete classes are named in exactly one place — the composition root — so any backing technology can be replaced without touching agent, tool, or API code. See [`design_document.md`](design_document.md) for the principles applied and where.

## Project layout

```
app/
  main.py            FastAPI app (transport only)
  container.py       Composition root — the ONE place concretes are wired
  config.py          Env-driven settings (12-factor)
  agent/             Tool-calling loop, prompts, report schema
  llm/               LLMClient interface + LiteLLM adapter
  tools/             Tool base/registry + the 7 tools
  data/              Store interfaces + SQLite/Chroma impls, embedders, loader
frontend/            React + Vite chat UI
tests/               pytest: tool unit tests + 4 scenario tests (offline)
docs/                sample prompts & test cases
data/                the Excel dataset (DB + vector index are generated here)
```

## Prerequisites

- **Python 3.10+**
- **Node 18+** (for the frontend)
- An **Anthropic API key** (`sk-ant-...`)

## Quick start

Two processes: the **backend** (FastAPI, port **8003**) and the **frontend**
(Vite dev server, port **5173**). Run each in its own terminal.

> The frontend proxies `/api` → `http://localhost:8003` (see
> `frontend/vite.config.js`). If you change the backend port, update that
> `target` to match.

### Terminal 1 — backend

```bash
# from the project root
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # then edit .env — you only need to set:
#   ANTHROPIC_API_KEY=sk-ant-...
# (LLM_MODEL already defaults to claude-opus-4-8)

uvicorn app.main:app --reload --port 8003
```

First launch loads the Excel dataset into SQLite and builds the ChromaDB vector
index automatically. This is idempotent — later starts skip the work and are
instant. (With `EMBEDDING_PROVIDER=local`, the first run also downloads a small
sentence-transformers model, which needs internet once.)

Verify it's up:

```bash
curl http://localhost:8003/health     # -> {"status":"ok"}
curl http://localhost:8003/tools      # -> the 7 registered tools
```

Interactive API docs: http://localhost:8003/docs

### Terminal 2 — frontend

```bash
cd frontend
npm install
npm run dev                          # serves http://localhost:5173
```

Open **http://localhost:5173** and click a sample incident or type your own.

### Try it without the frontend

```bash
curl -s http://localhost:8003/investigate \
  -H "Content-Type: application/json" \
  -d '{"incident":"Etcher-03 RF Power Instability, 45 min, LOT1055, twice last week."}'
```

## Run the backend in Docker (alternative to Terminal 1)

Instead of a local virtualenv, you can run the API in a container. This
replaces **Terminal 1** only — run the frontend the same way as above.

Requires **Docker Desktop** running (`docker info` should succeed).

1. Put your key in `.env` (compose reads it from there; nothing secret is baked
   into the image):

   ```bash
   cp .env.example .env               # then set ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Build and start the API:

   ```bash
   docker compose up --build          # serves the API on http://localhost:8003
   ```

   The image installs dependencies and bundles the dataset; on first start the
   container loads SQLite and builds the vector index. The `./data` folder is
   mounted in, so the generated DB and index persist across restarts.

3. Verify it's up (in another terminal):

   ```bash
   curl http://localhost:8003/health  # -> {"status":"ok"}
   ```

4. Stop it:

   ```bash
   docker compose down                # add -v to also clear the mounted data
   ```

> First build uses `EMBEDDING_PROVIDER=local`, which downloads a small
> sentence-transformers model at runtime (needs internet once). Set
> `EMBEDDING_PROVIDER=hash` in `.env` for a fully offline container.

### Choosing the model

Set `LLM_MODEL` in `.env` to any Anthropic model. The call is routed through LiteLLM, and
the agent depends only on the `LLMClient` interface — so swapping to another
provider later would mean one new adapter, not changes across the app.

### Embeddings

`EMBEDDING_PROVIDER` in `.env`: `local` (sentence-transformers, default, offline
after first download) or `hash` (zero-dependency fallback for CI/tests).

## Testing

```bash
pytest -q
```

Covers all seven tools plus the four required scenarios (normal, missing info,
repeated, unknown alarm). Tests run fully offline — real SQLite + real Chroma
with the hashing embedder, and a scripted fake LLM injected in place of the real
one (made possible by the dependency-injection design).

## Configuration reference

All via environment / `.env` (see `.env.example`): `LLM_MODEL`,
`ANTHROPIC_API_KEY`, `EMBEDDING_PROVIDER`, `DATASET_PATH`, `SQLITE_PATH`,
`CHROMA_PATH`, `MAX_TOOL_ITERATIONS`.
