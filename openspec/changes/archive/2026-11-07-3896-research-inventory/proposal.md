# Proposal

## Why

Issue #3896: no tool reads all the pins of the project. `devops survey` reads `pyproject.toml` only, and `devops k8s image-pins` checks that an image exists in its registry, not what it is. Nothing lists GitHub Actions versions, Dockerfile `FROM` lines, `tools.lock` entries and chart versions in one list. A research agent cannot watch what it cannot list. This change is the first slice of the research agent: a reader that lists the pins, with no model, no network and no store.

## What Changes

- New command group `devops research` with one command, `devops research inventory`. It reads the files of a repository and prints a typed list of components. A component has a kind, an ecosystem, a name, a version, a source file and a line. `--json` and `--format yaml` print the list and a summary with the count of each kind and each ecosystem, and the count of components with the ecosystem `unknown`.
- The reader covers these files: `pyproject.toml`, `uv.lock`, the `tools.lock` of the tools and its hashed requirement and Node lock files, the Dockerfiles, the devcontainer lock, the workflows and composite actions of `.github/`, the Argo CD Applications and the YAML under `k8s/`, and the Terraform files under `tf/`.
- A component of a source that the reader cannot map to a registry (a binary tool whose source is no GitHub repository) has the ecosystem `unknown`. It stays in the list and in the count.
- The command has the `no-external-request` dry-run class and an MCP tool (`research_inventory`, read only, with no path argument).
- `devops_cli.k8s.image_pins` makes `yaml_mappings` and `yaml_scalar` public, and adds `key_line` and `image_nodes`, so the reader reuses the way that `devops k8s image-pins` reads an image. `image_values` keeps its result.
- Observable behavior changes (a command, an MCP tool, an error code), so the change carries a spec delta for the new capability `research-inventory`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-inventory`: The typed list of components that `devops research inventory` reads from the files of a repository.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/research/`, `src/devops_cli/commands/research.py`, `src/devops_cli/exceptions/research.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/main.py`, `src/devops_cli/config/constants.py` (MCP exposure table), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/`.
- Tests: `tests/research/`, `tests/commands/test_research_inventory.py`, `tests/fixtures/research/repo/`.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md` and `docs/ERRORS.md`, all generated.
- No new dependency, no network egress and no secret.
- Not in this change: the file `.devops/research-watch.toml` with the OSV mapping and the pins outside the repository, the purl and upstream repository of a component, and the images that Helm renders. Another issue holds them.

## Feasibility

- Checked on 2026-11-07 at `origin/main` b6af763b by running the reader on the real tree: 548 components in eight kinds (312 Python packages, 74 actions, 58 Node packages, 46 container images, 24 tools, 18 charts, 9 Terraform providers, 7 devcontainer features), every one with a line and a version. The Python count agrees with the design result: 98 declared dependencies plus 139 transitive packages are the 237 packages that `uv.lock` lists with the project itself left out, and 18 of the 31 Argo CD Applications pin a chart.
- Parsers are the ones that the project already ships: `tomllib`, PyYAML (composed nodes give lines), `packaging` (requirements), `python-hcl2` 8.1.4, `tree-sitter-dockerfile` through `tree-sitter` 0.26, and `docker.utils.parse_repository_tag` of docker-py for image references.
- python-hcl2 8.1.4 gives no line for an attribute: `with_meta=True` adds none for the `required_providers` block. The line is the one that opens the provider's attribute. A parser gives no line for a key of TOML or JSON either, so the line of those comes from the text.
- tree-sitter 0.26 warns that the integer language of `tree-sitter-dockerfile` 0.2.0 is deprecated. The reader silences this one warning where it loads the grammar, as `devops ai ast` loads it.
- The renderer of `devops k8s image-pins` runs `helm template --repo`, which fetches the chart. The reader must make no request, so it reads the images in the files as they stand, and the rendered images stay for the follow-up issue.

## Existing Tool Considered

Renovate extracts the same pins, but its `extract` step gives no list that code can read here and it needs a service to run. Dependabot is off for this repository. `osv-scanner` reads lock files for advisories, not workflow, image and chart pins. The reader uses `tomllib`, PyYAML, `packaging`, `python-hcl2`, tree-sitter and docker-py, which the project already depends on, and the `tools_lock` model. No new parser library is needed. The code that the change adds is the walk over eight file formats (about 600 lines with the model); it deletes no internal code.
