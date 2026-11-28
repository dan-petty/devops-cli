# Design

## Decisions
- Use `mapped_inventory` in both `advisories` and `sweep` commands (`src/devops_cli/commands/research.py`) so components receive `osv_ecosystem`, `osv_name`, `purl`, `registry`, and `repo`, and `[[pin]]` entries join the inventory.
- Pass `watch = read_watch_list(...)` in `sweep` to both `sweep_dry_run` and `find_advisories`.
- In `_plan` (`src/devops_cli/research/advisories.py`), treat a non-registry component as covered when it has either a `watch` entry or an `osv_ecosystem`/`osv_name` pair. If `pinned_version(component.version)` is None (such as `version=""` on an external `[[pin]]` or `"latest"`), increment `plan.unpinned` once and enqueue no query; otherwise add `(component.osv_name, component.version, component.osv_ecosystem)` to `plan.osv` whenever the OSV pair is non-empty, and add the GitHub query whenever the component is an Action or `entry is not None`.
- In `_osv_findings`, query `osv.get_vulnerability(named.id, key[0], key[2])` so mapped components whose OSV module path differs from their inventory name resolve their vulnerability record cleanly.

## Rejected alternatives
- Dropping the OSV pair claim from `.devops/research-watch.toml` comments: rejected because OSV returns advisories for upstream modules (such as Go images) where GitHub repository advisories return none.
- Querying OSV inside `_plan` by looking up `watch` instead of using `mapped_inventory`: rejected because it duplicates `mapping.py` and omits `[[pin]]` components.
- Skipping GitHub repository advisories when `osv_ecosystem`/`osv_name` is set: rejected because both sources complement each other on watch entries.
