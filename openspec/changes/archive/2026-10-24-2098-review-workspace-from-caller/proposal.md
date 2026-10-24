# Proposal

## Why

Issue #2098, part 2 of the tracker #772: the review orchestrator and the scanners found the reviewed workspace from the working directory of the process, not from their caller. So a test could not give them a temporary workspace, and a review of a path changed with the directory that the command started in. On b26caf93, `git grep -n "Path.cwd()" -- src/devops_cli/ai/review/ src/devops_cli/security/` found 11 reads in code and one in a docstring. The scope that #1978 added: the review tests that build an orchestrator with no executor get the executor fake through the constructor, so the root conftest no longer wraps `DirectToolExecutor.run` for the canaries (`pin_review_tool_canaries`).

## What Changes

- The command layer reads the working directory one time and gives it down. `devops review path` and `devops review branch` read it once and resolve each target and the repository from it. The PR review helper reads it once. `devops review export-feedback` gives it as `workspace_root`, and `devops k8s audit` gives it to Popeye as `workdir`.
- The orchestrator takes its workspace through its constructor alone: `target_dir`, the absolute path of the reviewed directory, and `tool_executor`. `run_pre_analysis_refresh` and `init_per_file_payloads` take no `target_dir`, and the runner passes none. The session directory check allows the reviews directory and the temporary directory, and no longer the working directory. The summary of `devops review path --summary` reads the analysis of the reviewed repository.
- The review boundary (`_is_allowed_review_boundary`) and the allowed roots of the feedback export keep their rule. The working directory in them is the one that the command gives.
- Each scanner takes its directory from its caller. Kube-linter names a manifest relative to the working tree that holds the manifest. `run_mypy_scan` and `run_osv_scan` require `tree`. `run_popeye_scan` requires `workdir`. `relativize_scan_path` requires its root, and a path outside it stays as it is. A scan that is not isolated starts in the nearest directory that holds its targets, and a scan with no target starts in the temporary directory.
- The ast-grep rule `review-cwd-read` fails a read of `Path.cwd()` or `os.getcwd()` in `src/devops_cli/ai/review/`, `src/devops_cli/review/` and `src/devops_cli/security/`. The `constructs` row of `devops ci` and the `ast-grep-scan` commit hook run it.
- `ScannerFake` answers the canary run of each review tool with the recorded canary output, as the executor that a test gives and through the `scanner_fake` fixture. The root conftest drops `pin_review_tool_canaries`. Each review test that reached a canary through `DirectToolExecutor`, 41 tests in 14 files, gets the fake: through the constructor of the orchestrator, or through `scanner_fake` for a review that a command starts.
- `tests/test_review_pipeline.py::test_review_pipeline_stages`, `tests/test_review_repos.py::TestReviewReposSubdirectories::test_review_path_summary_in_repos_directory` and `tests/test_review_security_tools.py::test_pipeline_multi_scanner_aggregation` use a temporary workspace and fakes, and patch no devops-cli name.
- ARCHITECTURE.md (section 7.4) and docs/TESTING.md describe the rule and the fake.

A Kube-linter finding of a review that runs outside the reviewed checkout changes: it names the manifest by its path in the checkout, not by its file name alone. So the change carries the spec delta `review-workspace`. Every other change keeps the behavior of the commands.

The change fits one pull request.

## Capabilities

### New Capabilities

- `review-workspace`: a review and its scanners take their workspace from the command.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`, `runner.py`, `exporter.py`: the workspace through the constructor, the boundary and the export roots from the command.
- `src/devops_cli/security/base.py`, `kubelinter.py`, `mypy.py`, `osv_scanner.py`, `popeye.py`: the directories from the caller.
- `src/devops_cli/commands/review.py`, `src/devops_cli/commands/k8s/security_audit.py`: the one read of the working directory.
- `.ast-grep/rules/review-cwd-read.yml` and its rule tests, `tests/test_architectural_invariants.py`, `tests/test_net_construct_rules.py`, `.pre-commit-config.yaml` and `src/devops_cli/lang/en/messages.py`: the rule and the name of the `constructs` row.
- `tests/support/fakes/scanners.py`, `tests/conftest.py` and the review tests: the canary answers in the fake.

## Feasibility

I confirmed the premise against the code at b26caf93:

- `git grep -n "Path.cwd()\|os.getcwd()" -- src/devops_cli/ai/review/ src/devops_cli/security/` found 12 lines: 11 reads in `exporter.py` (2), `pipeline.py` (1), `runner.py` (2), `base.py` (2), `kubelinter.py`, `mypy.py`, `osv_scanner.py` and `popeye.py` (1 each), and the docstring of `relativize_scan_path`. The new rule reported the same 11 reads (`uv run ast-grep scan src tests`), and it reports none after the change.
- The orchestrator already took `target_dir` in its constructor, but `run_pre_analysis_refresh` and `init_per_file_payloads` set it again. Every listing, reading, sibling and manifest lookup of the orchestrator derives from `target_dir`. docs/TESTING.md makes the filesystem under `tmp_path` real, so the workspace is a directory and no file-system seam.
- Kube-linter named a manifest relative to the checkout of the working directory. The new aggregation test, run over the source of b26caf93, lost the Kube-linter finding of `k8s/app.yaml`: the location was `app.yaml:Deployment/app`, outside the payload of the manifest. `tests/test_secops.py::test_a_kubelinter_finding_names_the_manifest_in_its_own_checkout_from_any_directory` failed the same way.
- With the canary helper of the root conftest instrumented, a full test run (10491 passed) showed 41 tests in 14 files that reached a canary through `DirectToolExecutor`, not the 34 files that the comment of #1978 estimated. Without the helper, 27 of them failed: the floor refused the real Bandit or Semgrep of the canary. With the fake, all 41 pass.
- The three named tests took 0.37 s, 0.15 s and 0.27 s (setup and call, `uv run pytest --durations=0 -n0`) on b26caf93, and take 0.25 s, 0.12 s and 0.18 s after the change. Each is far under 5 s.

## Existing Tool Considered

ast-grep (`ast-grep-cli`, already pinned and run by the `constructs` row) holds the rule. It needs no new checker: the rule is one YAML file with its rule tests. `ToolExecutorFake` and `ScannerFake` are the shared fakes of the review-tool edge (ADR 0007), and this change adds no other fake. It deletes `pin_review_tool_canaries`, `_recorded_canary_answers` and `_load_recorded_canary_outputs` from the root conftest, the second `target_dir` of two orchestrator stages and of two runner functions, the working directory as an allowed root of the session directory, and the fallbacks of the scanners to the working directory.
