# Design

## Context

The agents of devops-cli get their scan tools from `get_default_tools` and the persona tool maps in `src/devops_cli/ai/tools/registry.py`. The tools are plain functions in `src/devops_cli/ai/tools/builtin_tools.py`, and pydantic-ai makes a tool schema from the signature of each one. The review scanners run the same scanners through the adapters of `devops_cli.security`, which return a `ScanOutcome` with a status, findings and a reason. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Each agent scan tool that has an adapter for a workspace path runs that adapter, and keeps no command line of its own.
- A reply never reads as clean when the scan gave no result.
- The scan commands that the MCP tools run report a missing Gitleaks as not run.

**Non-Goals:**

- The Popeye adapter, its flags and its parser (#1434).
- An adapter for `uv audit`.
- The JSON output of `devops scan trivy|sast|secrets`, which holds the findings and no status.

## Decisions

- **The reply starts with the status, in fixed words.** `CONST_AGENT_SCAN_STATUS_WORDS` gives `ok` to `ran` and `clean`, and `not installed` to `unavailable`, which every adapter but Gitleaks gives a missing tool. Every other status keeps its name, so `failed`, `not_applicable`, `coverage_gap`, `built-in patterns` and `dry-run` read as the adapters write them. Rejected: one new status enum for all adapters. The review pipeline, SARIF and `devops scan report` read the status strings that exist, so a rename is a change of its own.
- **A scan that gave no result says so in the reply.** For a status in `CONST_SCAN_NO_RESULT_STATUSES`, the reply ends with `The scan gave no result. Do not report the target as clean.` A model that reads only the end of a reply thus does not take an empty list for a clean target.
- **The reply is masked, then cut.** The status, the reason and the findings go through `mask_secrets` together, then `_truncated` cuts the text at `DEFAULT_TOOL_DIFF_MAX_CHARS`, with the same last line as before. `ScanOutcome` masks the reason before it cuts it for the same reason.
- **Semgrep takes the behavior of its adapter.** With no cached registry ruleset, `SemgrepScanner.scan` runs the rule pack alone and returns `coverage_gap` with the fetch command. The tool replies with that outcome. Rejected: the refusal that the tool had before, with no scan. It kept a second registry path next to the adapter. `devops scan sast` refuses because a person runs it and it must exit 1, but a tool reply can carry the findings of the rule pack and the gap together.
- **A Semgrep scan of a directory leaves out the directories of dependencies and data.** The adapter adds `--exclude` for each of `CONST_SEMGREP_EXCLUDED_DIRECTORIES`, as `devops scan sast` does. The old test said that the tool excluded no directory. That described the old command line, which the adapter replaces. The scan starts in the target directory, the working directory of the adapter, so Semgrep reads a relative config path from there, as `devops scan sast` does. For a cached registry ruleset the scan starts in the cache directory, as before.
- **The tests double the process edge through `scanner_fake`.** The tools take no `tool_executor`, because each parameter of a tool goes into the tool schema that the model reads. A test of a failed scan adds a scripted run to `scanner_fake.recorded`, and a test of a missing scanner sets PATH to an empty directory, so no fake and no process take part. #1982 rebuilds `scanner_fake` over `ToolExecutorFake`, and these tests then run through that fake. Rejected: a module-level executor that a test replaces. docs/TESTING.md refuses a module shaped for a test patch.
- **The scan commands read the same set of statuses.** `_handle_single_scanner_result` in `src/devops_cli/commands/scan.py` reads `CONST_SCAN_NO_RESULT_STATUSES` in place of its own tuple, which did not hold `not installed`. Rejected: a change of the Gitleaks status to `unavailable`. The review pipeline and its tests read `not installed` from that adapter, and this item does not need the rename.
- **Popeye and uv audit stay as they are.** Rejected: `scan_popeye` through `PopeyeScanner` now. `popeye --help` (0.22.1) shows that `-s error,warn` names sections, not a level, so the adapter would scan no resource and the reply would say `ok`. Rejected: a new uv audit adapter in this change. No adapter exists, and it is a scope of its own.

## Risks / Trade-offs

- [A Gitleaks leak reads as `failed`] → The Gitleaks adapter runs `detect --report-format json` with no `--report-path`, so Gitleaks writes no report on stdout, and a leak (exit 1) is a failed scan (#1434). Before, the agent tool replied that it detected no leak. A failed status is not a clean result, and #1434 fixes the report path.
- [A scan of a large workspace takes longer to record] → `DirectToolExecutor` records each run, with one `git status` of the targets in a checkout. `devops scan` makes the same record today.
