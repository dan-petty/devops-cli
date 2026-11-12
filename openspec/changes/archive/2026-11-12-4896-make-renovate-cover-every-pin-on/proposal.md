# Proposal: #4896

## Why
Renovate opened 0 pull requests since 2026-10-01, and updates come only after a security finding or by hand (#4896, child 1 of #4893). Also, `.github/renovate.json` stops most updates when an instance runs: rules turn off pep621, pip_requirements, pip-compile, setup-cfg, npm, helm-values and helmv3, and the pre-commit manager is off by default. The config has no schedule, no groups, no limits for the CI cap and no security settings. `rebaseWhen: behind-base-branch` pushes each open update again after each merge, and each push starts about 25 jobs. Default titles can be longer than the 60 characters of the `Semantic PR title` check. Fail-to-Pass Check fails on each `fix(deps)` bump, because a bump has no test that fails on its base. Closes #4896.

## What Changes
- Add the shared preset `.github/renovate/base.json`. Each Service repository extends it with `github>dan-petty/devops-cli//.github/renovate/base`. It sets the Monday schedule (UTC), patch updates at any time, one group of non-major updates for each ecosystem, `prHourlyLimit` 2, `prConcurrentLimit` 8, `rebaseWhen: conflicted`, OSV and GitHub security alerts with the prefix `fix(deps):`, the Dependency Dashboard, lock file maintenance, Dashboard approval for runtime and data migrations, labels from `.github/labels.yml`, short titles and `platformCommit` with no `gitAuthor`.
- `.github/renovate.json` extends only the preset. It removes the rules that turned managers off, adds file patterns for helm-values and pip-compile, the OpenTofu registry, custom managers for the pins that no built-in manager reads, coupled groups for the pins that a test compares, `postUpgradeTasks` for OpenSpec and the devcontainer lockfile, and notes for the bumps that need a person or an agent.
- The uv headers of `semgrep.txt` and `bandit.txt`, and the bump step in `tools.lock`, give each option with `=` (`--python-version=3.14`, `--output-file=<name>.txt`). The pip-compile manager of Renovate refuses the earlier form, and uv writes the header as it is called.
- Fail-to-Pass Check skips a pull request of `devops-cli-renovate[bot]`.
- `release.yml` pins setup-uv to `0.13.6` in 3 places. Three action version comments name the real tag, and the attestation action moves to the commit of its tag `v4.2.2`.
- CONTRIBUTING.md, docs/SDLC.md, docs/DESIGN.md and k8s/README.md describe the schedule.
- The Renovate configuration and the Fail-to-Pass trigger are observable behavior, so the change has spec deltas for `release-concurrency-and-renovate`, `ci-fail-to-pass` and `grafana-plugins`.

## Capabilities
- `release-concurrency-and-renovate`: the labels requirement and the release age requirement change; schedule, security, manager coverage and title requirements are added.
- `ci-fail-to-pass`: the trigger requirement excludes the Renovate App.
- `grafana-plugins`: a plugin update gets the preset labels and `scope/infra` from the rule of the custom managers of `k8s/`.

## Impact
- Nothing changes on GitHub until the Renovate CronJob of #4893 child 4 (#4905) runs with the App of child 2 (#4897).
- #4902 adds the managers of the 20 binaries of the tools lock and the gh download, and joins them to the groups `trivy`, `argo`, `cloudflared` and `gh` that this change adds.
- #4905 must allow the `postUpgradeTasks` commands in `allowedCommands`, put the `devops install-tools` target directory on `PATH`, and set `RENOVATE_X_SUPPRESS_PRE_COMMIT_WARNING`, so that the pre-commit pull requests carry no upstream support note.
- The change fits one pull request.

## Feasibility
- `renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json` from `renovate@44.235.1` (the newest release on 2026-11-12) exits 0.
- The Renovate 44.235.1 source confirms each setting: `separateMinorPatch` gives a patch the branch `patch-<group>` and a title suffix `(patch)` (`workers/repository/updates/branch-name`, `generate`); `dependencyDashboardApproval` holds a whole branch when one update needs it, so `separateMultipleMinor` gives a new Python minor its own branch; `dependencyDashboard` is an object with `osvVulnerabilitySummary` and `reportAbandonment`; a custom regex manager compiles each match string with the flag `g` only; the `replace` template helper exists; the pre-commit manager is off by default; the alert default suffix is `[SECURITY]`, which would make a 69-character summary.
- The tags of the three action commits were read with `devops gh api`: `c3c9e263` is `v7.4.0`, `f87e5991` is `v4.4.1`, and `9d57eef8` is a commit on `main` one commit after `v4.2.2` (`4d101475`) that only bumps `actions/attest` in `action.yml`.
- A local run of Renovate 44.235.1 (`--platform=local --dry-run=lookup`) on a copy of the branch, with the preset merged in, extracted dependencies with every manager. It also showed that the pip-compile manager refused the earlier headers: `Option --python-version must have equal sign '=' separating it's argument`; uv 0.13 writes `--python-version=3.14` and `--output-file=<name>.txt` into the header when it is called so.
- `helm show values` of gitea 12.7.0 and dcgm-exporter 4.8.4 gave the image registry and repository that the values tags select.
- Scope from the plan: the gh download pair needs a sha256 per release, so #4902 adds its manager with the repin command. The `tools` group is in the repository config, because its path exists only in this repository.

## Existing Tool Considered
Renovate managers, presets, `customManagers`, `customDatasources` and `postUpgradeTasks` cover the need. The change adds no code under `src/`; it changes only the header lines of two generated requirements files and one comment of `tools.lock`. It deletes the rules that turned the pep621, pip, npm, helm-values and helmv3 managers off, and the Style Dictionary exception rule.
