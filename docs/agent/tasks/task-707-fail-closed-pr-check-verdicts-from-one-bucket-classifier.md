# Task 707: Fail-Closed PR Check Verdicts From One Bucket Classifier

**Issue**: [#707](https://github.com/dan-petty/devops-cli/issues/707)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

When `gh pr checks` exits non-zero, `devops pr checks` renders a REST fallback table and returns 0 (`src/devops_cli/commands/pr.py:383-385`). `tests/test_pr_cmd.py:715-755` asserts that exit 0 while `Analyze` fails, and `AGENTS.md:131` and `:250` tell agents to monitor CI with this command. When its single unpaginated check-runs call fails, `check-readiness` reports no check blockers (`pr.py:1241-1271`). A `blocked` state still stops failing required checks (`pr.py:1203-1212`), but under `unstable` or `--allow-blocked-state` it prints "satisfies merge readiness", the certification `AGENTS.md:244` relies on. `pr wait` passes `gh api --paginate` output to `json.loads` (`github/pr_monitor.py:413-443`), which rejects multi-page output, usually ending in a timeout rather than a pass. Four conclusion sets disagree (`pr_monitor.py:23-31`, `config/constants.py:412`, `pr.py:1269`, `pr.py:265`), and the only rollup parser, `_parse_check_runs` (`pr_monitor.py:240`), has no caller. MCP `pr_check_readiness` passes a `--require-ready` flag the CLI does not define (`ai/mcp/server.py:2280-2281`). vibes `docs/RETROSPECTIVE.md` §8 records `gh pr checks --exit-status | tail` exiting 0 on a failure.

#### Key Deliverables:
- **Deliverable**: Two PRs.
  - [x] **PR1**: Adds `github/check_verdict.py`, returning gh's buckets (pass, fail, pending, skipping, cancel) plus `unread`, read from `gh pr checks --json name,state,bucket,workflow,link` with REST fallback. `pr checks`, `pr ready` and `check-readiness` take their verdict from it: non-zero on `fail`, `cancel` or `unread`, exit 8 on pending as gh does, table still rendered. PR1 inverts the exit-0 test, adds a readiness test where check-runs fails under `unstable`, and drops the MCP `require_ready` argument.
  - [x] **PR2**: Moves `pr wait` and `monitor` onto the seam, keeping REST polling of `/check-runs` via `gh api --paginate --slurp` plus `/status`, with exactly one conclusion-to-bucket table and a parity test against `gh pr checks --json bucket`. PR2 deletes the other conclusion sets, `_parse_check_runs`, `_parse_check_run_node` and the duplicate `_fetch_commit_check_runs` (`pr.py:986`). No workflow lint is added (see Measured). Must land before the v0.2.24 `tab-github` hub, which binds readiness to `check-readiness`.
- **Constraint**: `gh pr checks --json` exits 0 even with a check in the `fail` bucket, so switching to JSON while keeping the exit-code logic would reproduce the defect; the verdict must come from the buckets. An empty, errored or partial read is `unread` and blocks. `--allow-pending-checks` excuses pending checks only; `pr ready --force` is the only override. Do not reuse `parse_paginated_json` (`github/client.py:394`): it stops silently at the first decode error (`client.py:414-415`), the same fail-open. Whether gh's rollup pages past its first query is unverified, so a test should assert the bucket count against REST `total_count`.
- **Measured**: On PR 401, `gh pr checks 401` exits 1, while `gh pr checks 401 --json name,state,bucket` exits 0 with 1 of 7 checks in `fail`. On that PR's head, `json.loads` rejects `gh api --paginate '.../check-runs?per_page=3'` output with "Extra data". `SHELLCHECK_OPTS=--enable=check-extra-masked-returns actionlint` reports 3 SC2312 findings, all command substitutions, none carrying a gate verdict.
- **Source**: vibes `docs/RETROSPECTIVE.md`, `AGENTS.md`, `CHANGELOG.md`
- [x] Unit and integration test coverage with structural tuple equality assertions.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
