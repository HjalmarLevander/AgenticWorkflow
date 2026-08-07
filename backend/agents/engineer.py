from typing import Optional

from backend.llm import structured
from backend.schemas import ArchitecturePlan, CriticReport, EngineerOutput

SYSTEM = """You are a senior engineer who writes short, readable, production-grade
code. Prefer the simplest correct solution over a clever or defensive one — no
speculative abstractions, no unrequested error handling, no dead code.
Match the style and idioms shown in the reference snippets below when given.

Reference style (mimic brevity and idiom, not the exact problem):
{style_context}"""


def run_engineer(
    plan: ArchitecturePlan,
    style_context: str,
    critic_feedback: Optional[CriticReport] = None,
) -> EngineerOutput:
    system = SYSTEM.format(style_context=style_context or "(none provided)")
    prompt = f"Build this plan:\n{plan.model_dump_json(indent=2)}"
    if critic_feedback:
        issues = "\n".join(f"- [{f.severity}] {f.file}: {f.summary}" for f in critic_feedback.findings)
        prompt += f"\n\nFix these issues from review, keep everything else:\n{issues}"
    return structured(system, prompt, EngineerOutput)
