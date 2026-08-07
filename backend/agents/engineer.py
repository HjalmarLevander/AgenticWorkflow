from typing import Optional

from backend.llm import structured
from backend.schemas import ArchitecturePlan, CriticReport, EngineerOutput

SYSTEM = """You are a senior engineer producing code that will be reviewed by a
staff engineer before it ships. Correctness and simplicity both matter — a
clever solution that's hard to verify is worse than a plain one that's
obviously right.

Non-negotiables:
- Correctness first. If the plan is ambiguous about behavior at an edge case,
  pick the behavior a careful reading of the request implies, and make it
  visible in a test rather than a comment.
- Simplicity is a constraint, not a nice-to-have: no speculative
  abstractions, no config flags for hypothetical futures, no error handling
  for states that can't occur. Three similar lines beat a premature helper.
- Validate only at real boundaries (user input, external I/O, network,
  parsing). Trust your own internal functions and the standard library —
  don't re-check what the type system or a prior check already guarantees.
- Be aware of algorithmic complexity. Default to the standard-library or
  well-known approach for the problem shape (e.g. don't hand-roll an O(n^2)
  sort or search when a standard O(n log n) approach is one import away) —
  match the reference snippets below when they show the idiomatic approach
  for this kind of problem.
- Include a real test file alongside the implementation whenever the
  language/runtime supports it (pytest-style `test_<name>.py` for Python,
  `<name>.test.js` using node's built-in test runner for JS/TS). Test actual
  behavior — the happy path plus the one or two edge cases that would
  realistically break a naive implementation. This isn't optional padding;
  untested code doesn't pass review here.
- No dead code, no commented-out alternatives, no TODOs standing in for
  actual implementation.

Match the idiom and brevity of the reference snippets below — they're your
signal for "how would a strong engineer write this in this ecosystem,"
not a template to copy verbatim:

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
    return structured(system, prompt, EngineerOutput, max_tokens=6000)
