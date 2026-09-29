# Task 706: Reviewer-Aware Reply Detection for Thread Resolution and Oldest-First PR Updates

**Issue**: [#706](https://github.com/dan-petty/devops-cli/issues/706)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

AGENTS.md:132 requires an in-thread reply before a thread is resolved, and AGENTS.md:240-245 require oldest-first PR processing. Nothing in `src/` enforces either. The reply test was `len(t.comments) > 1` (`commands/pr.py:1226`, `github/pr_threads.py:312`), so a reviewer's own follow-up counted as a reply. `--allow-replied-threads` then reported no blocker, and `--auto-resolve` and `threads resolve-all` (default `--only-replied`) closed the thread. The thread query already fetches each comment's `author { login }` (`github/pr_threads.py:114`). `threads resolve` (`commands/pr.py:1747`) resolved with no check. `update --all` iterated `_fetch_open_prs` (`commands/pr.py:1552`, loop at 1610) in `gh pr list` order, which is newest-first. vibes `patterns/fifo-pull-request-shepherding.md:77` also demands the fixing SHA in every reply. No devops-cli incident supports that rule yet (see Measured).

#### Key Deliverables:
- [x] *Context & Rationale*: Enforced reviewer-aware reply detection so that reviewer follow-ups (the probe case) are not counted as valid resolution replies, and guaranteed oldest-first (FIFO) PR updating.
- [x] *Deliverable*: Added `has_non_opener_reply(thread)` in `src/devops_cli/github/pr_threads.py` and wired at both call sites (`resolve_all_pr_review_threads` and `_evaluate_threads_blockers`). Reworded help strings in `lang/en/help.py` to "a reply from someone other than the thread opener", and added probe case regression tests. `threads resolve` refuses a thread without such a reply unless `--without-reply` (`-w`) is passed, and FastMCP `pr_thread_resolve` exposes `without_reply`. Open PRs sorted in ascending order by number in `sort_prs_oldest_first`, ensuring `update --all` runs oldest-first.
- [x] *Constraint*: Did not port the fixing SHA rule per task constraints to avoid rebase / force-push breakage.
- [x] *Measured*: Probe case regression tests verify threads with only reviewer self-replies are rejected and treated as unreplied blockers. Open PR sorting verified FIFO order.
- [x] *Source*: vibes `patterns/fifo-pull-request-shepherding.md`, vibes `patterns/multi-agent-codebase-concurrency.md`, vibes `observations/systems/06-multi-agent-concurrency-shared-workspace-hazards-and-swarm-coordination.md`.
- [x] Unit and integration test coverage with structural tuple equality assertions.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
