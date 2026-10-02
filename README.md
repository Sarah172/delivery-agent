# delivery-agents

A small service surrounded by agents that automate its delivery lifecycle.

| Piece | Status |
|---|---|
| Target service (`app/`) with `/health` | Day 1 |
| CI workflow (`.github/workflows/ci.yml`) | Day 1 |
| MCP server (`mcp_server/`) exposing CI status to coding agents | Day 1 |
| LangGraph post-deployment verifier | Day 2 |
| Spec gate + spec-to-PR skill | Day 3 |
| Docker, logging, demo | Day 4 |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                          # 7 tests should pass
uvicorn app.main:app --reload      # then open http://localhost:8000/health
```

Simulate a bad deployment (used on Day 2):

```bash
FORCE_UNHEALTHY=1 uvicorn app.main:app
```

## MCP server

Three read-only tools over the GitHub Actions API:

| Tool | Purpose |
|---|---|
| `list_workflow_runs` | Recent CI runs, optionally by branch |
| `get_run_status` | One run, its jobs, and which steps failed |
| `get_failed_job_logs` | Tail of the log for each failed job |

### Configure

Create a fine-grained GitHub personal access token limited to this one
repository, with read-only **Actions** and **Metadata** permissions. Then:

```bash
export GITHUB_TOKEN=github_pat_...
export GITHUB_REPO=your-username/delivery-agents
```

### Connect to Claude Code

`.mcp.json` in this repo registers the server at project scope. Start
`claude` from the repo root (in the same shell where you exported the
variables), approve the server when prompted, and run `/mcp` to confirm
`delivery` is connected.

On Windows, change `command` in `.mcp.json` to `.venv\\Scripts\\python.exe`.

### Try it

- "Did the last CI run on main pass?"
- "Why did the latest run fail? Show me the relevant log lines."

## Design notes

- **Read-only by design.** The server can observe CI but not change it.
- **Repo is fixed by config**, not chosen by the model.
- **Logs are truncated to the tail** to keep the model's context small.
- **Errors are returned as readable text** so the agent can recover or report.
- **The GitHub client is separate from the MCP layer**, so it is unit-tested
  with a fake transport and can be reused by the Day 2 verifier.
