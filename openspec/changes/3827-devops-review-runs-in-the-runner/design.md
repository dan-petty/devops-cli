# Design

## Decisions

- **A review in the pod of a runner Job starts its scanners with the existing direct executor, the class at `src/devops_cli/security/tool_executor.py:666:class DirectToolExecutor:`.**: It needs no user namespace, and the runner pod is the isolation boundary: no Kubernetes token, none of the job variables in the step shell, and the job process is not dumpable.
- **The review chooses its executor from the setting `roadmap.implement.in_runner`, which the command layer passes as `in_runner`.**: Only the pod of a runner Job sets that setting, so a workstation and the Service pod keep the sandbox with no new option and no host guess.
- **A missing scanner is the state `src/devops_cli/ai/review/pipeline.py:927:ANALYZER_NOT_INSTALLED = "not installed"` of the review's own analyzer table, and not a PATH probe over every entry of `STATIC_ANALYZERS`.**: `src/devops_cli/ai/review/pipeline.py:986:states[name] = ANALYZER_NO_FILES` for an analyzer whose kind has no file in the diff, so a Python sample diff does not fail closed for Kube-linter, which #3562 and #5394 own and the image leaves out.
- **A missing scanner fails the review after the scanners that ran, and not before the review starts.**: The findings of the scanners that ran stay in the report, and the exit code still says that the review is not clean.
- **The fail-closed rule applies only to a review in the pod of a runner Job.**: The image is the contract there: a scanner that the image lacks is a broken image. A workstation may lack a scanner, and its review stays advisory.
- **The new error class goes in `src/devops_cli/exceptions/ai.py` beside the other review errors, and `docs/ERRORS.md` is regenerated in the same group.**: `docs/ERRORS.md` is the generated catalog of the CLI's error classes, and the docs check refuses a catalog that is not the output of its generator.
- **The change adds Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep, and leaves Kube-linter out.**: #3562 and its split #5394 own Kube-linter, and #3108 already returned actionlint, shellcheck and Trivy; the fourth acceptance criterion forbids adding a tool that either item adds.
- **The executor choice is recorded in `docs/adr/0028-review-scanners-run-in-the-runner-pod.md` rather than as an amendment of ADR 0005.**: The runner exception is specific to the pod, and an amendment of the tool-anchored review ADR would hide it from a reader.
- **The group that writes the new ADR also regenerates the index of `docs/adr/README.md` with `uv run devops docs generate`.**: `src/devops_cli/docs/generator.py:1328:synced = sync_index(` writes that table, and `tests/invariants/test_adr_records.py:25:assert sync_index(page, read_record_texts(ADR_DIRECTORY)) == page` fails on a record whose row the table lacks, so the ADR and its index row land in one step.

## Rejected alternatives

- **Keep `bubblewrap` for a review in the runner pod.**: `src/devops_cli/core/process_hardening.py:19:seccomp profile refuses. So the job guarantees an` states that the pod's RuntimeDefault seccomp profile refuses the unshare that a sandbox for the shell needs.
- **Run a rootless container runtime or a second pod as the sandbox of the scanners.**: `docker` is an entry of `NOT_IN_RUNNER` with the reason "No check, hook, test or job of the gate runs it. The Job has no cluster token and no container engine.", so the runner pod can start neither a container runtime nor a second pod.
- **Move every `NOT_IN_RUNNER` program into the image.**: `NOT_IN_RUNNER` holds `kubectl`, `kustomize`, `helm`, `argo` and the rest with the reason that no check, hook, test or job of the gate runs them, and #3562 with #5394 owns `kubectl` and `kube-linter`; the pod has no cluster token.
- **Add gVisor, which the alternatives check of the issue named.**: The alternatives block of the issue records its rejection by ADR 0018, and the change reuses the existing executor, so it needs no new sandbox.
- **Report a missing scanner as a coverage gap and keep exit 0, as the review does on a workstation today.**: `src/devops_cli/ai/review/pipeline.py:1193:lines.append(f" [yellow]! Not installed, so not run: {', '.join(missing)}[/yellow]")` reports a missing scanner as a warning with no failed status, so it reads as no finding; the second acceptance criterion refuses that result in the runner.
- **Leave the index of `docs/adr/README.md` to a later docs run.**: `tests/invariants/test_adr_records.py:25:assert sync_index(page, read_record_texts(ADR_DIRECTORY)) == page` compares the whole README with the generated table, so a new record without its row fails the test and the `docs` gate row in the same pull request.

## Unchanged references

- `tests/ai/review/test_review_tool_sandbox.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_runner.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_review_path.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_review_path_routing.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_review_symbol_delta.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_review_console_report.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/ai/review/test_review_history.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
- `tests/review/test_review_group_analysis.py` (call site): It calls `execute_review_workflow`; the default keeps the sandbox, so its cases still hold.
