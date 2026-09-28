# Task 706: Reviewer-Aware Reply Detection for Thread Resolution and Oldest-First PR Updates

**Issue**: [#706](https://github.com/dan-petty/devops-cli/issues/706)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

AGENTS.md:132 requires an in-thread reply before a thread is resolved, and AGENTS.md:240-245 require oldest-first PR processing. Nothing in `src/` enforces either. The reply test is `len(t.comments) > 1` (`commands/pr.py:1226`, `github/pr_threads.py:312`), so a reviewer's own follow-up counts as a reply. `--allow-replied-threads` then reports no blocker, and `--auto-resolve` and `threads resolve-all` (default `--only-replied`) close the thread. The thread query already fetches each comment's `author { login }` (`github/pr_threads.py:114`). `threads resolve` (`commands/pr.py:1747`) resolves with no check. `update --all` iterates `_fetch_open_prs` (`commands/pr.py:1552`, loop at 1610) in `gh pr list` order, which is newest-first. vibes `patterns/fifo-pull-request-shepherding.md:77` also demands the fixing SHA in every reply. No devops-cli incident supports that rule yet (see Measured).

#### Key Deliverables:
- Context & Rationale*: AGENTS.md:132 requires an in-thread reply before a thread is resolved, and AGENTS.md:240-245 require oldest-first PR processing. Nothing in `src/` enforces either. The reply test is `len(t.comments) > 1` (`commands/pr.py:1226`, `github/pr_threads.py:312`), so a reviewer's own follow-up counts as a reply. `--allow-replied-threads` then reports no blocker, and `--auto-resolve` and `threads resolve-all` (default `--only-replied`) close the thread. The thread query already fetches each comment's `author { login }` (`github/pr_threads.py:114`). `threads resolve` (`commands/pr.py:1747`) resolves with no check. `update --all` iterates `_fetch_open_prs` (`commands/pr.py:1552`, loop at 1610) in `gh pr list` order, which is newest-first. vibes `patterns/fifo-pull-request-shepherding.md:77` also demands the fixing SHA in every reply. No devops-cli incident supports that rule yet (see Measured).
- Deliverable*: Add one predicate, `has_non_opener_reply(thread)`: some comment after the first has an author login different from the first comment's. Use it at both call sites. Reword `lang/en/help.py:678-690` to "a reply from someone other than the thread opener", and add the probe case as a regression test. `threads resolve` refuses a thread without such a reply unless `--without-reply` is passed, and MCP `pr_thread_resolve` exposes that flag. Sort open PRs by ascending number in one helper, so `update --all` runs oldest-first. In-Flight Work, PR Stagnation & Blocker Radar can reuse that helper. Queue position in `check-readiness`/`wait` belongs to that entry, whose body is in v0.2.24 while its matrix row says v0.2.23. Ship this fix separately and first: MCP `pr_check_readiness` appends the removed `--require-ready` (`ai/mcp/server.py:2280-2281`), and the CLI rejects it. Drop the flag, then fix `tests/test_fastmcp_contracts.py:519,532` and `docs/MCP_TOOLS.md:1138`.
- Constraint*: Do not port the SHA rule yet. A reply's SHA stops pointing at a branch commit after a rebase or force-push, because the rebase rewrites that commit. Agents would then re-reply after every rebase or stop rebasing, and a reasoned decline would need an empty commit. Do not add a readiness blocker either: threads resolved under the old rule would fail open PRs. Revisit both only after a devops-cli thread is seen resolved without a reply.
- Measured*: A thread whose only follow-up is the reviewer's own "Still not fixed." yields 0 blockers under `--allow-replied-threads` and is selected by `resolve-all --only-replied` (`uv run python -B replied_probe.py`, GitHub stubbed). The last 100 merged PRs (#379-#577) carry 9 review threads. All 9 were opened and self-resolved by CodeQL with no reply (`gh api graphql` over `pullRequests(states:MERGED,last:100){reviewThreads}`). `gh pr list --state all --limit 5` returned [577,576,575,574,573].
- Source*: vibes `patterns/fifo-pull-request-shepherding.md`, vibes `patterns/multi-agent-codebase-concurrency.md`, vibes `observations/systems/06-multi-agent-concurrency-shared-workspace-hazards-and-swarm-coordination.md`
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
