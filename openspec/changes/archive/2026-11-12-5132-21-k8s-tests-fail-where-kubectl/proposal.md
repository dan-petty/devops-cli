# Proposal: #5132

## Why
The roadmap implement job for #1878 stopped because `uv run devops ci test` failed 21 tests with `FileNotFoundError: 'kubectl'` on the base commit. The runner image holds no kubectl on purpose (`NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py`, #3562). The cause is in the tests: ADR 0007 and `docs/TESTING.md` say that a test starts no program and that the lookup of a program on PATH is part of its fake, but the hermetic floor still let every test start `kubectl kustomize` and `kubectl patch --local`. A test that needed the real binary thus passed in the devcontainer and on the GitHub runner and failed only in the runner image. Closes #5132.

## What Changes
- `tests/conftest.py`: the floor refuses every start of kubectl, its offline renderers included, as ADR 0007 decided. A test that starts a real kubectl now fails on each host, so the defect cannot come back unseen.
- `tests/invariants/test_hermetic_floor.py`: a new floor test proves that the floor refuses `kubectl kustomize` and `kubectl patch --local`.
- `tests/k8s/test_image_pins.py` (9 tests): `kubectl kustomize` answers from the files of the test tree and from the committed chart render, in place of the real binary.
- `tests/k8s/test_k8s_argocd_gate.py` (10 tests): the fake of kubectl also answers its lookup on PATH, so the gate finds kubectl on a host that holds none.
- `tests/commands/k8s/test_k8s.py`: the deploy-stack test checks that the host patch is a JSON merge patch that names `kustomize.patches` alone, with no real `kubectl patch --local`.
- The Qdrant Secret test of `tests/commands/k8s/test_k8s_rag_ingest_manifests.py` renders committed manifests, so it moves to the `k8s` row of `devops ci` as `tests/gate/k8s_checks/rag_ingest.py`.
- Two docstrings that named the old allowance (`tests/support/fakes/openspec.py`, `tests/tools_lock/test_k8s_argo_workflows.py`) now name the refusal.
- The change touches only tests and the gate checks under `tests/`. No devops command, option, message, manifest or Service behavior changes, so it has no spec delta and sets `skip_specs: true`.

## Capabilities
None. The change keeps all behavior that a consumer observes.

## Impact
- Files: `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`, `tests/k8s/test_image_pins.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`, `tests/gate/k8s_checks/rag_ingest.py`, `tests/support/fakes/openspec.py`, `tests/tools_lock/test_k8s_argo_workflows.py`.
- The test suite passes with or without kubectl on PATH, so the implement runner can run `devops ci test`.
- The `k8s` row of `devops ci` holds one more check. It reads the render of `k8s/devops` that the row already makes.
- No new dependency. No change to a check name. The change fits one pull request.

## Feasibility
- Census with kubectl hidden: a directory with a symbolic link to each program of `/usr/local/bin` except kubectl took the place of `/usr/local/bin` in PATH, with no host change. `pytest -n 8 tests` on `origin/main` gave `24 failed, 23949 passed, 2 skipped`: the 21 tests above, and 3 tests (`review_window` of `tests/core/test_git_contract.py`, `test_review_facts`) that fail with kubectl on PATH too (#4865).
- Census of real kubectl starts with kubectl on PATH: a probe floor that logged each allowed `kubectl kustomize` or `kubectl patch --local` start gave 11 tests: the 9 image-pin tests, the deploy-stack test and the Qdrant Secret test. The 10 gate tests already faked `kubectl kustomize` and failed only on `shutil.which("kubectl")` in `src/devops_cli/k8s/argocd_gate.py`. No other test starts a real kubectl, so the refusal fails no test once these change.
- `.github/workflows/image-pins.yml` runs `uv run devops k8s image-pins` with the real kubectl and helm over the committed Applications, so the real normalization of the chart output stays checked.
- deploy-stack sends `--type merge` (`src/devops_cli/commands/k8s/stack_lifecycle.py`). RFC 7386 section 2: a merge patch changes only the members it names and merges an object into the object at its place.

## Existing Tool Considered
- pytest's own `monkeypatch` and the project's `ProcessFake` and `GitFake` fakes cover the process edge and the lookup on PATH. No new tool.
- A JSON merge patch library (for example `json-merge-patch`) could apply the patch in the deploy-stack test. It is not a dependency, and the check of the patch shape proves the same fact with RFC 7386, so the change adds no library and no hand-written merge.
- Deleted internal code: `_is_allowed_kubectl_renderer` of `tests/conftest.py`, `_real_kustomize` of `tests/k8s/test_image_pins.py`, and `_rendered_devops_manifests` and `_extract_secret_refs` of `tests/commands/k8s/test_k8s_rag_ingest_manifests.py`.
