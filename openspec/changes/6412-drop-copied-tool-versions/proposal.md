# Proposal: #6412

## Why
Closes #6412. Some files that devops-cli writes or reads hold copies of tool versions, and the copies drift. `osv_scanner.py` writes the osv-scanner version into the CycloneDX inventory and into the seed of the empty-database digest. The `devops devcontainer init --image` path of `devcontainer.json.j2` adds a block of Dev Container Features, and the block drifts from the published image. The knowledge base repeats the pins of `pyproject.toml` and `uv.lock`, and some of these copies are already different from `uv.lock`. devops-cli is not a package manager: a version lives only in the manifest that its package manager owns.

## What Changes
- The CycloneDX inventory of the osv-scanner adapter names the tool with `vendor` and `name` only. The optional `version` field goes.
- The digest of an empty osv-scanner database cache uses a seed with no version. The module docstring names no version.
- `devops devcontainer init` writes no `features` key on any path. The block of eight Features goes, `docker-in-docker:2` with it. The image owns the user `vscode` and the tools. The unreachable branch that wrote a `python:<version>-trixie` image goes.
- The scaffold drops `DOCKER_CLI_HINTS`: the published image has no Docker CLI. Its extension list is the same as the list in `.devcontainer/devcontainer.json`.
- The help of `--minikube` says what the option does now: it forwards the ports of the Minikube stack.
- The knowledge base names no package version. `python_packages.md` loses its pins and its version column, and says that `pyproject.toml` and `uv.lock` own the versions. The library articles lose their `name==version` pins and the version after each PyPI link.
- The output of `devops devcontainer init` and of the osv-scanner adapter changes, so the change has a spec delta.

## Capabilities
- `scanner-adapters`: ADDED requirement for the osv-scanner inventory.
- `devcontainer-image-tools`: ADDED requirement for the scaffold with no Feature.

## Impact
- The digest of an empty osv-scanner cache changes one time.
- `devops devcontainer init --image <other>` adds no Feature. The other image must have the user `vscode` and the tools, as the published image has.
- A Renovate update of a Python package or of osv-scanner changes no file under `src/`.
- The change fits one pull request.

## Feasibility
- `git grep -nE '2\.6\.0' origin/main -- src/devops_cli/security/osv_scanner.py` finds the docstring (line 3), the seed (line 103) and the CycloneDX tool entry (line 213). The CycloneDX 1.5 schema makes each field of a tool entry optional.
- `devops devcontainer init` (`src/devops_cli/commands/devcontainer.py`) always sets `image`: the `--image` value or the published image. So the `{% else %}` branch of the template that writes `python:<version>-trixie` never runs.
- After #6414, `.devcontainer/image/devcontainer.json` has `remoteEnv` `DOCKER_HOST=unix:///var/run/docker.sock`. The Dev Containers CLI writes `remoteEnv` into the `devcontainer.metadata` label of the image, and `.github/actions/devcontainer-smoke` checks `DOCKER_HOST` in an image that it starts with no `remoteEnv` of its own. `.devcontainer/devcontainer.json` does not set `DOCKER_HOST`. So the published path of the scaffold gets the value from the label, and a copy in the template is not necessary.
- `git grep -nE '[a-z0-9-]+==[0-9]' origin/main -- src/devops_cli/ai/knowledge_base` finds 26 pins in 23 lines of `python_packages.md` and one line in each of 4 library articles. `python_packages.md` also has a column of 13 versions. A census of the PyPI links with a version (`pypi\.org/project/[^)]*\) \(` followed by a version in a code span) finds 18 library articles.

## Existing Tool Considered
- `pyproject.toml`, `uv.lock` and Renovate already own each package version, and the image of devtools owns each tool. The change builds nothing: it deletes copies.
- Internal code that the change deletes: the `features` block and the Python image branch of `src/devops_cli/templates/devcontainer.json.j2`, the version of the CycloneDX tool entry, and the version in the digest seed of `src/devops_cli/security/osv_scanner.py`.
