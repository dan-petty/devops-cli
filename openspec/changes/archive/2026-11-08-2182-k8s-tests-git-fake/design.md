# Design

## Context

See `proposal.md` for motivation and background (#2182).
The five Kubernetes test modules started real git subprocesses.
Under the hermetic floor and ADR 0007 as amended by #2143, tests in `src/` must not start external programs.

## Decisions

### 1. `_Cluster` in `test_k8s.py` answers git and kustomize without subprocess execution

- **Decision**: Update `_Cluster.__call__` to intercept `git` and `kustomize` commands directly. When a git fetch is issued, record the target revision (`self.revision`). When `kustomize` is called, return canned ingress manifests corresponding to the requested revision (`pinned`, `release`, or `main`). Delete helpers `_git` and `_commit`.
- **Alternative considered**: Run real git in a temporary repository.
  - *Rejected*: Violates the rule against starting child processes and makes the tests slow.
- **Alternative considered**: Build a separate fake runner class for cluster tests.
  - *Rejected*: `_Cluster` already serves as the process double installed in `process_fake`.

### 2. `test_k8s_argocd_gate.py` reaches git through `GitFake`

- **Decision**: Configure `git_fake` in `tests/k8s/test_k8s_argocd_gate.py` to answer remote configuration and in-memory tarball archives for `git archive`. Provide a scripted handler for `kubectl kustomize` to parse and build manifests in memory. Delete helper `_git_run`.
- **Alternative considered**: Keep `_git_run` with real git.
  - *Rejected*: Violates hermetic testing standards and acceptance criteria.

### 3. `test_k8s_argocd_overrides.py` uses `git_fake` and guarded execution recording

- **Decision**: Migrate `test_an_application_renders_what_its_revision_holds` to create the test directory directly and verify execution without starting git processes. Use `git_fake` answers and `run_subprocess` for failure tests. Delete `_repo` and `_run`. Delete `test_the_fetch_of_an_ssh_remote_starts_ssh_without_a_prompt_through_the_guard` because `test_only_the_fetch_gets_the_ssh_option_and_every_command_gets_only_the_prompt_switch` verifies all command line options and environment variables deterministically.
- **Alternative considered**: Retain the SSH stand-in script test.
  - *Rejected*: The stand-in script requires real execution of both git and a shell script, which violates the zero-program invariant.

### 4. Delete `test_this_repository_passes_the_argocd_gate` from invariants

- **Decision**: Delete `test_this_repository_passes_the_argocd_gate` from `tests/invariants/test_k8s_argocd_apps.py`.
- **Alternative considered**: Keep the test in invariant test suite.
  - *Rejected*: The test invokes `check_argocd_gate(REPO_ROOT)`, starting git and running kubectl kustomize 23 times against committed repository manifests. Per #2164, checks on committed manifests belong to the `devops ci` gate rows (`tests/gate/k8s_checks/argocd_apps.py`).

### 5. `test_k8s_devops_runtime.py` filters uncommitted files in Python

- **Decision**: In `test_kustomization_lists_every_manifest_and_pins_no_image_and_stays_out_of_the_root`, replace `subprocess.run(["git", "ls-files", ...])` by excluding `configmap.yaml` directly from the directory glob.
- **Alternative considered**: Mock `subprocess.run`.
  - *Rejected*: The project prohibits patching `subprocess` in tests when pure logic suffices.
