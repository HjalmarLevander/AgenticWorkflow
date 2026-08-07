import os
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI

# Initialize client (Requires OPENAI_API_KEY environment variable)
client = OpenAI()

# ==========================================
# 1. The Schema: Forcing the Contract
# ==========================================
class UIComponent(BaseModel):
    name: str = Field(description="Name of the UI element (e.g., 'Sidebar', 'Ticker')")
    purpose: str = Field(description="What this component does")

class ArchitecturePlan(BaseModel):
    rationale: str = Field(description="Why this architecture was chosen")
    layout_style: str = Field(description="CSS strategy (e.g., CSS Grid, Flexbox)")
    components: List[UIComponent]
    file_name: str = Field(description="The target file name, e.g., 'hedgi_dashboard.html'")

# ==========================================
# 2. Agent 1: The Planner (Structured Output)
# ==========================================
def run_planner(prompt: str) -> ArchitecturePlan:
    """Forces the LLM to return a perfectly structured ArchitecturePlan object."""
    
    # Using .parse() instead of .create() is the magic here.
    # It forces the LLM to adhere to the schema and returns a typed Python object.
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a UI Architect. Create a modular plan."},
            {"role": "user", "content": prompt}
        ],
        response_format=ArchitecturePlan
    )
    
    return response.choices[0].message.parsed

# ==========================================
# 3. Agent 2: The Engineer (Consumer)
# ==========================================
def run_html_builder(plan: ArchitecturePlan) -> str:
    """Consumes the typed Pydantic object to ensure precise execution."""
    
    # Because of Pydantic, we can rely on 'plan.components' existing 
    # and being a list, 100% of the time. No KeyError handling needed.
    component_names = [c.name for c in plan.components]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an HTML/CSS Engineer. Output ONLY valid HTML. No markdown formatting."},
            {"role": "user", "content": f"Build a {plan.layout_style} layout containing: {component_names}. Rationale: {plan.rationale}"}
        ]
    )
    return response.choices[0].message.content

# ==========================================
# 4. The Orchestrator Loop
# ==========================================
if __name__ == "__main__":
    print("Agent Swarm Starting...\n")
    
    # 1. Planner decides *what* to build based on a broad prompt
    plan = run_planner("I need a quantitative trading dashboard with a sidebar and a main live chart area.")
    
    print(f"[Planner] Layout selected: {plan.layout_style}")
    print(f"[Planner] Components designed: {[c.name for c in plan.components]}")
    
    # -> IDEAL SPOT TO PAUSE FOR HUMAN-IN-THE-LOOP REVIEW <-
    
    # 2. Builder executes exactly what was planned
    print("\n[Builder] Writing HTML...")
    html_output = run_html_builder(plan)
    
    # 3. Save the artifact for VS Code to render
    with open(plan.file_name, "w") as f:
        f.write(html_output)
        
    print(f"\n[Orchestrator] Successfully generated and saved to {plan.file_name}")