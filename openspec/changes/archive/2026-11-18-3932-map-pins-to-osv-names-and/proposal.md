# Proposal

## Why

`devops research inventory` of #3896 lists the pins of a repository, but a component has no OSV name, no purl and no upstream repository, so the advisory step of #3898 and the release step of #3907 cannot query a source for it. The inventory also lists no pin that lives outside the repository and no image that only a rendered chart names. This change adds those fields and that list, and keeps the default run offline.

## What Changes

- `.devops/research-watch.toml` gains the OSV ecosystem, the OSV name and an optional purl on a `[[watch]]` entry, and the `[[pin]]` entries of the pins that live outside the repository.
- `Component` gains the OSV ecosystem, the OSV name, the purl, the registry reference and the upstream repository, each an empty string by default, so a component that no mapping entry names keeps the ecosystem `unknown` and stays counted.
- A new `mapped_inventory` in `src/devops_cli/research/mapping.py` applies the mapping, builds the purl and the registry reference, and adds each extra pin at the file `external` and line 0.
- A new `renderer_for` in `src/devops_cli/research/render.py` builds the renderer of `devops k8s image-pins` for the opt-in render.
- `devops research inventory` gains the opt-in `--render` option; a run without it, and a dry run, builds no renderer, starts no program and opens no connection.
- The changed help text of the command changes the MCP tool description of `research_inventory`, so the MCP tool listing snapshot and `docs/MCP_TOOLS.md` change with it.
- `tests/research/test_mapping.py`, `tests/research/test_watch_list.py`, `tests/research/test_research_watch_file.py` and `tests/commands/test_research_inventory.py` hold the tests of the mapping, the extra pins, the fixture scan and the command.
- The spec delta adds the mapped identity, the extra pin, the purl, the registry reference, the upstream repository and the opt-in render, and modifies the offline requirement to name the one option that reaches outside the files.
- `docs/CLI_REFERENCE.md`, `docs/commands/research.md` and `docs/MCP_TOOLS.md` are regenerated, and the settings table gains no row because the change adds no setting.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `research-inventory`: Mapped OSV identity, Extra pin of the mapping file, Package purl, Registry reference, Upstream repository, Opt-in render, The reader reaches nothing outside the files

## Impact

