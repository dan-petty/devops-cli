# Tasks

## 1. Choose the review executor from the runner profile

Kind: behavior. Reads: `src/devops_cli/ai/review/runner.py`, `src/devops_cli/security/tool_executor.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/config/settings.py`, `tests/ai/review/test_review_tool_sandbox.py`, `tests/ai/review/test_runner.py`, `tests/commands/test_review_adjudication.py`. Changes: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/commands/review.py`, `tests/ai/review/test_review_runner_executor.py` (new).
Adds: `review_tool_executor`

- [x] 1.1 `test_a_review_in_the_runner_pod_starts_its_scanners_with_DirectToolExecutor` and `test_a_review_outside_the_runner_pod_keeps_the_sandbox` in `tests/ai/review/test_review_runner_executor.py`
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_runner_executor.py` fails on the base
- [x] 1.2 Write the failing cases in `tests/ai/review/test_review_runner_executor.py` first: with the runner flag set and the process fake answering Bandit, Gitleaks and Semgrep, `execute_review_workflow` starts each scanner as a direct child of the review and the report holds their findings; with the default, each command starts bubblewrap, as `tests/ai/review/test_review_tool_sandbox.py` shows. Then add `review_tool_executor(*, in_runner: bool) -> ToolExecutor` to `src/devops_cli/security/tool_executor.py`, answering the direct executor for the pod of a runner Job and the sandbox executor otherwise, and correct the docstring of `src/devops_cli/security/tool_executor.py:class DirectToolExecutor`, which says that a review never runs its tools there. In `src/devops_cli/ai/review/runner.py`, give `execute_review_workflow` the keyword `in_runner: bool = False`, build its executor with `review_tool_executor(in_runner=in_runner)`, report a sandbox refusal only for the sandbox executor, and correct its docstring, which says that a review runs its tools in the sandbox and in no other place. In `src/devops_cli/commands/review.py`, pass the setting `roadmap.implement.in_runner` of the loaded settings at each of its five calls of `execute_review_workflow`
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_runner_executor.py` passes

## 2. Fail a runner review closed when a scanner is missing

Kind: behavior. Reads: `src/devops_cli/ai/review/runner.py`, `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/exceptions/ai.py`, `docs/ERRORS.md`, `tests/docs/test_exceptions.py`, `tests/ai/review/test_runner.py`, `tests/ai/agents/test_pydantic_ai_exceptions.py`. Changes: `src/devops_cli/ai/review/runner.py`, `src/devops_cli/exceptions/ai.py`, `docs/ERRORS.md`, `tests/ai/review/test_review_runner_executor.py`.
Adds: `ReviewScannerMissingError`

- [ ] 2.1 `test_a_review_in_the_runner_pod_that_lacks_a_scanner_lists_it_as_not_run_and_exits_nonzero` in `tests/ai/review/test_review_runner_executor.py`
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_runner_executor.py` fails on the base
- [ ] 2.2 Write the failing case in `tests/ai/review/test_review_runner_executor.py` first: with the runner flag set, a sample diff that holds a Python file and Gitleaks absent from PATH, the review keeps the findings of the scanners that ran, lists Gitleaks as not installed, and raises `ReviewScannerMissingError`. Then add `ReviewScannerMissingError` to `src/devops_cli/exceptions/ai.py` beside the other review errors, with error code `REVIEW_SCANNER_MISSING` and exit status 1. In `src/devops_cli/ai/review/runner.py`, in the runner profile and after the review has printed its report, build the file kinds with `src/devops_cli/ai/review/pipeline.py:def classify_scanner_files`, take the states with `src/devops_cli/ai/review/pipeline.py:def static_analyzer_states`, and raise the error naming each analyzer whose state is `src/devops_cli/ai/review/pipeline.py:927:ANALYZER_NOT_INSTALLED = "not installed"`. Regenerate `docs/ERRORS.md` in the same step, so the catalog holds the row of the new class
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_runner_executor.py` passes
- [ ] 2.3 Regenerate `docs/ERRORS.md` with `uv run devops docs generate`, so it holds the row of `ReviewScannerMissingError`
  - Verification: `$ uv run devops ci docs` passes

## 3. Hold the review scanners in the runner image

Kind: behavior. Reads: `src/devops_cli/roadmap/runner_tools.py`, `src/devops_cli/tools_lock/tools.lock`, `src/devops_cli/tools_lock/semgrep.txt`, `src/devops_cli/ai/review/pipeline.py`, `Dockerfile`, `tests/roadmap/test_roadmap_runner_tools.py`, `docs/CLUSTER.md`, `tests/invariants/test_runner_image.py`, `tests/invariants/test_runner_hooks.py`, `tests/roadmap/stage/test_roadmap_stage_context.py`, `tests/core/test_renovate_config.py`. Changes: `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`, `tests/roadmap/test_roadmap_runner_tools.py`, `docs/CLUSTER.md`.

- [ ] 3.1 `test_the_review_scanners_are_runner_tools_and_the_cluster_tools_stay_out` in `tests/roadmap/test_roadmap_runner_tools.py`, which asserts that Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep are entries of `RUNNER_TOOLS` at their lock versions, that none of the five is an entry of `NOT_IN_RUNNER`, and that `kubectl` and `kube-linter` stay in `NOT_IN_RUNNER`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` fails on the base
- [ ] 3.2 Write the failing case in `tests/roadmap/test_roadmap_runner_tools.py` first: the five scanners are entries of `RUNNER_TOOLS` at their lock versions and are absent from `NOT_IN_RUNNER`, while `kubectl` and `kube-linter` stay in `NOT_IN_RUNNER`; the case also fails when one of the 8 entries of `STATIC_ANALYZERS` of `src/devops_cli/ai/review/pipeline.py` is in neither table. Then move the five names in `src/devops_cli/roadmap/runner_tools.py` from `NOT_IN_RUNNER` to `RUNNER_TOOLS` as entries of the tools lock, each with the reason `job` and its `--version` check. Add one `devops install-tools --tool <name> --target-dir /opt/devops-tools/bin` line for each in the `runner-tools` stage of `Dockerfile`, beside the promtool and trivy lines. The step stops when a scanner has no lock entry or brings a fixed HIGH finding in the image scan, and adds no tool that #3562, #5394 or #3108 already adds
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` passes
- [ ] 3.3 Edit `docs/CLUSTER.md` to name Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep among the tools of the runner image, and to record that `kubectl` and `kube-linter` stay out through #3562 and #5394
  - Verification: `$ uv run devops ci docs` passes

## 4. Record the executor choice and check the built image

Kind: other. Reads: `docs/adr/0005-review-findings-come-from-tools-not-models.md`, `docs/adr/README.md`, `src/devops_cli/docs/adr_records.py`, `src/devops_cli/core/process_hardening.py`, `docs/CLUSTER.md`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0028-review-scanners-run-in-the-runner-pod.md` (new), `docs/adr/README.md`.

