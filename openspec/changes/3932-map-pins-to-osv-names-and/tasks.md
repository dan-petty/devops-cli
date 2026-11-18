# Tasks

## 1. Read the OSV identity and the extra pins of the watch list

Kind: behavior. Reads: `src/devops_cli/research/watch.py`, `src/devops_cli/research/models.py`, `tests/research/test_watch_list.py`, `tests/research/test_advisories.py`. Changes: `src/devops_cli/research/watch.py`, `tests/research/test_watch_list.py`.
Adds: `PinEntry`

- [x] 1.1 Add `test_the_watch_list_reads_the_osv_identity_and_the_extra_pin` in `tests/research/test_watch_list.py`: it writes a mapping file under `tmp_path` with a `[[watch]]` entry that gives `osv_ecosystem` and `osv_name` and a `[[pin]]` entry that declares a tool, and asserts that `read_watch_list` gives both the OSV fields and the pin
  - Verification: `$ uv run devops ci test tests/research/test_watch_list.py` fails on the base
- [x] 1.2 Write the failing case in `tests/research/test_watch_list.py` first, with the `_write` helper of that module. Add to `src/devops_cli/research/watch.py:33:class WatchEntry(BaseModel):` the optional `osv_ecosystem`, `osv_name` and `purl` fields and keep `extra` at `forbid`. Add `PinEntry` to `src/devops_cli/research/watch.py`, with `kind` of `ComponentKind`, `name`, an optional `version` that defaults to the empty string, an `ecosystem` that defaults to `unknown`, and the optional `osv_ecosystem`, `osv_name`, `repo` and `purl`. Add `pin: list[PinEntry]` to `src/devops_cli/research/watch.py:44:class WatchList(BaseModel):`. Keep the refusal of `src/devops_cli/research/watch.py:29:_COVERED_ELSEWHERE = frozenset({Ecosystem.PYPI, Ecosystem.NPM, Ecosystem.GITHUB_ACTIONS})` for the `watch` entries only, so a pin of any ecosystem is read
  - Verification: `$ uv run devops ci test tests/research/test_watch_list.py` passes

## 2. Map each component to its OSV identity, purl and registry reference

