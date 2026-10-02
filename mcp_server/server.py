"""MCP server exposing read-only CI/CD status tools for one GitHub repo.

Run:  python -m mcp_server.server      (stdio transport, for Claude Code)

Design choices worth being able to explain:
  * Read-only on purpose. An agent that can only observe CI cannot break it.
  * One repo, set by config, not by the model. The model cannot be talked
    into reading some other repository.
  * Errors come back as plain text the model can act on, not stack traces.
  * Logs go to stderr. With stdio transport, stdout IS the protocol channel,
    so a stray print() would corrupt it.
"""

import json
import logging
import sys

from mcp.server.mcpserver import MCPServer

from mcp_server.github_client import GitHubClient, GitHubError

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("delivery-mcp")

mcp = MCPServer(
    "delivery",
    instructions=(
        "Read-only tools for inspecting GitHub Actions CI runs of the configured repository. "
        "Typical flow: list_workflow_runs -> get_run_status -> get_failed_job_logs."
    ),
)


def _client() -> GitHubClient:
    # Built per call so a missing token is reported as a tool error
    # instead of crashing the server at startup.
    return GitHubClient()


def _ok(data) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_workflow_runs(branch: str | None = None, limit: int = 5) -> str:
    """List the most recent CI workflow runs, newest first.

    Use this first to find a run_id. Optionally filter by branch name.
    Returns run_id, workflow, branch, commit, status and conclusion for each run.
    """
    log.info("list_workflow_runs branch=%s limit=%s", branch, limit)
    try:
        runs = await _client().list_runs(branch=branch, limit=limit)
    except GitHubError as exc:
        return f"ERROR: {exc}"
    return _ok(runs) if runs else "No workflow runs found."


@mcp.tool()
async def get_run_status(run_id: int) -> str:
    """Get one workflow run with its jobs and the names of any failed steps.

    Use this to answer 'did CI pass?' or to see which job and step failed.
    """
    log.info("get_run_status run_id=%s", run_id)
    try:
        return _ok(await _client().get_run(run_id))
    except GitHubError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
async def get_failed_job_logs(run_id: int, max_lines: int = 60) -> str:
    """Get the last lines of the log for each FAILED job in a run.

    Use this after get_run_status shows a failure, to find the cause.
    Returns only the tail of each log (max_lines, 10-300) to stay concise.
    """
    log.info("get_failed_job_logs run_id=%s max_lines=%s", run_id, max_lines)
    try:
        logs = await _client().get_failed_logs(run_id, max_lines=max_lines)
    except GitHubError as exc:
        return f"ERROR: {exc}"
    return _ok(logs) if logs else "This run has no failed jobs."


if __name__ == "__main__":
    mcp.run()