- [ ] 4.1 Write `docs/adr/0028-review-scanners-run-in-the-runner-pod.md` in the MADR 4 form that `docs/adr/README.md` and `docs/adr/0005-review-findings-come-from-tools-not-models.md` show: a front matter with `status: accepted`, `date`, `decision-makers: [owner]`, `issue: 3827` and `body-hash`; the decision is the direct executor in the pod of a runner Job; the considered options name the refused `unshare` that `src/devops_cli/core/process_hardening.py` records, the rootless container runtime and a second pod; the consequences name the five scanners, the pod as the isolation boundary and the image scan. Then run `uv run devops docs generate`, so the index between the markers of `docs/adr/README.md` holds the row of record 0028, because `tests/invariants/test_adr_records.py` compares that table with the records of `docs/adr/`. Then run the manual check below, which the image-scan requirement of the runner image makes binding, and run this check by hand: Run `uv run devops docs generate`, so the index of `docs/adr/README.md` holds the row of record 0028. Then run `uv run devops ci test tests/invariants/test_adr_records.py` and put the body hash it prints into the front matter of the record. Then, on a workstation with a container engine, run `docker build --target runner -t runner-review .`, then `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 runner-review`, then `docker run --rm -e DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools --entrypoint python runner-review -m devops_cli.roadmap.runner_tools`. Expect the index to hold the new row, the ADR test to pass, the build to pass its runner tool check, the scan to exit 0, and the tool check to exit 0. Stop when an added scanner brings a fixed HIGH finding and name that scanner in the pull request.
- [ ] 4.2 Write `docs/adr/0028-review-scanners-run-in-the-runner-pod.md` as an accepted MADR record that names the direct executor, the `unshare` that the pod's RuntimeDefault seccomp profile refuses, and the pod as the isolation boundary, and regenerate the index of `docs/adr/README.md` with `uv run devops docs generate`, so the table holds the row of the new record
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: in the runner profile, `devops review` runs on a sample diff and returns findings.
- Group 2: A test: with a scanner missing, the review reports the tool as not run and does not return a clean result.
- Group 4: The image scan and the gate tests pass with the added tools (the reason for `NOT_IN_RUNNER`).
- Group 3: The change cites #3562 and #3108 for the tool set and adds nothing they already add.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
