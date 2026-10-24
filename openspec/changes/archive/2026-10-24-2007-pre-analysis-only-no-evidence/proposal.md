# Proposal

## Why

Issue #2007: `devops review ... --pre-analysis-only` still starts Ruff and mypy in the payloads stage, but its help says that the flag skips the stages after pre-analysis. The flag turns off the static scan, and `init_per_file_payloads` started the Ruff, mypy and C901 complexity evidence (`_run_review_evidence`) with no stage flag check. The "payloads 5.41s" in the output of #1919 is the time of these tools. `--no-static-scan` and `--reporting-only` had the same defect, so a benchmark with `--no-static-scan` still counted Ruff and mypy candidates as the model's.

## What Changes

- The static scan stage holds the Ruff, mypy and complexity evidence, after the security analyzers. When the stage is off, the review starts no analyzer and no evidence tool. This applies to `--pre-analysis-only`, `--no-static-scan` and `--reporting-only`.
- The skip line of the payloads stage names the evidence: "Static analyzers and Ruff, mypy and complexity evidence skipped (disabled via flag)".
- The `--no-static-scan` help says that the option also turns off the Ruff, mypy and complexity evidence. The generated command references and the knowledge base stage list agree.

The tools that a review starts are observable behavior, so the change has a spec delta (`review-stages`).

This change fits in one pull request.

## Capabilities

### New Capabilities

- `review-stages`: The stage options of a review decide which tools the review starts.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `init_per_file_payloads` runs `_run_review_evidence` only in the static scan branch.
- `src/devops_cli/lang/en/help.py`: the `--no-static-scan` help.
- `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`: the `static_scan` stage names the evidence tools and the options that turn the stage off.
- `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`, `docs/commands/review.md`: regenerated.
- `tests/test_scanner_tool_executor.py`: a test of the tools that a review with the static scan off starts.
- The speed changes of #2034 in `src/devops_cli/security/osv_scanner.py`, `src/devops_cli/security/mypy.py` and `src/devops_cli/core/repo.py` stay as they are.

## Feasibility

I confirmed the premise against the code of origin/main at d4d6816c:

- `resolve_stage_flags(pre_analysis_only=True)` gives `pre_analysis=True` and `static_scan`, `group_analysis` and `reporting` false (`src/devops_cli/ai/review/flags.py`).
- `init_per_file_payloads` checked `stage_flags.static_scan` only for `_run_static_scanners`, and then called `_run_review_evidence` for every review.
- The new test ran on that revision with a tree that has `[tool.mypy] python_version` and a `uv.lock`. For each of `--pre-analysis-only`, `--no-static-scan` and `--reporting-only`, the review started `python -I -m mypy`, which the test floor refused, after a Ruff request to the tool executor fake.
- `docs/SELF_IMPROVEMENT.md` says that a review with `--no-static-scan` "runs no scanners", so that every candidate is the model's. The change makes that sentence true for Ruff and mypy.

## Existing Tool Considered

None is necessary: the change moves one existing call into the branch of the existing static scan flag. The change deletes no internal code and adds no new code path.
