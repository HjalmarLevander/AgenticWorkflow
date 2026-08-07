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
    """Runs as a FastAPI BackgroundTask — exceptions here are silently
    swallowed by the framework unless caught, which would otherwise leave
    the session stuck at whatever stage it was on forever, with no signal
    to the polling client that anything went wrong. Always land on a
    terminal stage."""
    state = SESSIONS[session_id]
    state.stage = Stage.ENGINEERING
    try:
        _build_and_review(state)
    except Exception as e:
        state.stage = Stage.FAILED
        state.error = f"{type(e).__name__}: {e}"
    return state


def _build_and_review(state: SwarmState) -> None:
    """Two independent revision triggers share one budget (MAX_REVISIONS):
    the Critic rejecting the code, or the Runner actually failing to execute
    it. Runner failure is ground truth and was previously a dead end — the
    pipeline would record the failure and stop instead of sending it back to
    the Engineer, even though a critic-approved change can still fail to
    run (verified: missing a dependency, or a bug the Critic's read-through
    didn't catch)."""
    style_context = query_style(f"{state.plan.rationale}\n{state.plan.layout_style}")
    critic_feedback = None
    runner_feedback = None

    while True:
        state.engineer_output = run_engineer(state.plan, style_context, critic_feedback, runner_feedback)
        critic_feedback = runner_feedback = None

        state.stage = Stage.CRITIQUING
        state.critic_report = run_critic(state.engineer_output)
        if not state.critic_report.approved and state.revision_count < MAX_REVISIONS:
            critic_feedback = state.critic_report
            state.revision_count += 1
            state.stage = Stage.ENGINEERING
            continue

        state.stage = Stage.RUNNING
        state.run_result = run_runner(state.engineer_output)
        if not state.run_result.passed and state.revision_count < MAX_REVISIONS:
            runner_feedback = state.run_result
            state.revision_count += 1
            state.stage = Stage.ENGINEERING
            continue

        break

    state.stage = Stage.DONE if state.run_result.passed else Stage.FAILED


def get(session_id: str) -> SwarmState:
    return SESSIONS[session_id]
