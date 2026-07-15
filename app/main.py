"""FastAPI application — the transport layer.

Principle: Separation of Concerns — HTTP concerns live here only. The endpoint
delegates immediately to the injected InvestigationAgent and knows nothing
about tools, stores or the LLM provider.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.report import InvestigationReport
from app.config import settings
from app.container import Container, build_container

# --- request/response models (typed I/O contract) --------------------------


class InvestigateRequest(BaseModel):
    incident: str


class InvestigateResponse(BaseModel):
    report: InvestigationReport | None
    trace: list[dict]
    raw_text: str | None = None


# --- app lifecycle ----------------------------------------------------------
# Build the DI container once at startup and stash it on app.state (so the
# heavy stores/models are created a single time, not per request).
_container: Container | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _container
    _container = build_container(settings)
    yield


app = FastAPI(title="Incident Investigation Agent", lifespan=lifespan)

# Allow the Vite dev server to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-friendly; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> dict[str, list[str]]:
    """Introspection: which tools the agent can call."""
    assert _container is not None
    return {"tools": _container.registry.names()}


@app.post("/investigate", response_model=InvestigateResponse)
def investigate(req: InvestigateRequest) -> InvestigateResponse:
    """Run one incident investigation and return the structured report (blocking)."""
    assert _container is not None
    result = _container.agent.investigate(req.incident)
    return InvestigateResponse(
        report=result.report, trace=result.trace, raw_text=result.raw_text
    )


@app.post("/investigate/stream")
def investigate_stream(req: InvestigateRequest) -> StreamingResponse:
    """Stream the investigation as Server-Sent Events.

    Emits `status` events as each step happens, then one `final` event carrying
    the structured report + trace. The agent's generator is synchronous;
    Starlette iterates it in a threadpool, so the blocking LLM calls don't stall
    the event loop and each event flushes as soon as it's produced.
    """
    assert _container is not None

    def event_source() -> Iterator[str]:
        for event in _container.agent.stream(req.incident):
            if event["type"] == "final":
                result = event["report"]
                payload = {
                    "type": "final",
                    "report": result.report.model_dump() if result.report else None,
                    "trace": result.trace,
                    "raw_text": result.raw_text,
                }
            else:
                payload = event  # status events are already JSON-serialisable
            yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush
        },
    )