Kind: behavior. Reads: `src/devops_cli/research/models.py`, `src/devops_cli/research/inventory.py`, `src/devops_cli/research/watch.py`, `src/devops_cli/research/container_pins.py`, `src/devops_cli/docker/registry.py`, `tests/research/test_inventory.py`, `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, `tests/research/test_watch_list.py`, `tests/research/test_inventory_repository.py`. Changes: `src/devops_cli/research/models.py`, `src/devops_cli/research/mapping.py` (new), `tests/research/test_mapping.py` (new).
Adds: `apply_mapping`, `purl_of`, `registry_of`, `mapped_inventory`

- [x] 2.1 Add `test_a_mapped_component_gets_its_osv_identity`, `test_an_extra_pin_of_the_mapping_file_is_listed`, `test_an_unmapped_pin_stays_unknown_and_is_counted`, `test_a_package_component_gets_a_purl` and `test_an_image_component_keeps_its_registry_reference` to the new module `tests/research/test_mapping.py`, in the shape of the cases of `tests/research/test_inventory.py`; each writes a repository under `tmp_path` with a package file, a container file and a mapping file, and calls `mapped_inventory`, `apply_mapping`, `purl_of` and `registry_of`
  - Verification: `$ uv run devops ci test tests/research/test_mapping.py` fails on the base
- [x] 2.2 Write the failing cases in `tests/research/test_mapping.py` first, with the fixture helpers of `tests/research/test_inventory.py`. Add to `src/devops_cli/research/models.py:class Component` the fields `osv_ecosystem`, `osv_name`, `purl`, `registry` and `repo`, each a string that defaults to the empty string, so every existing caller keeps working. Add `src/devops_cli/research/mapping.py`: `mapped_inventory(root)` reads the components with `read_inventory` of `src/devops_cli/research/inventory.py` and the watch list with `read_watch_list` of `src/devops_cli/research/watch.py`, passes them to `apply_mapping`, sorts by file, line and name and summarizes; `apply_mapping` rebuilds each frozen component with `model_copy` and sets on it the OSV ecosystem, the OSV name, the purl and the upstream repository of the watch entry that names its ecosystem and name, sets the registry of a container image with `registry_of`, appends one component for each `[[pin]]` entry at the file `external` and line 0, and leaves a component that no entry names at the ecosystem `unknown`; `purl_of` builds the purl of a `pypi`, `npm` or `helm` component with `PackageURL` and gives the empty string for any other ecosystem; `registry_of` gives the registry host of a container image with `src/devops_cli/docker/registry.py:48:def image_reference(image: str) -> tuple[str, str]:` and the empty string for another kind
  - Verification: `$ uv run devops ci test tests/research/test_mapping.py` passes

## 3. List the rendered images of the Applications when the option is set

Kind: behavior. Reads: `src/devops_cli/research/mapping.py`, `src/devops_cli/research/container_pins.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/k8s/environment.py`, `tests/research/test_inventory.py`. Changes: `src/devops_cli/research/render.py` (new), `src/devops_cli/research/mapping.py`, `tests/research/test_mapping.py`.
Adds: `renderer_for`

- [ ] 3.1 Add `test_a_rendered_image_is_listed_when_a_renderer_is_given` and `test_the_default_inventory_starts_no_program_and_opens_no_connection` to `tests/research/test_mapping.py`; the first passes a fake renderer to `mapped_inventory` and asserts that the image is listed at the file `rendered` and line 0 and that the fake ran once, the second refuses `subprocess.Popen` and the socket connect and asserts that `mapped_inventory` lists the same components and that `renderer_for` was never called
  - Verification: `$ uv run devops ci test tests/research/test_mapping.py` fails on the base
- [ ] 3.2 Write the failing cases in `tests/research/test_mapping.py` first. Add to `mapped_inventory` the keyword-only `renderer` parameter, `None` by default: with a renderer set it adds each returned reference as a container image with `src/devops_cli/research/container_pins.py:34:def image_component(reference: str, file: str, line: int) -> Component:` at the file `rendered` and line 0, and without one it adds no rendered image. Add `src/devops_cli/research/render.py` with `renderer_for(k8s_dir)` that returns a callable: it resolves the environment with `src/devops_cli/k8s/environment.py:103:def resolve_environment(`, renders it with `src/devops_cli/k8s/image_pins.py:288:def collect_image_pins(`, and yields the keys of `src/devops_cli/k8s/image_pins.py:86:pinned: dict[str, tuple[str, ...]]` and of `src/devops_cli/k8s/image_pins.py:89:latest: dict[str, tuple[str, ...]]`, and never those of `src/devops_cli/k8s/image_pins.py:88:local: dict[str, tuple[str, ...]]`
  - Verification: `$ uv run devops ci test tests/research/test_mapping.py` passes

## 4. Add the render option to the inventory command and its tool description

Kind: behavior. Reads: `src/devops_cli/commands/research.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/dry_run/state.py`, `src/devops_cli/research/render.py`, `tests/commands/test_research_inventory.py`, `tests/ai/mcp/test_mcp_tool_listing.py`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/commands/research.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_research_inventory.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.
Adds: `inventory_render`

- [ ] 4.1 Add `test_the_render_option_lists_an_image_of_the_rendered_applications` and `test_a_dry_run_with_the_render_option_calls_the_renderer_never` to `tests/commands/test_research_inventory.py`: the first replaces `renderer_for` in `devops_cli.commands.research` with a fake that returns one image, asserts that the image is in the output of the run with `--render`, and asserts that a run without the option calls `renderer_for` never; the second runs the command under the root `--dry-run` with `--render` and asserts that `renderer_for` was never called; change `test_inventory_json_is_the_inventory_of_the_root` to compare the output with the JSON of `mapped_inventory`
  - Verification: `$ uv run devops ci test tests/commands/test_research_inventory.py tests/ai/mcp/test_mcp_tool_listing.py` fails on the base
- [ ] 4.2 Write the failing cases in `tests/commands/test_research_inventory.py` first. Add to `src/devops_cli/commands/research.py:40:@app.command("inventory", help=HELP.research.inventory)` the boolean option `--render`, whose help is `HELP.research.inventory_render`, and pass the renderer as the `renderer` argument only when the option is set and `is_dry_run()` of `src/devops_cli/dry_run/state.py` is false, so the default run and a dry run build no renderer. Add `inventory_render` to `src/devops_cli/lang/en/help.py:class ResearchCommandHelp` and say in the `inventory` help of that class that the command reads files only unless `--render` is set. The MCP tool `research_inventory` takes its description from that help, so regenerate the listing snapshot of `tests/ai/mcp/test_mcp_tool_listing.py` with the `--snapshot-update` run of that test
  - Verification: `$ uv run devops ci test tests/commands/test_research_inventory.py tests/ai/mcp/test_mcp_tool_listing.py` passes

## 5. Declare the OSV names and the pins outside the repository

Kind: other. Reads: `.devops/research-watch.toml`, `src/devops_cli/research/mapping.py`, `src/devops_cli/research/watch.py`. Changes: `.devops/research-watch.toml`, `tests/research/test_research_watch_file.py` (new).

- [ ] 5.1 Add `osv_ecosystem = "Go"` and the module path as `osv_name` to the `argo`, `argocd` and `trivy` entries of `.devops/research-watch.toml`, which already carry that path as `package`, and describe the two fields in the comment of the file. Add a `[[pin]]` of the kind `tool` for the node OS, named `ubuntu`, with the OSV ecosystem `Ubuntu` and the OSV name `linux`, and a `[[pin]]` of the kind `tool` for the NVIDIA driver, named `nvidia-driver`; neither entry carries a version, a host name, an address or a path of a device file, because those versions belong to the environment's own record and not to this repository. Write `tests/research/test_research_watch_file.py`: it reads `.devops/research-watch.toml` and every file of the research fixtures, and fails on an RFC 1918 or loopback address parsed with `ipaddress`, on a host name that ends in `.local`, `.internal` or `.svc`, on `localhost`, and on a path of a device file; it also asserts that `mapped_inventory` of the repository lists both external pins at the file `external` and line 0, and that the `argo`, `argocd` and `trivy` components carry the OSV ecosystem `Go`
  - Verification: `$ uv run devops ci test tests/research/test_research_watch_file.py` passes

## 6. Regenerate the CLI reference, the command page and the MCP tool list

Kind: other. Reads: `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`, `src/devops_cli/commands/research.py`. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`.

- [ ] 6.1 Run `uv run devops docs generate` and commit the three generated pages, so `docs/CLI_REFERENCE.md` and `docs/commands/research.md` list `--render` under `devops research inventory` and `docs/MCP_TOOLS.md` holds the new description of `research_inventory`. The settings table gains no row, because the change adds no setting. Edit no generated page by hand
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 Regenerate `docs/CLI_REFERENCE.md`, `docs/commands/research.md` and `docs/MCP_TOOLS.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test that fails on the base: a component named in the mapping file gets its OSV ecosystem and name, and an extra pin of the file appears in the list.
- Group 2: A test: a pin with no mapping appears with ecosystem `unknown` and is counted.
- Group 3: A test: the default inventory makes no network request and starts no program.
- Group 3: A test: the opt-in render lists an image that only the rendered chart names, with a fake for the renderer.
- Group 5: No private host name, private address or device path is in the fixtures or the mapping file.
- Group 6: The command is in the CLI reference (`devops docs generate --sync-readme`) and the settings table if it adds a setting.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
