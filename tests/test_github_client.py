"""Tests use a fake HTTP transport, so no network or real token is needed."""

import asyncio

import httpx
import pytest

from mcp_server.github_client import GitHubClient, GitHubError

REPO = "octo/demo"


def make_client(handler) -> GitHubClient:
    return GitHubClient(token="t", repo=REPO, transport=httpx.MockTransport(handler))


def fake_github(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == f"/repos/{REPO}/actions/runs":
        return httpx.Response(200, json={"workflow_runs": [
            {"id": 1, "name": "CI", "head_branch": "main", "head_sha": "abcdef123456",
             "event": "push", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-02T10:00:00Z", "html_url": "https://example/run/1"},
        ]})
    if path == f"/repos/{REPO}/actions/runs/1":
        return httpx.Response(200, json={"id": 1, "name": "CI", "head_branch": "main",
                                         "head_sha": "abcdef123456", "status": "completed",
                                         "conclusion": "failure", "html_url": "https://example/run/1"})
    if path == f"/repos/{REPO}/actions/runs/1/jobs":
        return httpx.Response(200, json={"jobs": [
            {"id": 10, "name": "test", "status": "completed", "conclusion": "failure",
             "steps": [{"name": "Install", "conclusion": "success"},
                       {"name": "Run tests", "conclusion": "failure"}]},
            {"id": 11, "name": "lint", "status": "completed", "conclusion": "success", "steps": []},
        ]})
    if path == f"/repos/{REPO}/actions/jobs/10/logs":
        return httpx.Response(200, text="\n".join(f"line {i}" for i in range(500)))
    return httpx.Response(404)


def test_list_runs_shapes_output():
    runs = asyncio.run(make_client(fake_github).list_runs())
    assert runs[0]["run_id"] == 1
    assert runs[0]["commit"] == "abcdef1"
    assert runs[0]["conclusion"] == "failure"


def test_get_run_reports_failed_steps():
    run = asyncio.run(make_client(fake_github).get_run(1))
    assert run["jobs"][0]["failed_steps"] == ["Run tests"]


def test_failed_logs_only_failed_jobs_and_truncated():
    logs = asyncio.run(make_client(fake_github).get_failed_logs(1, max_lines=20))
    assert len(logs) == 1 and logs[0]["job"] == "test"
    assert logs[0]["total_lines"] == 500
    assert logs[0]["log_tail"].splitlines() == [f"line {i}" for i in range(480, 500)]


def test_bad_token_gives_readable_error():
    client = make_client(lambda request: httpx.Response(401))
    with pytest.raises(GitHubError, match="401"):
        asyncio.run(client.list_runs())


def test_missing_config_is_rejected(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    with pytest.raises(GitHubError):
        GitHubClient()
