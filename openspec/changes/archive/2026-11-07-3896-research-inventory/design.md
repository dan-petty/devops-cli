# Design

## Context

The research agent needs one list of what the project pins before it can look for news upstream. The list is an input to later steps, so it must be stable (same files, same list, same order) and typed.

## Goals / Non-Goals

**Goals:**
- One `Component` for each pin in the files, with a kind, an ecosystem, a name, a version, a file and a line.
- No model, no network, no store, and no program started.
- Tests on fixture files that copy the shapes of the repository, and one test over the real tree.

**Non-Goals:**
- The mapping file `.devops/research-watch.toml`, the purl and the upstream repository of a component, and pins outside the repository.
- The images that Helm renders from a chart.
- Any lookup of a newer version.

## Decisions

- **Decision: One component for each place a pin is written.**
  *Choice:* The list holds the same action once for each `uses:` line, so `actions/checkout` has about twenty-two components. A later step groups them by name and version. The file and line of each stay known.
  *Rejected alternative:* One component for each name and version, with a list of places. It loses the line of a pin that a later step must edit, and gives a model with a list inside a record.
- **Decision: A direct Python dependency has the pin of `pyproject.toml`; `uv.lock` adds only the packages that no direct dependency names.**
  *Choice:* The count of Python components equals the packages of the lock plus the groups that declare them.
  *Rejected alternative:* A component for each package of `uv.lock` and one more for each declaration. It counts one pin twice.
- **Decision: Lines come from the parser when it gives one, else from the text.**
  *Choice:* PyYAML nodes and tree-sitter nodes give lines. For TOML, JSON and HCL, `LineIndex` finds the line that shows the pin, and gives 0 when none does. A test over the real tree fails on a 0.
  *Rejected alternative:* A TOML library that keeps positions, such as `tomlkit`. It adds a dependency for one number.
- **Decision: Read the images in the files, not the rendered ones.**
  *Choice:* `image_nodes` of `devops_cli.k8s.image_pins` reads an `image` value, and the reader adds the `repository` with `tag` form of a values file.
  *Rejected alternative:* Reuse the renderer of `devops k8s image-pins`. It runs `helm template --repo` and `kubectl kustomize`, which start programs and fetch charts. The acceptance criteria forbid a network request.
- **Decision: The ecosystem is `unknown` when the pin does not show it.**
  *Choice:* A binary tool with a GitHub `source` is `github-release`; any other source is `unknown`. The summary counts `unknown`.
  *Rejected alternative:* Drop the component. A tool that nobody can map would then be invisible.
- **Decision: A parse failure raises `InventoryError`.**
  *Choice:* A file that does not parse stops the run with the file name (`RESEARCH_INVENTORY_ERROR`). A partial list would look complete.
  *Rejected alternative:* Skip the file and go on. It hides a pin.
- **Decision: The MCP tool takes no argument.**
  *Choice:* `--root` is not an option of the tool, so a model cannot point the reader at another path.
