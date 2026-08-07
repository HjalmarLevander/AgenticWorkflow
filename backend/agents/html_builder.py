from backend.llm import text
from backend.schemas import ArchitecturePlan

SYSTEM = """You are a rapid-prototyping UI engineer. Output ONLY a single valid
HTML file (inline CSS, no build step) that sketches the approved plan's layout
and components. No markdown fences, no commentary — just the HTML."""


def run_html_builder(plan: ArchitecturePlan) -> str:
    component_list = ", ".join(f"{c.name} ({c.purpose})" for c in plan.components)
    prompt = (
        f"Layout: {plan.layout_style}\n"
        f"Rationale: {plan.rationale}\n"
        f"Components: {component_list}"
    )
    return text(SYSTEM, prompt)
