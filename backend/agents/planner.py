from backend.llm import structured
from backend.schemas import ArchitecturePlan

SYSTEM = """You are a pragmatic software architect. Turn the request into a small,
concrete plan: the minimum set of components needed, nothing speculative.
Favor simple, well-understood layouts over novel ones."""


def run_planner(prompt: str) -> ArchitecturePlan:
    return structured(SYSTEM, prompt, ArchitecturePlan)
