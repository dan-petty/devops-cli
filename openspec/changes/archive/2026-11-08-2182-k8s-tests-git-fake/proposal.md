# Proposal

## Why

Issue #2182 migrates five Kubernetes and Argo CD test modules to the git fake delivered in #2146.
The owner's rule of 2026-10-24 states that a test of `src/` starts no program.
The test suite audit of 2026-10-24 recorded that tests in these five modules started a real `git` process:

- `tests/commands/k8s/test_k8s.py`: 21 tests started git.
- `tests/k8s/test_k8s_argocd_gate.py`: 9 tests started git.
- `tests/k8s/test_k8s_argocd_overrides.py`: 5 tests started git.
- `tests/invariants/test_k8s_argocd_apps.py`: 2 tests started git.
- `tests/config/test_k8s_devops_runtime.py`: 1 test started git.

The tests used four helper functions that started real git subprocesses: `_git` and `_commit` in `test_k8s.py`, `_git_run` in `test_k8s_argocd_gate.py`, and `_repo` in `test_k8s_argocd_overrides.py`.
Starting real git slowed down test execution and violated the hermetic test floor.

## What Changes

- `tests/commands/k8s/test_k8s.py`:
  - Delete helpers `_git` and `_commit`.
  - Update `applications_repo` fixture to create directories without executing git subprocesses.
  - Update `_Cluster` process stand-in to answer git and kustomize commands directly from memory, stopping real subprocess execution.
  - Update `test_deploy_stack_refuses_a_revision_with_no_placeholder_host_rather_than_clear_staged_hosts` to use the revision response of `_Cluster` without starting git.

- `tests/k8s/test_k8s_argocd_gate.py`:
  - Delete helper `_git_run`.
  - Use `git_fake` to answer git remote configuration and in-memory git archive tarballs without starting git processes.
  - Migrate `test_a_file_in_working_tree_but_not_in_commit_does_not_reach_the_build` to use `git_fake` with an in-memory tarball archive representing committed tree state.
  - Answer `kubectl kustomize` through `git_fake` so no external kubectl starts.

- `tests/k8s/test_k8s_argocd_overrides.py`:
  - Delete helpers `_repo` and `_run`.
  - Migrate `test_an_application_renders_what_its_revision_holds` to use direct filesystem fixture and guarded runner inspection.
  - Migrate `test_a_revision_or_repository_from_the_cluster_is_never_read_as_a_git_option` and `test_a_revision_that_cannot_render_is_refused` to use `git_fake` answers and `run_subprocess`.
  - Delete redundant test `test_the_fetch_of_an_ssh_remote_starts_ssh_without_a_prompt_through_the_guard`. The adjacent test `test_only_the_fetch_gets_the_ssh_option_and_every_command_gets_only_the_prompt_switch` already checks the exact SSH options and prompt flags without starting an SSH child process.

- `tests/invariants/test_k8s_argocd_apps.py`:
  - Delete test `test_this_repository_passes_the_argocd_gate`. Checks of committed repository files belong to dedicated `devops ci` rows (#2164, `tests/gate/k8s_checks/argocd_apps.py`).
  - Migrate `test_cluster_app_of_apps_ignores_pre_and_post_delete_finalizers_jq` to evaluate the finalizer regex in Python, starting no `jq` process.

- `tests/config/test_k8s_devops_runtime.py`:
  - Remove `subprocess.run` calling `git ls-files` in `test_kustomization_lists_every_manifest_and_pins_no_image_and_stays_out_of_the_root`. Filter `configmap.yaml` directly in Python.
  - Remove unused `subprocess` import.

- `tests/support/git_scenarios.py`:
  - Add scenarios `argocd_gate_archive` and `argocd_application_render`.
  - Record scenario transcripts into `tests/fixtures/git/`.

## Impact

- Files modified:
  - `tests/commands/k8s/test_k8s.py`
  - `tests/k8s/test_k8s_argocd_gate.py`
  - `tests/k8s/test_k8s_argocd_overrides.py`
  - `tests/invariants/test_k8s_argocd_apps.py`
  - `tests/config/test_k8s_devops_runtime.py`
- Files added:
  - `openspec/changes/2182-k8s-tests-git-fake/`

## Feasibility

- Premise confirmed against the live repository at commit `c8990bed`.
- Before migration, running all five files with `uv run pytest tests/commands/k8s/test_k8s.py tests/k8s/test_k8s_argocd_gate.py tests/k8s/test_k8s_argocd_overrides.py tests/invariants/test_k8s_argocd_apps.py tests/config/test_k8s_devops_runtime.py -n 0 --durations=0` took 9.05 seconds across 173 tests.
- Searching for the four helpers before migration confirms:
  - `_git_run` occurs in `tests/k8s/test_k8s_argocd_gate.py`
  - `_git` and `_commit` occur in `tests/commands/k8s/test_k8s.py`
  - `_repo` occurs in `tests/k8s/test_k8s_argocd_overrides.py`
- The `git` verification row (`uv run python -c "import sys; from tests.support.git_recording import main; sys.exit(main(['--check']))"`) currently passes with 19 committed scenarios.

## Existing Tool Considered

The project provides `GitFake` in `tests/support/fakes/git.py` behind the `git_fake` fixture (#2146).
This change builds no new double or library. It adds recorded git scenarios and migrates test files to the existing fake.