- Code: `src/devops_cli/research/watch.py`, `src/devops_cli/research/models.py`, `src/devops_cli/research/mapping.py`, `src/devops_cli/research/render.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/lang/en/help.py`, `.devops/research-watch.toml`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`
- Tests: `tests/research/test_watch_list.py`, `tests/research/test_mapping.py`, `tests/commands/test_research_inventory.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`, `tests/research/test_research_watch_file.py`

## Feasibility

- The first review finding is no defect of the plan's premise and is fixed: `search_code` for 'It reads files only.' gave `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json:4285:"description": "List every pin of the project as a typed component: Python packages, tools, container images, GitHub Actions, Helm charts and Terraform providers. It reads files only.",`, so group 4 now changes that snapshot in `changes` and runs `tests/ai/mcp/test_mcp_tool_listing.py` in its `verify`, and `list_files` of `tests/ai/mcp` gave `tests/ai/mcp/test_mcp_tool_listing.py`.
- The second review finding is no defect of the plan's premise and is fixed: `search_code` for 'MCP_TOOLS.md' gave `docs/MCP_TOOLS.md:110:| [`research_inventory`](#research_inventory) |` and `docs/MCP_TOOLS.md:1748:List every pin of the project as a typed component: Python packages, tools, container images, GitHub Actions, Helm charts and Terraform providers. It reads files only.`, so group 6 now changes `docs/MCP_TOOLS.md` with the other two generated pages.
- The changed text that reaches both files is `src/devops_cli/lang/en/help.py:2847:images, GitHub Actions, Helm charts and Terraform providers. It reads files only.` inside `src/devops_cli/lang/en/help.py:class ResearchCommandHelp`, which group 4 edits.
- The probe line 'The path `.devops/research-watch.toml` is a file of the staging commit.' confirms the mapping file, and `read_file` of `src/devops_cli/research/watch.py` gave `src/devops_cli/research/watch.py:27:WATCH_FILE = ".devops/research-watch.toml"`, the constant that names it.
- The probe lines 'The path `src/devops_cli/research/watch.py` is a file of the staging commit.', 'The path `src/devops_cli/research/models.py` is a file of the staging commit.' and 'The path `tests/research/test_watch_list.py` is a file of the staging commit.' confirm the files of the first group; `list_files` of `tests/research` also gave `tests/research/test_inventory.py`, which the second group reads and names.
- The probe line '`WatchList` defines no field `entry_of` in `src/devops_cli/research/watch.py`.' reads a method as a field: the callers answer gave `src/devops_cli/research/watch.py:51:def entry_of(self, ecosystem: Ecosystem, name: str) -> WatchEntry | None:`, and the change adds a `pin` field to that class and no field named after the method.
- The probe line 'The path `PackageURL.from_string` is no file of the staging commit. No commit in the history deleted or renamed it.' names a symbol of a library, not a path: `search_code` for 'packageurl-python' gave `pyproject.toml:87:"packageurl-python==0.17.6",`, so the dependency is already locked and the change adds none.
- `read_file` of `src/devops_cli/research/models.py` gave `src/devops_cli/research/models.py:class Component` with the fields `kind`, `ecosystem`, `name`, `version`, `file` and `line`, so group 2 adds five string fields with a default and no existing caller changes.
- `file_symbols` of `src/devops_cli/research/inventory.py` gave `src/devops_cli/research/inventory.py:21:def summarize(components: list[Component]) -> InventorySummary:` and `src/devops_cli/research/inventory.py:32:def read_inventory(root: Path) -> Inventory:`; the plan changes neither function, because `mapped_inventory` composes them.
- The command that gains the option is `src/devops_cli/commands/research.py:40:@app.command("inventory", help=HELP.research.inventory)`, whose root option sits at `src/devops_cli/commands/research.py:46:typer.Option("--root", help=HELP.research.inventory_root),`.
- The command declares `src/devops_cli/commands/research.py:41:@dry_run_class("no-external-request")`, and `search_code` gave `src/devops_cli/dry_run/state.py:43:def is_dry_run() -> bool:`, so the plan builds the renderer only when the option is set and the run is no dry run, and the declared class stays true.
- `read_file` of `src/devops_cli/commands/docs.py` gave `src/devops_cli/commands/docs.py:60:def generate(`, the command that group 6 runs; `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md:204:the option `--sync-readme` is deleted, so the command is `devops docs generate` (#5244).` states that the option of the issue's criterion is gone, so the plan writes the command without it.
- `list_files` of `docs/commands` gave `docs/commands/research.md`, and `search_code` for 'research inventory' gave `docs/CLI_REFERENCE.md:436:| [**research**](commands/research.md) |`, two of the three generated pages that the last group regenerates.
- `src/devops_cli/k8s/image_pins.py:288:def collect_image_pins(` needs a checkout of the repository, a client of a registry and a network: it renders each chart with helm, reads a git source of another repository and resolves each image in its registry. It runs only behind `--render`, and no test calls it.
- `src/devops_cli/k8s/environment.py:103:def resolve_environment(` needs a checkout of the repository and the settings of the workstation, and opens no network connection; it runs only behind `--render`.
- `src/devops_cli/docker/registry.py:48:def image_reference(image: str) -> tuple[str, str]:` needs no checkout, client or network: docker-py splits the reference on the host and gives `docker.io` for a name with no registry.
- `src/devops_cli/research/container_pins.py:34:def image_component(reference: str, file: str, line: int) -> Component:` needs no checkout, client or network: it splits a reference string alone.
- The verify commands introduce no program: `uv run devops ci test`, `uv run devops ci docs` and `uv run devops docs generate` start `uv` and `devops`, which the runner image holds. Their failure classes are `test`, `lint`, `types` and `ci_infra`, each with an action in the failure taxonomy.
- `helm` and `kubectl` are `NOT_IN_RUNNER`, so no group renders the real tree and no test starts them; the pod sets `readOnlyRootFilesystem: true` and `runAsNonRoot: true`, and each test writes only under its temporary directory.
- The versions of the node OS and of the NVIDIA driver are not checked by this run: no file of the repository states them, so the mapping file declares those two pins with no version and the plan invents none.
- The first checks against the real system are `uv run devops ci test tests/research/test_watch_list.py`, `uv run devops ci test tests/research/test_mapping.py`, `uv run devops ci test tests/commands/test_research_inventory.py tests/ai/mcp/test_mcp_tool_listing.py`, `uv run devops ci test tests/research/test_research_watch_file.py` and `uv run devops ci docs`.
- The change adds no setting, so the settings table gains no row and the CLI reference holds the command and its option alone.

## Existing Tool Considered

`packageurl-python` 0.17.6 builds and parses the purl, `tomllib` reads the mapping file, and `collect_image_pins` of `devops k8s image-pins` renders the Applications; the mapping schema, the extra-pin reader and the opt-in adapter are the glue this change builds, at about 15k tokens to build, 3k tokens to keep and fix, and 2 days elapsed.

## Dependencies

None.
