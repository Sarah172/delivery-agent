# agentic-mcp-compliance-engine

An AWS IAM compliance auditor where a deterministic rule engine finds the
risks and an LLM explains them and drafts least-privilege fixes.

| Piece | File |
|---|---|
| MCP server exposing the IAM dump as a read-only tool | `server.py` |
| Deterministic rule engine | `rules.py` |
| Agent client: MCP fetch, rule scan, LLM triage, report | `client.py` |
| Sample AWS IAM authorization dump (Cloudsplaining format, ~800 KB) | `cloudsplaining_iam_details.json` |

## How it works

1. **Fetch.** `client.py` spawns `server.py` over stdio and calls the
   `fetch_cloud_policies` tool, which returns the IAM dump. The client closes
   the MCP session as soon as the data is in memory, which avoids timeouts on
   large payloads.
2. **Detect.** `rules.py` walks every user, role, group and policy and flags:

   | Rule | Risk category |
   |---|---|
   | `AdministratorAccess` attached | Privilege Escalation |
   | Wildcard `"Action": "*"` | Infrastructure Modification |
   | `s3:*` | Data Exfiltration |

3. **Explain.** Only the confirmed findings, not the raw dump, are sent to
   `gpt-4o-mini`. The response is parsed into a Pydantic `AuditReport`
   (severity, category, resource, explanation, remediation) using OpenAI
   structured outputs.
4. **Report.** The client writes `Compliance_Audit_Report_<timestamp>.md`
   with each finding's risk analysis and a corrected IAM policy snippet.

On the sample dump (44 users, 78 roles, 5 groups, 84 policies) the rule
engine flags 56 findings.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env
python client.py                   # spawns server.py; writes the report
```

## Design notes

- **The model never decides what is a vulnerability.** Detection is plain
  Python, so results are reproducible and auditable. The LLM only explains
  findings and proposes fixes.
- **Minimal context.** The LLM receives the list of findings, not the
  ~800 KB dump.
- **Read-only tool.** The MCP server can read one configured file and
  nothing else.
- **Typed output.** LLM responses must validate against a Pydantic schema
  before they reach the report.

An earlier version sent the whole dump to the LLM and asked it to find the
risks. That was slow, heavy on context, and impossible to reproduce, which
led to the current rule-engine-first design.

## Known limitations and next steps

- **Fail closed.** A rule engine error currently returns no findings, which
  the client reports as "secure." Errors should stop the run instead.
- **Deterministic severity.** Severity is still assigned by the LLM. It
  should be mapped per rule in `rules.py` and typed as an enum.
- **Statement-level parsing.** Rules match strings in the serialized JSON.
  They should parse each statement, respect `Effect: Deny`, and catch `*`
  inside action lists.
- **Coverage check.** Verify that the report includes every finding the rule
  engine produced.
- **Tests and CI.** Turn the sample data into pytest golden cases, and run
  them in GitHub Actions.
- **More rules.** Add the remaining Cloudsplaining categories, such as
  resource exposure and specific privilege-escalation paths.
