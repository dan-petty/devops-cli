# Task: Automated release cutting diagnoses ruleset refusals and raises typed errors (#1280)

**Issue**: [#1280](https://github.com/dan-petty/devops-cli/issues/1280)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/release, scope/roadmap

## Description
When all deliverables in an active release milestone were delivered and closed, `roadmap-service` scheduled a release cut via `cut_release`. However, when pushing the cut branch to origin, the push was refused by GitHub branch ruleset 23059172 (`GH013: Repository rule violations found for refs/heads/release/vX.Y.Z`). `cut_release` printed the failure and raised `typer.Exit(1)`, causing background service jobs in Loki to fail with an uninformative `typer.exceptions.Exit: 1` rather than structured diagnostics.

Per the owner decision on 2026-10-08, direct pushes to `release/vX.Y.Z` are retained, with the machine account configured to bypass ruleset 23059172 (Write role, mode Always). The code changes implement fail-closed typed error reporting across the entire release cutting sequence:
1. Every failure mode in `cut_release` raises a typed `DevOpsCLIError` subclass naming its cause:
   - `ReleaseWorkingTreeDirtyError` when the working tree has uncommitted changes.
   - `ReleaseRemoteFetchError` when fetching the remote release branch tip fails.
   - `ReleaseBranchMissingError` when `git rev-parse` fails to verify the tracking ref.
   - `ReleasePushError` when pushing the cut branch or tag fails.
   - `ReleasePushRefusedError` when git push is refused by a repository ruleset (`GH013`).
   - `ReleasePRCreationError` when `gh pr create` fails.
2. When git push fails due to ruleset refusal (`GH013`), `_raise_remote_git_failure` diagnoses the failure, naming the ruleset refusal and the required bypass entry (Write role on ruleset 23059172 under Settings → Rules → Rulesets).
3. The release Typer application is configured with `exit_on=DevOpsCLIError`, allowing CLI invocations to format error messages safely without unhandled tracebacks while programmatic callers (`roadmap-service`, `devops roadmap close`) receive typed exceptions.
4. Documentation across `HELP.roadmap.close`, `RELEASE_CYCLE.md`, `k8s/README.md`, and `changelog.d/1124.md` has been aligned with the ruleset bypass architecture.

## Acceptance Criteria
- [x] Every failure mode in `cut_release` raises a typed `DevOpsCLIError` subclass naming its cause: dirty working tree (`ReleaseWorkingTreeDirtyError`), remote fetch failure (`ReleaseRemoteFetchError`), missing tracking ref (`ReleaseBranchMissingError`), ruleset push refusal (`ReleasePushRefusedError`), general push failure (`ReleasePushError`), and PR creation failure (`ReleasePRCreationError`).
- [x] Push refused by repository ruleset (`GH013`) raises `ReleasePushRefusedError` and diagnoses the refusal, naming the Write role bypass requirement on ruleset 23059172 in Settings → Rules → Rulesets.
- [x] Documentation in sync: `HELP.roadmap.close` and generated reference docs, `RELEASE_CYCLE.md`, `k8s/README.md`, and `changelog.d/1124.md` updated with the ruleset bypass architecture.
- [x] Offline tests with real git pre-receive hook simulating `GH013` ruleset refusal verify the typed error, message diagnostics, and timeout boundaries (< 1 s per call phase).
- [x] All 14 checks in `uv run devops ci` pass with 100% success.
- Pending a person: In Settings → Rules → Rulesets, open ruleset 23059172 covering `release*` and add a bypass entry for the repository role the machine account holds (**Write**), mode **Always**. Verify that the next automated cut pushes `release/vX.Y.Z` without ruleset refusal.

## Decisions and Deviations
- **Ruleset bypass instead of `chore/prepare-vX.Y.Z` preparation PR**: The owner confirmed on 2026-10-08 that automatic cuts continue pushing version bumps and `docs/ROADMAP.md` directly to `release/vX.Y.Z` under an authorized bypass list entry, keeping the single release PR into `main` without extra intermediate PR choreography.
- **Unified `exit_on=DevOpsCLIError` on `release` Typer app**: CLI invocations cleanly report exception messages via `exit_on_error` and exit 1, while service callers catch typed exceptions to capture structured Loki error logs.

## Deliverables
- [x] `src/devops_cli/exceptions/git.py`: Added `ReleaseWorkingTreeDirtyError`, `ReleaseRemoteFetchError`, `ReleaseBranchMissingError`, `ReleasePushError`, `ReleasePushRefusedError`, and `ReleasePRCreationError`.
- [x] `src/devops_cli/exceptions/__init__.py`: Re-exported the new release exception classes.
- [x] `src/devops_cli/lang/en/messages.py`: Added `push_refused_ruleset` message to `ReleaseMessages`.
- [x] `src/devops_cli/lang/en/help.py`: Updated `HELP.roadmap.close` with ruleset bypass requirement.
- [x] `src/devops_cli/commands/release.py`: Refactored `_verify_clean_tree`, `_run_remote_git_or_exit`, `_fetch_remote_release_tip`, `_checkout_cut_branch`, `_commit_and_push_cut_branch`, and `_execute_release_pr` to raise typed exceptions, and set `exit_on=DevOpsCLIError` on `app`.
- [x] `RELEASE_CYCLE.md` & `k8s/README.md`: Documented `roadmap-service` automated cut ruleset bypass requirements.
- [x] `changelog.d/1124.md`: Updated note to reference #1280 resolution.
- [x] `changelog.d/1280.md`: Recorded release cut error typing and ruleset refusal diagnostics.
- [x] `tests/test_release.py`: Added offline tests for all typed release failure modes and `GH013` ruleset refusal.
