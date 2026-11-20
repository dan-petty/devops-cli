# Tasks

## 1. Tool jobs take the tools of the devtools image

Kind: other. Reads: `.github/workflows/ci.yml`, `.github/workflows/copilot-setup-steps.yml`, `.github/workflows/image-pins.yml`, `.github/workflows/rule-pack.yml`, `.github/workflows/service-image-test.yml`, `.github/actions/devcontainer-image/action.yml`, `.github/actions/setup-toolchain/action.yml`. Changes: `.devcontainer/Dockerfile`, `.github/actions/devtools-commands/action.yml`, the five workflows, `tests/invariants/test_workflow_contracts.py`, `tests/commands/test_ci.py`, `tests/roadmap/test_roadmap_runner_tools.py`, `tests/gate/tree_checks/config_reads.toml`.

- [x] 1.1 Add the stage `devtools-bin` to `.devcontainer/Dockerfile` with the nine commands of the host jobs, and the composite action `.github/actions/devtools-commands`. The action restores `$RUNNER_TEMP/devtools-bin` with `actions/cache` under a key of the runner, the digest of the `FROM` line and the sorted commands, builds the stage and moves the named commands there only on a miss, and puts the directory first on `PATH`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Run `rule-pack` in the devtools image with the tag and the digest of the Dockerfiles, and delete its `install-tools` lines
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Call the action from `Static Analysis`, the test shards, `Copilot Setup Steps`, `Image Pins` and `Service Image Tests` in place of their `install-tools` lines, and add `.devcontainer/Dockerfile` and the action folder to the `paths` of `copilot-setup-steps.yml`, `image-pins.yml` and `service-image-test.yml`. Remove the four tool lines from the copilot run lines of the workflow contract test, delete the trivy step order test and the allowlist entries of the three removed steps of `ci.yml`, lower the count of `tests/commands/test_ci.py` in `config_reads.toml`, and let the runner tools test read the `commands` of the action as tools of the required jobs
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.4 Confirm that no workflow installs a tool of the devtools image with `devops install-tools`
  - Verification: `$ ! git grep -n -E 'install-tools --tool (tofu|osv-scanner|trivy|kube-linter|promtool|gitleaks|semgrep|tuicr|helm|kubectl)' -- .github`

## 2. The rules lock holds no Semgrep version

Kind: behavior. Reads: `src/devops_cli/review/rules_pack.py`, the branch of #4388. Changes: `src/devops_cli/review/rules_pack.py`, `src/devops_cli/review/rules/rules.lock`, `src/devops_cli/commands/review.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_review_rules_pack.py`, `docs/commands/review.md`, `docs/commands/ai.md`.

- [x] 2.1 Write the failing cases: a lock entry with `semgrep_version` does not load, and `devops review rules test --check` prints the version that a stand-in `semgrep --version` states; the other cases use that stand-in version and no pin
  - Verification: `$ uv run devops ci test tests/commands/test_review_rules_pack.py`
- [x] 2.2 Delete `RuleLockEntry.semgrep_version`, the field in `rules.lock`, `pinned_semgrep_version` and the version compare of `verify_rules_lock`; `run_rule_pack_tests` returns the lock and the detected version, which the command prints. Name no pinned version in the help text of `--check`, and regenerate the docs
  - Verification: `$ uv run devops ci test tests/commands/test_review_rules_pack.py`

## 3. Documents

Kind: documents. Reads: `docs/SDLC.md`, `docs/CLUSTER.md`. Changes: `docs/SDLC.md`, `docs/CLUSTER.md`.

- [x] 3.1 Name the source of the tools of a CI job and the cache of the action in "Where a Check Runs", the kubectl and helm of the image in the image pins section, the tools and the paths of the Service Image Tests, and the promtool of the devtools image in `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- #6409 installs OpenSpec and Style Dictionary with `npm ci` from the root `package-lock.json`, in place of the three OpenSpec steps and the Style Dictionary step.
- #4363 deletes `devops install-tools`, `src/devops_cli/tools_lock/` and the `src/devops_cli/tools_lock/**` path of `service-image-test.yml`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
