# Tasks

## 1. OSV inventory with no tool version

Kind: behavior.

- [x] 1.1 Assert in `tests/security/test_osv_scanner.py` that the CycloneDX inventory names osv-scanner with `vendor` and `name` and no `version`
  - Verification: `$ uv run devops ci test tests/security/test_osv_scanner.py`
- [x] 1.2 Remove `version` from the tool entry that `parse_osv_scanner_output` writes
  - Verification: `$ uv run devops ci test tests/security/test_osv_scanner.py`

## 2. Scaffold with no Feature

Kind: behavior.

- [x] 2.1 Assert in `tests/commands/test_devcontainer.py` that `init --image python:3.14` writes no `features` key, and replace the kubectl Feature tests of `tests/core/test_template_rendering.py` with a test that `minikube` adds only `forwardPorts` and no path adds `features`
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py tests/core/test_template_rendering.py`
- [x] 2.2 Delete the `features` block and the unreachable Python image branch of `src/devops_cli/templates/devcontainer.json.j2`, change the help of `--minikube`, and regenerate the command reference
  - Verification: `$ uv run devops docs generate --check`

## 3. Copied values

Kind: other.

- [x] 3.1 Seed the empty-database digest with a string that has no version, and remove the version from the docstring of `src/devops_cli/security/osv_scanner.py`
  - Verification: `$ ! git grep -nE '[0-9]+\.[0-9]+\.[0-9]+' -- src/devops_cli/security/osv_scanner.py`
- [x] 3.2 Remove `DOCKER_CLI_HINTS` from the scaffold, because the published image has no Docker CLI
  - Verification: `$ ! git grep -n DOCKER_CLI_HINTS -- src/devops_cli/templates`
- [x] 3.3 Make the extension lists of the scaffold the same as the lists of `.devcontainer/devcontainer.json`
  - Verification: `$ d=$(mktemp -d) && uv run devops devcontainer init "$d" > /dev/null && jq -se '[.[].customizations | map_values(.extensions)] | .[0] == .[1]' .devcontainer/devcontainer.json "$d/.devcontainer/devcontainer.json"`
- [ ] 3.4 Remove the `name==version` pins and the version column of `python_packages.md` and the pins of four library articles, and say that `pyproject.toml` and `uv.lock` own the versions
  - Verification: `$ ! git grep -nE '[a-z0-9-]+==[0-9]' -- src/devops_cli/ai/knowledge_base`
- [ ] 3.5 Remove the version after each PyPI link of the library articles
  - Verification: `$ ! git grep -nE 'pypi\.org/project/[^)]*\) \(.[0-9]' -- src/devops_cli/ai/knowledge_base`

## 4. Documents

Kind: other.

- [ ] 4.1 Say in `docs/DEVCONTAINER_USAGE.md` that `devops devcontainer init` adds no Feature, and that an image that `--image` names must have the user `vscode` and the tools
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
