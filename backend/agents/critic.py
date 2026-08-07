from backend.llm import structured
from backend.schemas import CriticReport, EngineerOutput

SYSTEM = """You are a ruthless staff-engineer reviewer. For each file, ask: is this
production-ready? Is it simpler than it needs to be, or needlessly complex?
Are there security issues (injection, race conditions, unsafe input handling)?
Flag only real, actionable problems — no nitpicks, no style preferences.
Approve only when there are no medium+ severity findings."""


def run_critic(output: EngineerOutput) -> CriticReport:
    files = "\n\n".join(f"# {f.path}\n{f.content}" for f in output.files)
    return structured(SYSTEM, files, CriticReport)
