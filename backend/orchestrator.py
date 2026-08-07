"""Runs the swarm pipeline, pausing at the two human-in-the-loop checkpoints:
plan approval ("go for it") and HTML draft approval.
"""
from backend.agents.critic import run_critic
from backend.agents.engineer import run_engineer
from backend.agents.html_builder import run_html_builder
from backend.agents.planner import run_planner
from backend.agents.runner import run_runner
from backend.schemas import Stage, SwarmState
from backend.style_vault import query_style

MAX_REVISIONS = 3
SESSIONS: dict[str, SwarmState] = {}


def start(session_id: str, prompt: str) -> SwarmState:
    state = SwarmState(session_id=session_id, prompt=prompt)
    state.plan = run_planner(prompt)
    state.stage = Stage.AWAITING_PLAN_APPROVAL
    SESSIONS[session_id] = state
    return state


def approve_plan(session_id: str) -> SwarmState:
    state = SESSIONS[session_id]
    state.stage = Stage.DRAFTING_HTML
    state.html_draft = run_html_builder(state.plan)
    state.stage = Stage.AWAITING_DRAFT_APPROVAL
    return state


def approve_draft(session_id: str) -> SwarmState:
    state = SESSIONS[session_id]
    state.stage = Stage.ENGINEERING
    _build_and_review(state)
    return state


def _build_and_review(state: SwarmState) -> None:
    style_context = query_style(f"{state.plan.rationale}\n{state.plan.layout_style}")
    feedback = None

    while True:
        state.engineer_output = run_engineer(state.plan, style_context, feedback)
        state.stage = Stage.CRITIQUING
        state.critic_report = run_critic(state.engineer_output)

        if state.critic_report.approved or state.revision_count >= MAX_REVISIONS:
            break
        feedback = state.critic_report
        state.revision_count += 1
        state.stage = Stage.ENGINEERING

    state.stage = Stage.RUNNING
    state.run_result = run_runner(state.engineer_output)
    state.stage = Stage.DONE if state.run_result.passed else Stage.FAILED


def get(session_id: str) -> SwarmState:
    return SESSIONS[session_id]
