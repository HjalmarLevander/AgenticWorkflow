# Robin Swarm

A multi-agent coding system that turns a request
into reviewed, sandbox-verified code:

**Planner** (scopes the work, names the risk) → confirm → **HTML Draft**
(visual sketch, human-in-the-loop pause) → confirm → **Engineer** (writes
code + tests, grounded in a RAG-retrieved corpus of reference implementations)
→ **Critic** (reviews against the same reference corpus — cites specific
files, not vibes) → revise if rejected → **Runner** (actually executes the
code and its tests in an isolated Docker container — not an LLM opinion, a
real pass/fail).

The goal of this is to make the coding pipeline simpler. That is, prompt
project and start planning. Once planning is done, see an HTML draft of 
what final product should look like. Begin writing code. The engineer is
given a large context of concise production grade code. The intention of 
the engineer is to write as few lines of code as possible in order to make
human review simpler and eventually large scale projects more tractable. 
Then the critic includes multiple personas who discuss the code and see if 
any algorithm can be improved, what the inefficiencies are, etc. Lastly, the 
runner ensure everything is working as intended before you are provided the 
final result. 

## Architecture

```
VS Code Extension (TypeScript)         FastAPI Backend (Python)
  @robin chat participant      HTTP     backend/main.py
  webview for HTML draft      ─────▶    backend/orchestrator.py  (state machine)
  applyEdit() for final diff  ◀─────    backend/agents/*.py      (one file per agent)
                                        backend/style_vault.py   (local RAG over style_vault/)
                                        backend/agents/runner.py (Docker sandbox execution)
```

Every agent call is a stateless request to the Anthropic API — there's no
shared session between agents. The orchestrator passes each agent's typed
(Pydantic) output as text into the next agent's prompt; that's the entire
"communication" mechanism.

## Setup

**Prerequisites:** Python 3.12+, Docker (or [Colima](https://github.com/abiosoft/colima)
on macOS), Node 18+, and an Anthropic account with API credit.

```sh
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# Auth — either export ANTHROPIC_API_KEY, or:
ant auth login   # brew install anthropics/tap/ant, then this opens a browser

# Sandbox images (built once, cached after)
docker build -t robin-sandbox-python -f backend/sandbox/Dockerfile.python backend/sandbox
docker build -t robin-sandbox-node -f backend/sandbox/Dockerfile.node backend/sandbox

# Extension
cd extension && npm install
```

### Populating the style vault (optional but recommended)

Drop reference code into `style_vault/` (any `.py`/`.md`/`.rst`/`.txt`) —
your own old projects, or clone reference repos. `style_vault/` is
gitignored (it's third-party code, not something to carry in this repo's
history), so run the fetch script once after cloning to pull the same set
used during development:

```sh
./scripts/fetch_style_vault.sh
```

It's embedded locally (no API cost) on server startup, or on demand via
`POST /ingest-style`. This is what grounds the Engineer's style and the
Critic's judgment in real reference code instead of the model's priors alone.

## Running it

```sh
uvicorn backend.main:app --reload   # starts on :8000
```

Then in VS Code: open `extension/`, press F5 to launch the Extension
Development Host, and use `@robin <request>` in the chat panel.

### Cost

Defaults to `claude-sonnet-5`. A full run (plan → draft → build → review →
verify, no revisions needed) costs roughly **$0.05–0.15**. Check spend any
time via `GET /cost`, or override the model with `ROBIN_MODEL=claude-opus-5`.

## Repo layout

- `backend/` — FastAPI server, orchestrator, and the five agents
- `extension/` — VS Code chat participant
- `style_vault/` — your reference code (gitignored — this is local input, not source we own)
