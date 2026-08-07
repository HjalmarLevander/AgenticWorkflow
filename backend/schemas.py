"""Pydantic contracts passed between agents. Every agent call is typed end to end."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UIComponent(BaseModel):
    name: str
    purpose: str


class ArchitecturePlan(BaseModel):
    rationale: str
    layout_style: str
    components: list[UIComponent]
    file_name: str = Field(description="Target HTML sketch file, e.g. 'dashboard.html'")


class SourceFile(BaseModel):
    path: str
    content: str


class EngineerOutput(BaseModel):
    summary: str
    files: list[SourceFile]


class Finding(BaseModel):
    file: str
    line: Optional[int] = None
    summary: str
    severity: str = Field(description="low | medium | high | critical")


class CriticReport(BaseModel):
    findings: list[Finding]
    approved: bool = Field(description="True if production-ready with no blocking findings")


class RunResult(BaseModel):
    passed: bool
    log: str


class Stage(str, Enum):
    PLANNING = "planning"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    DRAFTING_HTML = "drafting_html"
    AWAITING_DRAFT_APPROVAL = "awaiting_draft_approval"
    ENGINEERING = "engineering"
    CRITIQUING = "critiquing"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SwarmState(BaseModel):
    session_id: str
    prompt: str
    stage: Stage = Stage.PLANNING
    plan: Optional[ArchitecturePlan] = None
    html_draft: Optional[str] = None
    engineer_output: Optional[EngineerOutput] = None
    critic_report: Optional[CriticReport] = None
    run_result: Optional[RunResult] = None
    revision_count: int = 0
    error: Optional[str] = None
