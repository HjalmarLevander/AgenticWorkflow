import re

from backend.llm import text
from backend.schemas import ArchitecturePlan

# HTML/CSS layout is where models most reliably go wrong: elements overlapping
# because of stray `position: absolute`, content getting clipped by a fixed
# height, or a grid that silently collapses on real content instead of the
# placeholder text the model imagined. These rules target those failure modes
# specifically, not generic "write good code" advice.
SYSTEM = """You are a rapid-prototyping UI engineer producing a single self-contained
HTML file (inline CSS, no build step, no external resources) that sketches
the approved plan's layout. Output ONLY the HTML — no markdown fences, no
commentary.

Layout rules — these exist because AI-generated HTML/CSS overlaps and clips
content more often than it should. Follow them exactly:

1. LAYOUT ENGINE: Use CSS Grid or Flexbox for structure. Never use
   `position: absolute` or `position: fixed` to place a layout region (a
   sidebar, a header, a card) — that's how elements end up overlapping when
   content length varies. The only acceptable use of absolute/fixed
   positioning is a genuine overlay (tooltip, modal, dropdown) *stacked on
   top of* normal-flow content — and if you use it, add a comment explaining
   why that element specifically needs to break out of the flow.

2. NO FIXED HEIGHTS ON CONTENT CONTAINERS: Never set a fixed `height` (in px)
   on an element that holds text or a variable number of children — use
   `min-height` instead, or let it size to content. A fixed height is why
   real content gets clipped even though the placeholder text fit fine.

3. SIZE DEFENSIVELY: Put `box-sizing: border-box` on `*` at the top of your
   CSS. Add `overflow-wrap: break-word` (or `word-break: break-word`) to any
   element that holds user-generated or variable-length text, so a long
   value can't push past its container. Wrap any table or wide content in a
   container with `overflow-x: auto` rather than letting it blow out the
   page width.

4. PICK ONE OF THESE STRUCTURAL PATTERNS based on what the plan calls for —
   don't invent a bespoke positioning scheme when one of these fits:

   - Single column (stacked panels/sections): each section is a normal
     block-level element in document flow, `max-width` centered, vertical
     gap via `margin-bottom` or a flex column with `gap`.
   - Sidebar + main: `display: grid; grid-template-columns: <fixed-width>
     1fr;` on the outer container — never absolute-position the sidebar.
   - Header + content: `display: flex; flex-direction: column;` on the page
     root, header as a normal flex child, content area `flex: 1`.
   - Card/stat grid: `display: grid; grid-template-columns: repeat(auto-fit,
     minmax(<min-card-width>, 1fr)); gap: <spacing>;` — this is what makes a
     "grid of N cards" reflow correctly instead of overlapping or
     overflowing when N doesn't divide evenly.

5. EVERY ELEMENT NEEDS ITS OWN SPACE: before finishing, mentally check that
   no two visible elements are positioned to occupy the same region of the
   page at the same time, unless one is a deliberate overlay per rule 1.
   A layout where the sidebar and main content could visually collide, or
   where a header could sit on top of the content below it, is a defect —
   not a style choice.

Match the plan's `layout_style` and component list, but the concrete pattern
you build with must be one of the four above."""

# The model doesn't reliably follow "no markdown fences" — verified: it wraps
# output in ```html even when told not to. Strip defensively rather than
# trusting the instruction, since this gets assigned straight to
# webview.html and a literal fence would render as broken text, not HTML.
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")

# Cheap, non-blocking lint for the one failure mode prompting can't fully
# prevent: absolute/fixed positioning used for layout rather than a genuine
# overlay. This can't tell intent apart from a comment reliably, so it only
# warns — but it gives visibility instead of silently shipping a layout bug.
_RISKY_POSITIONING_RE = re.compile(r"position:\s*(absolute|fixed)")


def run_html_builder(plan: ArchitecturePlan) -> str:
    component_list = ", ".join(f"{c.name} ({c.purpose})" for c in plan.components)
    prompt = (
        f"Layout: {plan.layout_style}\n"
        f"Rationale: {plan.rationale}\n"
        f"Components: {component_list}"
    )
    # HTML+CSS for a multi-component layout easily exceeds a few thousand
    # tokens — verified: a 4-component dashboard truncated mid-file at 4000.
    html = text(SYSTEM, prompt, max_tokens=8000).strip()
    html = _FENCE_RE.sub("", html).strip()

    risky = _RISKY_POSITIONING_RE.findall(html)
    if risky:
        print(f"[html_builder] warning: {len(risky)} absolute/fixed positioning rule(s) "
              f"in generated HTML — verify these are genuine overlays, not layout hacks.")

    return html
