### Problem Description

Refine collects the context of an item with `git grep -n -F -w -e <identifier> <sha> --` over the whole tree at the pinned commit (`_collect_identifiers` in `src/devops_cli/roadmap/refine/refine.py`). `git_result` runs it with `timeout=15`. When the grep takes longer, `subprocess.TimeoutExpired` escapes from `refine_one_item`, and `plan_refine` stops with it. Refine does not record the item as a failed model call, so the item gets no failure class and no wait.

### Reproduction Steps

1. Run refine for #4135 (body names `crawl4ai`) on a loaded workstation: `uv run devops roadmap refine --item 4135`.
2. Time the same grep: `git grep -n -F -w -e crawl4ai HEAD -- | wc -l` gave 438 lines in 12.0 s on 2026-11-12.

### Expected vs Actual Behavior

- Expected: a slow grep cuts the context of the item, and refine goes on with the other parts of the context.
- Actual: `TimeoutExpired: Command '['git', '-C', '<checkout>', 'grep', '-n', '-F', '-w', '-e', 'crawl4ai', '<sha>', '--']' timed out after 15 seconds` stops the plan of the item.

### Proposed Solution

- Limit the grep to the paths that hold code and documents (for example a pathspec that leaves out `openspec/changes/archive/` and `tests/fixtures/`), or use `--max-count`.
- Treat a timeout of one grep as no result for that identifier, and log it.
- Open PR #4820 changes the symbol search of refine; check that it does not already cover this.

### Existing Tool Considered

git grep is the tool. The change is a pathspec and the handling of a timeout. Cost: about 20,000 tokens and 30 minutes.

### Acceptance Criteria

- A test with a git fake that times out on one grep shows that refine plans the item with the other context.

Source: the read-only replay of #4798 on 2026-11-12.


Source: https://github.com/dan-petty/devops-cli/pull/4874

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-14: none.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.adr_hash": "a1cd29eb2588913c344a50dcec7edc599fc9cc39aed976ed694194eb1398099a", "alternatives.body_hash": "8466119db20dcc97107e6eb12e1f612c3ec5e7b8f3624147f8014369890005c4", "alternatives.checked_at": "2026-11-14T21:09:34.594180+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": null, "alternatives.tool_id": null, "alternatives.verdict": "none", "intake.jev_shadow": "{\"at\":\"2026-11-12T00:56:50Z\",\"answers\":{\"priority\":[\"P1-High\",0.78,\"P2-Medium\"],\"value\":[\"Medium\",0.22,\"Medium\"],\"effort\":[\"Low\",0.88,\"Low\"],\"duplicate\":[\"\",0.05,\"\"]}}"} -->
