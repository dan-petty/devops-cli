# Tasks

## 1. The k8s row refuses a change to an environment path

Kind: behavior. Reads: `docs/HOMELAB_REPO_SWITCH.md`, `tests/gate/runner.py`, `tests/gate/configured_domain.py`, `tests/invariants/test_configured_domain_check.py`. Changes: `tests/gate/k8s_checks/environment_freeze.py`, `tests/gate/k8s.py`, `tests/invariants/test_environment_freeze_check.py`.
Adds: `is_environment_path`, `outcome`, `check_the_branch_changes_no_environment_path`

- [x] 1.1 Write the failing tests in `tests/invariants/test_environment_freeze_check.py`. `is_environment_path` is true for `k8s/llm/valkey.yaml`, `k8s/catalog.toml`, `k8s/monitoring/dashboards/coredns.json` and the new file `k8s/new-app/deployment.yaml`, and false for `k8s/devops/kustomization.yaml`, `k8s/overlays/homelab/devops/kustomization.yaml`, `k8s/README.md`, `k8s/llm/profiles/README.md`, `src/devops_cli/cli.py`, `docs/CLUSTER.md` and `k8sx/a.yaml`. `outcome` takes a `subprocess.CompletedProcess` of the git command: a diff that holds `k8s/llm/valkey.yaml` and `docs/a.md` fails with one finding that names `k8s/llm/valkey.yaml` and a last line that names `dan-petty/homelab`; a diff of the move from `k8s/llm/valkey.yaml` to `k8s/devops/valkey.yaml` fails with one finding that names `k8s/llm/valkey.yaml`; a diff of `k8s/devops/a.yaml`, `k8s/README.md` and `src/a.py` passes and names the count of changed paths; an empty diff passes; a git exit status of 128 fails and names the status, the error of git and `origin/main`
  - Verification: `$ uv run devops ci test tests/invariants/test_environment_freeze_check.py` fails at collection, because the module does not exist
- [x] 1.2 Add `tests/gate/k8s_checks/environment_freeze.py` with `is_environment_path`, `outcome` and the check `check_the_branch_changes_no_environment_path`, which runs `git diff --name-only --no-renames -z origin/main...HEAD` in the checkout with a timeout and asserts that `outcome` gives 0. Change the docstring of `tests/gate/k8s.py`, so that it names the check that reads git
  - Verification: `$ uv run devops ci test tests/invariants/test_environment_freeze_check.py` passes
- [x] 1.3 Run the row on the branch, which changes `k8s/README.md` only under `k8s`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Renovate updates no environment path

Kind: other. Reads: `.github/renovate.json`, the preset `renovate/base.json` of dan-petty/infra. Changes: `.github/renovate.json`.

- [x] 2.1 Add the package rule with `matchFileNames` `k8s/**`, `!k8s/devops/**` and `!k8s/overlays/homelab/devops/**` and `enabled: false` to `.github/renovate.json`, with a description that names step 12 and step 17 of `docs/HOMELAB_REPO_SWITCH.md`
  - Verification: `$ npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict --no-global .github/renovate.json` exits 0
- [x] 2.2 Check the patterns with the matcher of Renovate 44.239.2: import `matchRegexOrGlobList` from `dist/util/string-match.js` of the package in Node, and give it the patterns of the rule with `k8s/llm/valkey.yaml`, `k8s/argocd/apps/argocd.yaml`, `k8s/devops/renovate/cronjob.yaml`, `k8s/overlays/homelab/devops/kustomization.yaml` and `Dockerfile`. Only the first two match

## 3. Documents

Kind: other. Reads: `docs/HOMELAB_REPO_SWITCH.md`, `k8s/README.md`, `docs/CLUSTER.md`, `docs/TESTING.md`, `docs/SDLC.md`. Changes: the same files.

- [x] 3.1 In `k8s/README.md`, change the introduction and the GitOps section: Argo CD reads the environment from dan-petty/homelab and the product base from this repository, and the `k8s` row refuses a change to an environment path. Bootstrap & Adoption and Recovery take the bootstrap file and the values of Argo CD from a homelab checkout of `main`, and Recovery takes the chart version from Application `argocd` of that checkout
- [x] 3.2 In `docs/CLUSTER.md`, say in the introduction which repository Argo CD reads each part from, and that the values of Image Updater are in the homelab copy
- [x] 3.3 In `docs/HOMELAB_REPO_SWITCH.md`, step 12 names the check, its module, the Markdown exception and the Renovate rule. Step 17 deletes the check, its test and the Renovate rule with the environment files
- [x] 3.4 In `docs/TESTING.md`, the `k8s` row also holds the freeze check, and the layout list names `test_environment_freeze_check.py`. In `docs/SDLC.md`, the Renovate paragraph names the rule
  - Verification: `$ uv run devops ci --check --only docs,openspec` passes
