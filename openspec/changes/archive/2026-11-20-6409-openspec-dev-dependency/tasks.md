# Tasks

## 1. Run and judge OpenSpec by the lockfile of the checkout

Kind: behavior. Changes: `src/devops_cli/openspec/tool.py`, `src/devops_cli/openspec/gate.py`, `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/commands/openspec.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/openspec/test_openspec_gate.py`, `tests/core/test_openspec_command.py`, `tests/tools_lock/test_openspec_contract.py`, `tests/support/fakes/openspec.py`, `tests/support/openspec_scenarios.py`.

- [x] 1.1 `test_the_gate_compares_with_the_lockfile_of_the_checkout`, `test_a_checkout_whose_lockfile_pins_no_openspec_fails_the_version_check`, `test_the_gate_runs_the_openspec_that_npm_installed_in_the_checkout` and `test_a_version_finding_names_the_openspec_that_npm_installed` in `tests/openspec/test_openspec_gate.py`, and `test_a_binary_other_than_the_pin_of_the_checkout_lockfile_fails_check_and_regenerate` in `tests/core/test_openspec_command.py`: each scenario tree holds a copy of the root `package-lock.json`, the fake records the program it started, and the hint is `npm ci --ignore-scripts`; the ten cases failed on the base
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py tests/core/test_openspec_command.py tests/tools_lock/test_openspec_contract.py`
- [x] 1.2 Add `locked_version`, `installed_program` and `OpenSpecTool.program` and `path` to `src/devops_cli/openspec/tool.py`; `isolated_openspec(root)` runs `node_modules/.bin/openspec` of the checkout when it exists, else the `openspec` on PATH; `version_finding` reads the pin from the root `package-lock.json` of the checkout and reports a lockfile that pins none; check, regenerate, archive, new and `devops roadmap plan-check` pass the checkout; `missing_hint` names `npm ci --ignore-scripts`
  - Verification: `$ uv run devops ci test tests/openspec tests/core/test_openspec_command.py tests/tools_lock/test_openspec_contract.py`

## 2. Audit and list the root lockfile

Kind: behavior. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/research/tool_pins.py`, `tests/commands/test_ci.py`, `tests/commands/test_dependency_audit.py`, `tests/core/test_dependency_audit_ignores.py`, `tests/research/test_inventory.py`, `tests/research/test_advisories.py`, `tests/commands/test_research_inventory.py`, `tests/fixtures/research/repo/package-lock.json` (new).

- [x] 2.1 `test_the_audit_check_audits_uv_and_each_npm_lockfile_without_a_shell` expects `npm audit ... --prefix .`, the ignore tests of `tests/commands/test_dependency_audit.py` name `package-lock.json`, and `test_inventory_lists_one_component_for_each_pin_of_the_fixture_repository` expects the package of the root lockfile of the fixture repository; the cases failed on the base
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/commands/test_dependency_audit.py tests/research`
- [x] 2.2 `_npm_audit_cmds` audits the root lockfile first, `npm_audit_lockfile` joins the prefix as a POSIX path, and `read_tool_pins` reads the root `package-lock.json`
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/commands/test_dependency_audit.py tests/core/test_dependency_audit_ignores.py tests/research`

## 3. Delete the tool folders and the install-tools version check

Kind: other. Changes: `src/devops_cli/tools_lock/openspec/` (deleted), `src/devops_cli/tools_lock/style-dictionary/` (deleted), `src/devops_cli/tools_lock/tools.lock`, `src/devops_cli/commands/install_tools.py`, `src/devops_cli/tools_lock/versions.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_install_tools.py`, `tests/tools_lock/test_tools_lock.py`, `tests/tools_lock/test_versions.py`, `tests/ci/test_fail_to_pass.py`, `docs/commands/install-tools.md`.

- [x] 3.1 Delete the two package folders and their `tools.lock` entries, the OpenSpec version check of `devops install-tools` with its messages and tests, and `path_version` with its tests; the npm tests of install-tools use the Dev Containers CLI; regenerate the command documents with `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_install_tools.py tests/tools_lock tests/ci/test_fail_to_pass.py`
- [x] 3.2 No path names the deleted folders or entries
  - Verification: `$ ! git grep -n -I -F -e src/devops_cli/tools_lock/openspec -e src/devops_cli/tools_lock/style-dictionary -e npm.openspec -e npm.style-dictionary -- README.md CONTRIBUTING.md AGENTS.md CONTEXT.md .devcontainer .github src tests Dockerfile Makefile`

## 4. Install the root lockfile in the devcontainer, CI and the Service image

Kind: other. Changes: `package.json` (new), `package-lock.json` (new), `.gitignore`, `.dockerignore`, `Dockerfile`, `Makefile`, `.devcontainer/devcontainer.json`, `.github/workflows/ci.yml`, `.github/workflows/pr-title.yml`, `.github/workflows/copilot-setup-steps.yml`, `.github/workflows/service-image-test.yml`, `.github/renovate.json`, `.pre-commit-config.yaml`, `tests/invariants/test_workflow_contracts.py`.

- [x] 4.1 Add the root `package.json` and `package-lock.json` with OpenSpec 2.1.0 and Style Dictionary 5.8.0 as devDependencies and the overrides scoped under `style-dictionary`, and ignore `/node_modules/`
  - Verification: `$ uv run devops ci --check --only audit,lockfile`; by hand, `npm ci --ignore-scripts` and `npm ls @fission-ai/openspec style-dictionary` exit 0, and `git status --porcelain` shows no path under `node_modules`
- [x] 4.2 The `openspec` stage of `Dockerfile` installs the root lockfile in the `node` stage and prunes it to OpenSpec; `.dockerignore` lets the two files in; the image jobs of `ci.yml` and the Service Image Tests workflow watch them
  - Verification: by hand, `podman build --target openspec .` exits 0, and `node node_modules/@fission-ai/openspec/bin/openspec.js --version` in the result prints the version of `package-lock.json`; in CI, the smoke step of the Service Image job runs `openspec --version`
- [x] 4.3 The devcontainer runs `npm ci --ignore-scripts` after post-create and puts `node_modules/.bin` on `PATH`; the static, Design Tokens, plan-check and Copilot setup jobs run `npm ci --ignore-scripts`; `make design-tokens` calls `node_modules/.bin/style-dictionary`; Renovate drops the two custom managers and the OpenSpec rule matches the npm manager
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,openspec`

## 5. Documents

Kind: other. Changes: `CONTRIBUTING.md`, `docs/DESIGN.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/SDLC.md`, `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`, `docs/adr/0024-the-project-owns-its-design-tokens-in-the-dtcg-format-and-style-dictionary-builds-them.md`, `tests/support/openspec_recording.py`.

- [x] 5.1 CONTRIBUTING names `npm ci --ignore-scripts` in the setup steps and the OpenSpec update steps; DESIGN, DEVCONTAINER_USAGE and SDLC name the root lockfile; ADR 0010 and ADR 0024 get Status History lines
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- Pending a person: run `npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`, which the build session could not run.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
