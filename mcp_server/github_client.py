"""Thin, read-only GitHub Actions client.

Kept separate from the MCP layer so it can be unit-tested without MCP, and
reused later by the LangGraph verifier.
"""

import os

import httpx

API = "https://api.github.com"


class GitHubError(Exception):
    """An error with a message that is safe and useful to show to the model."""


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPO")  # "owner/name"
        if not self.token:
            raise GitHubError("GITHUB_TOKEN is not set.")
        if not self.repo or "/" not in self.repo:
            raise GitHubError("GITHUB_REPO must be set as 'owner/name'.")
        self._transport = transport

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(
            base_url=API,
            headers=headers,
            timeout=20,
            follow_redirects=True,  # job logs redirect to a download URL
            transport=self._transport,
        ) as client:
            try:
                resp = await client.get(path, params=params)
            except httpx.HTTPError as exc:
                raise GitHubError(f"Network error calling GitHub: {exc}") from exc

        if resp.status_code == 401:
            raise GitHubError("GitHub rejected the token (401). Check GITHUB_TOKEN.")
        if resp.status_code == 403:
            raise GitHubError("GitHub returned 403: rate limited, or the token lacks Actions read access.")
        if resp.status_code == 404:
            raise GitHubError(f"Not found (404): {path}. Check GITHUB_REPO and the id.")
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub returned {resp.status_code} for {path}.")
        return resp

    async def list_runs(self, branch: str | None = None, limit: int = 5) -> list[dict]:
        params: dict = {"per_page": max(1, min(limit, 20))}
        if branch:
            params["branch"] = branch
        resp = await self._get(f"/repos/{self.repo}/actions/runs", params)
        return [
            {
                "run_id": r["id"],
                "workflow": r.get("name"),
                "branch": r.get("head_branch"),
                "commit": (r.get("head_sha") or "")[:7],
                "event": r.get("event"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "created_at": r.get("created_at"),
                "url": r.get("html_url"),
            }
            for r in resp.json().get("workflow_runs", [])
        ]

    async def get_run(self, run_id: int) -> dict:
        run = (await self._get(f"/repos/{self.repo}/actions/runs/{run_id}")).json()
        jobs = (await self._get(f"/repos/{self.repo}/actions/runs/{run_id}/jobs")).json()
        return {
            "run_id": run["id"],
            "workflow": run.get("name"),
            "branch": run.get("head_branch"),
            "commit": (run.get("head_sha") or "")[:7],
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "url": run.get("html_url"),
            "jobs": [
                {
                    "job_id": j["id"],
                    "name": j.get("name"),
                    "status": j.get("status"),
                    "conclusion": j.get("conclusion"),
                    "failed_steps": [
                        s.get("name") for s in j.get("steps", []) if s.get("conclusion") == "failure"
                    ],
                }
                for j in jobs.get("jobs", [])
            ],
        }

    async def get_failed_logs(self, run_id: int, max_lines: int = 60) -> list[dict]:
        """Return only the tail of each failed job's log.

        Full CI logs can be thousands of lines. Returning the tail keeps the
        model's context small and focused on where the failure is reported.
        """
        max_lines = max(10, min(max_lines, 300))
        run = await self.get_run(run_id)
        failed = [j for j in run["jobs"] if j["conclusion"] == "failure"]
        out = []
        for job in failed:
            resp = await self._get(f"/repos/{self.repo}/actions/jobs/{job['job_id']}/logs")
            lines = resp.text.splitlines()
            out.append(
                {
                    "job": job["name"],
                    "failed_steps": job["failed_steps"],
                    "total_lines": len(lines),
                    "log_tail": "\n".join(lines[-max_lines:]),
                }
            )
        return out
