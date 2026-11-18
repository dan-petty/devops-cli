# Design

## Decisions

- **Extend `.devops/research-watch.toml` with the OSV fields and the `[[pin]]` entries instead of adding a second file.**: The file already maps a component to its repository for the advisories step, and one file keeps the two steps in sync.
- **Match a pin to a mapping entry by its inventory ecosystem and name.**: The watch list keys on that pair, and an image and a chart with the same name already differ in ecosystem.
- **Declare the pins outside the repository as `[[pin]]` entries that the inventory lists at the file `external` and line 0.**: An explicit entry is reviewable and testable, and it needs no probe of a host.
- **Give a `[[pin]]` entry an optional version, empty when the entry declares none.**: The versions of the node OS and of the driver belong to the environment's own record, which this repository does not hold, so the file declares those two pins and invents no version.
- **Build the purl with `PackageURL` of `packageurl-python`, already a locked dependency.**: The library applies the purl type rules and the percent-encoding, and the change adds no dependency and no line of the lock.
- **Take the upstream repository from the `repo` of the mapping entry or of the extra pin.**: It is local data that the advisories step already maintains, and it needs no registry or API call.
- **Apply the mapping in a new module and leave the file reader of the research package untouched.**: That reader has callers under `src/` that read another inventory, and `mapped_inventory` composes it for the new fields.
- **Add `--render` to `devops research inventory` and build the renderer only when it is set.**: One command keeps one inventory, and the default path cannot reach the renderer.
- **Build no renderer when the run is a dry run, and keep the dry-run class `no-external-request`.**: `--render` reaches the network, and a dry run sends no external request, so the option is skipped when `is_dry_run()` is true and the declared class stays true.
- **Pass the renderer into `mapped_inventory` as a keyword-only parameter, and build the real one in `src/devops_cli/research/render.py`.**: A test replaces the renderer with a fake that needs no checkout and no network.
- **Change the MCP tool description with the command help, and regenerate the listing snapshot and `docs/MCP_TOOLS.md` in the same groups.**: `research_inventory` takes its description from the `inventory` help of `src/devops_cli/lang/en/help.py`, so `test_the_tool_listing_matches_the_snapshot` and the docs row fail unless the snapshot and the generated tool list change too.
- **List the pinned and the latest rendered images, and not the images of a registry that only the cluster reaches.**: A cluster-local registry name is no public pin to query, and the advisory and release steps query public sources.
- **Scan the mapping file and the research fixtures for a private host name, an address and a device path in a test, and keep the render opt-in.**: The mapping becomes data that a later step queries, and the fixture scan and the default-run test are the checks that fail when such a value or a renderer reaches the default path.

## Rejected alternatives

- **A new TOML file for the mapping.**: It splits one source from the watch list that the advisories step reads at `src/devops_cli/research/watch.py:27:WATCH_FILE = ".devops/research-watch.toml"`, so the two can drift.
- **Environment variables for the mapping.**: They are hard to review and to test, and no test can assert the mapping of a component from a file.
- **Match a pin to a mapping entry by name and kind.**: The watch list has no kind field, and an image and a chart with the same name already differ in ecosystem.
- **Match a pin to a mapping entry by file and line.**: A pin moves between lines, and an external pin has no file.
- **Infer the pins outside the repository from the host.**: It needs a network or host probe and breaks the offline default.
- **A hand-written purl formatter.**: It must reimplement the purl type rules and the percent-encoding that `packageurl-python` already applies.
- **No purl, with the registry reference only.**: It does not meet the purl requirement for package components.
- **A separate command for the rendered images.**: It adds a second entry point for one inventory.
- **Render the Applications on every inventory run.**: It makes the default run open a connection and start helm, and `helm` is `NOT_IN_RUNNER`.
- **Change the dry-run class of `devops research inventory` to `request-plan` and declare `--dry-run`.**: The default run reads files only and executes normally under `--dry-run`, as `src/devops_cli/commands/research.py:41:@dry_run_class("no-external-request")` states; the render is the one path that reaches out, and the plan skips it in a dry run.
- **Query a registry or an API for the upstream repository.**: It needs a network request and breaks the offline default.
- **Infer the repository from the image name.**: It is unreliable, and it can name a host that is not public.
- **Add a keyword-only parameter to the file reader of the research package.**: Its callers under `src/` read another inventory, so the plan would change them for no behavior of their own; the mapping lives in `src/devops_cli/research/mapping.py` instead.
- **Keep the `inventory` help unchanged and give the MCP tool its own description.**: The tool description comes from the command help, so a second text would drift; the plan changes the help once and regenerates the snapshot and `docs/MCP_TOOLS.md`.

## Security

The plan adds no dependency: `packageurl-python` stays locked as it is, so the lock and its supply chain do not change. A trust boundary is crossed when a watch entry or a pin entry names a host, an address or a repository that a later step queries, and when `--render` starts helm and fetches a chart source over the network. A person must confirm that the mapping file and the research fixtures hold no private host name, no RFC 1918 or loopback address and no device path, that a run without `--render` and a dry run build no renderer, and that the changed tool description in `docs/MCP_TOOLS.md` matches the command help. `tests/research/test_research_watch_file.py` fails when such a name, an address or a path appears, the default-run case in `tests/research/test_mapping.py` fails when a program starts or a socket connects, `test_a_dry_run_with_the_render_option_calls_the_renderer_never` fails when a dry run reaches the renderer, and `test_the_tool_listing_matches_the_snapshot` fails when the tool description and the snapshot differ.
