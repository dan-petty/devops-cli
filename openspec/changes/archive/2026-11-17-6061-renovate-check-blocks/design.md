# Design

## Audit

Each Renovate pull request of `dan-petty-renovate[bot]` since 2026-11-16 20:00Z, with each failed step of every run attempt. The job `Require Passing Test Shards` fails when a shard fails, so it has no cause of its own and the table leaves it out.

| Pull request | Head commits | Failed step | Cause | Fixed by |
| --- | --- | --- | --- | --- |
| #6028 certifi (security) | `d34a6230d` | `Service Image Tests` shard 3, Run Test Suite in Service Image (attempt 1) | `test_sigterm_export` hung to 600 s: the child lost SIGTERM before `signal.pause()` | #6048 |
| #6029 container images (patch) | `7468d1945` (2 attempts), `08478d83b`, `1e1fa6917`, `ffa670d0b` | `Static Analysis`, row `k8s` | One gate case, `tests/gate/k8s_checks/devops_runtime.py:84`, compares the SearXNG pin with `SEARXNG_IMAGE` | #6069 |
| #6029 | same | `Tests & Coverage` shard 2 or 4 | `tests/invariants/test_k8s_searxng.py::test_the_engine_names_file_is_the_one_of_the_pinned_image` holds a fixture to the pin | #6069; SearXNG has its own branch behind approval (#6052) |
| #6046 helm charts (patch) | `6eaadc3a8`, `f5b215201` | `Tests & Coverage` shards 1 and 3 | Tests compare a chart version with a constant: `test_k8s.py::test_deploy_stack_installs_each_chart_at_the_version_that_its_application_pins`, `test_k8s_argocd_apps.py` (2), `test_k8s_manifests.py` (2), `test_k8s_local_path_placement.py`, `test_k8s_qdrant_security.py` | #6060 |
| #6046 | `f375783dc`, `76d8cbfc4` | `Semantic PR title`, Check that a Hidden Type Ships No Runtime Code | `chore(deps)` title, and a commit by hand changed `HELM_RELEASES_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py` | #6057 (chart prefix); #6060 (the table reads the manifest or drops the version) |
| #6047 python dependencies (patch) | `1fb492322` | `Static Analysis`, row `uv-check` | `ty` renamed `invalid-return-type` and `call-non-callable`, which `pyproject.toml` names | By hand: commit `99ab44b90` on the branch (step 3 of the re-run plan on #6061) |
| #6047 | `99ab44b90` | `Service Image Tests` shard 5 (attempts 1 and 2) | `test_sigterm_export` hang | #6048 |
| #6055 grafana 14.4.2 | `68d75a444`, `401a04b72` | `Tests & Coverage` shards 2 and 3 | The chart-version tests of #6046, and `test_k8s_monitoring_integration.py::test_grafana_runs_the_grafana_community_chart_that_ships_a_patched_grafana` | #6060 |
| #6056 ruff (patch) | `706214afd` | none | - | - |

The branches that the Dependency Dashboard (#6030) holds next show the failure mode that this change removes. Each one changes a file under `src/devops_cli/` and has the title `chore(deps)`, so the `Semantic PR title` check would refuse it:

| Branch | File under `src/devops_cli/` |
| --- | --- |
| `renovate/patch-uv` | `roadmap/runner_tools.py` (`UV_VERSION`) |
| `renovate/tools` (semgrep) | `tools_lock/semgrep.in`, `semgrep.txt`, `tools.lock` |
| `renovate/major-openspec` | `tools_lock/openspec/package.json`, `tools.lock` |
| `renovate/lock-file-maintenance` | the npm lockfiles of `tools_lock/` |
| `renovate/pip-compile-refresh` | the requirements files of `tools_lock/` |
| `renovate/minor-3.15-python-runtime` (approval) | `config/defaults.py`, `tools_lock/` |
| `renovate/major-node` (approval) | `roadmap/runner_tools.py` (`NODE_MAJOR`) |

## Decisions

- A package rule with `matchFileNames: ["src/devops_cli/**"]` sets `fix(deps):`. It is the path rule of `src/devops_cli/github/release_title.py`, which the title check runs, less the `.md` exception: Renovate reads no `.md` file there.
- The groups `uv`, `node`, `python runtime` and `bandit` set the prefix on their own rule, as #6057 did for `dcgm-exporter`. Renovate 44.239.1 builds a branch from the first update after a sort (`generate.js:230`), so a group with one update under `src/devops_cli/` and one outside can get either prefix. The groups `tools` and `openspec` hold only files under `src/devops_cli/`, so the path rule covers them.
- A rule with `matchUpdateTypes: ["lockFileMaintenance"]` sets the prefix of lock file maintenance. Its branch mixes `uv.lock` with the npm lockfiles of the tools lock, and the pip-compile refresh writes only files of the tools lock.
- `Service Image Tests` and the `k8s` row stay on for the Renovate App. The image test must see a base image or a Python update, and a security fix merges itself (#6031). The hang is fixed in the test (#6048), and the only `k8s` case that failed goes with #6069. The audit found no step that fails on a check that does not apply to its change, so no workflow trigger changes.

## Proof

- `npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json` prints `Config validated successfully against 2 file(s)`.
- A script outside the repository merges the defaults of Renovate 44.239.1, `.github/renovate/base.json` and `.github/renovate.json`, and runs Renovate's `applyPackageRules` on one update of each member of the affected groups. With `main`, each update outside the `Dockerfile` gets `chore(deps):`. With this change, each of them gets `fix(deps):`, and a `python dependencies`, a `ruff` and a `container images` update keep `chore(deps):`.

## Rejected alternatives

- Skip `service-image-build` and `service-image-test` for the Renovate App (the first refine design): a base image or a Python update is the change that the image test exists for, and the hang was a defect of one test.
- Add `k8s` to `--skip` for the Renovate App (the first refine design): the one failing case compares a pin with a constant, and #6069 removes it. The row also checks the manifests that an image update changes.
- `semanticCommitType: fix` per rule: Renovate uses it only when no `commitMessagePrefix` is set, and the shared preset sets one for every update.
- A test that reads `.github/renovate.json` and asserts the prefix: the owner rule of 2026-11-16 (#6060) puts no test on a configuration value. The validator and the dry evaluation above prove the change.
