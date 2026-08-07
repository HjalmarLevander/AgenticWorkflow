"""Local FastAPI server orchestrating the agent swarm. Run with:
    uvicorn backend.main:app --reload
"""
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from backend import orchestrator
from backend.schemas import SwarmState
from backend.style_vault import ingest

app = FastAPI(title="Agent Swarm")


@app.on_event("startup")
def _ingest_style_vault() -> None:
    ingest()


class RunRequest(BaseModel):
    prompt: str


@app.post("/run")
def run(req: RunRequest) -> SwarmState:
    session_id = str(uuid.uuid4())
    return orchestrator.start(session_id, req.prompt)


@app.get("/status/{session_id}")
def status(session_id: str) -> SwarmState:
    try:
        return orchestrator.get(session_id)
    except KeyError:
        raise HTTPException(404, "unknown session")


@app.post("/approve-plan/{session_id}")
def approve_plan(session_id: str) -> SwarmState:
    return orchestrator.approve_plan(session_id)


@app.post("/approve-draft/{session_id}")
def approve_draft(session_id: str, background: BackgroundTasks) -> SwarmState:
    state = orchestrator.get(session_id)
    background.add_task(orchestrator.approve_draft, session_id)
    return state


@app.post("/ingest-style")
def ingest_style() -> dict:
    """Call after adding/updating files in style_vault/ to re-embed them."""
    return {"chunks_indexed": ingest()}
