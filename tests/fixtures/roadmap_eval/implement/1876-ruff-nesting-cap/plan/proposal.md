# Proposal

## Why

Issue #1876, part 2 of decision 5: Ruff's `PLR1702` (too-many-nested-blocks) takes the place of the `structural-invariants` pre-commit hook. The hook ran a nesting metric that the project wrote (`core/code_metrics.py`), and a leg of the whole-tree test ran the same metric again. Part 1, #2010, made the tree clean under Ruff preview without a setting change.

## What Changes

- `pyproject.toml` selects `PLR1702` with `max-nested-blocks = 4`. `PLR1702` is a preview rule, so `[tool.ruff.lint]` sets `preview = true` with `explicit-preview-rules = true`: no preview rule runs that `select` does not name. Preview is set for lint only, so the formatter keeps its stable style.
- The cap is 4, not the 5 of the owner's 2026-10-22 decision. At 4, Ruff fails five nested `if`, `for`, `while`, `with` or `except` blocks, as the hook did at `--max-depth 5`. At 5, Ruff allows a fifth block, which is one level looser than the hook. A stricter cap needs no approval.
- 12 functions in `src` had 5 nested blocks when a `try` body counts, which the hook did not count. Each one moves a block into a helper, with the same behavior.
- The `structural-invariants` hook, the nesting leg of `test_the_source_tree_keeps_its_structural_invariants`, `nesting_depth`, `breaches`, `main`, `_NESTING`, the `max_nesting_depth` field and `DEFAULT_MAX_NESTING_DEPTH` are deleted.
- `devops scan complexity` loses `--max-indent` and its nesting findings, and the MCP tool loses `max_indent`. The architecture spec verifier (`devops ai spec`) loses the `max_indentation` rule, and keeps one passing or failing forbidden-import rule for each file. These are the answers to decision 3 of #1876.
- `tests/test_ruff_complexity_cap.py` holds the cap of 4, the preview settings and the formatter's stable style, and it has a negative control: five nested `if` blocks fail and four pass.
- `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`, `docs/VISION.md` and the code-review knowledge-base page name `PLR1702` at 4.
- The command, the MCP tool and the lint gate change behavior that a consumer sees, so the change carries a spec delta: the new capability `lint-nesting-cap`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `lint-nesting-cap`: Ruff caps nesting at 4 blocks through explicit lint preview, and the scanner and the spec verifier report no nesting depth.

## Impact

- `pyproject.toml`, `.pre-commit-config.yaml`.
- `src/devops_cli/core/code_metrics.py`, `security/complexity.py`, `commands/scan.py`, `ai/spec/verifier.py`, `config/defaults.py`, `lang/en/help.py`.
- The 12 functions in `ai/agents/agent.py`, `ai/harness/slots.py`, `ai/kb.py`, `ai/mcp/dispatcher.py`, `ai/spend/transport.py`, `argo/gitops.py`, `commands/ai.py`, `commands/k8s/networking.py`, `config/settings.py`, `dry_run/decorator.py`, `k8s/service.py` and `security/aibom.py`.
- Tests: `test_ruff_complexity_cap.py`, `test_code_metrics.py`, `test_scan_complexity.py`, `test_ai_spec.py`, `test_architectural_invariants.py`, `test_review_ruff_mypy_evidence.py`, `test_docs_command_resolver.py`.
- Docs: the files above, and the regenerated `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/scan.md`.
- Follow-up: #2600 decides whether `devops scan complexity` and the inspection hotspots read Ruff's `C901` count in place of the McCabe port (decision 4 of #1876).

## Feasibility

Checked on origin/main `c96dbfe3` (after #2010) with Ruff 0.16.8, the version of the pre-commit `ruff-check` hook and of `uv.lock`:

- `ruff rule PLR1702`: "This rule is in preview and is not stable." Its option is `lint.pylint.max-nested-blocks`, default 5.
- With preview on, `explicit-preview-rules = true` and `PLR1702` selected, `ruff check --config pyproject.toml .` reported 0 findings for every selected rule at `max-nested-blocks = 5`, and 13 `PLR1702` findings in 12 functions at 4, each "5 > 4". After the 12 changes it reports 0.
- `ruff check --show-settings` with lint preview only: `linter.preview = enabled`, `linter.explicit_preview_rules = true`, `linter.pylint.max_nested_blocks = 4`, `formatter.preview = disabled`. The command-line flag `--preview` sets `formatter.preview = enabled` too, so the setting stays under `[tool.ruff.lint]`.
- Generated functions, Ruff at 4 against the hook at `--max-depth 5`:

| Innermost statement inside | 4 blocks | 5 blocks |
| :--- | :--- | :--- |
| `if`, `for`, `while`, `with`, `except` | both pass | both fail |
| `try` bodies | both pass | Ruff fails, the hook passes |
| `match` cases | both pass | the hook fails, Ruff passes |

- Two gaps stay, as the issue says the pull request must state: Ruff does not count `match` blocks, and it does not count an `assert`, which the hook counted as a level although it opens no block. No function in `src` or `tests` breached the hook at 5 on the base, so no current code depends on either gap.

## Existing Tool Considered

Ruff `PLR1702`, which the project's Ruff already ships. The change builds nothing and deletes the hook, 88 lines of `core/code_metrics.py`, 268 lines of `tests/test_code_metrics.py`, the nesting leg of the whole-tree test, the scanner's nesting findings and option, and the spec verifier's indentation rule.
