# Proposal: #7385

## Why
Two `devops research` commands read only part of `.devops/research-watch.toml` (#7385):
1. `devops research sweep` calls `read_inventory` and `find_advisories(inventory)` with no `watch` argument (and `sweep_dry_run` calls `advisory_requests(inventory)` with no `watch`), so `[[watch]]` and `[[pin]]` entries are ignored and their findings never reach the sweep or `ResearchCriticalFindings`.
2. `devops research advisories` calls `read_inventory` instead of `mapped_inventory`, `_plan` in `src/devops_cli/research/advisories.py` queues OSV queries only for Python and Node packages (ignoring component `osv_ecosystem`/`osv_name`), and `_osv_findings` passes `components[0].name` instead of `key[0]` (`osv_name`) to `get_vulnerability`.

## What Changes
- Update `_plan` in `src/devops_cli/research/advisories.py` so non-registry components with `osv_ecosystem` and `osv_name` at an exact pinned version queue OSV queries `(osv_name, version, osv_ecosystem)`, stay out of `not_covered`, and preserve any `[[watch]]` GitHub `repo` query.
- Update `_osv_findings` in `src/devops_cli/research/advisories.py` to pass `key[0]` (the OSV query package name) to `osv.get_vulnerability`.
- Update `sweep_dry_run` in `src/devops_cli/research/sweep.py` to accept `watch` and pass it to `advisory_requests`.
- Update `advisories` and `sweep` in `src/devops_cli/commands/research.py` to build the inventory with `mapped_inventory` and pass `watch` (`read_watch_list`) to both `sweep_dry_run` and `find_advisories`.
- Add unit and CLI tests in `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, and `tests/commands/test_research_advisories.py`.

## Capabilities
- `research-advisories`: Queries OSV for mapped `osv_ecosystem`/`osv_name` components, uses `key[0]` in record reads, and reads `mapped_inventory` in the CLI command.
- `research-sweep`: Reads `mapped_inventory` and `.devops/research-watch.toml` in both `--dry-run` and live `devops research sweep` runs.

## Impact
- `src/devops_cli/research/advisories.py`, `src/devops_cli/research/sweep.py`, `src/devops_cli/commands/research.py`: Wired end-to-end watch-list OSV and GitHub lookup path.
- `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, `tests/commands/test_research_advisories.py`: Regression coverage for all new and updated behaviors.

## Feasibility
Confirmed against `src/devops_cli/commands/research.py:121-135,254-266`, `src/devops_cli/research/advisories.py:119-149,331-334`, `src/devops_cli/research/sweep.py:152-166`, and `src/devops_cli/research/mapping.py:68-82`. `mapped_inventory` and `OSVClient` already populate and accept arbitrary `(osv_name, version, osv_ecosystem)` keys.

## Existing Tool Considered
Alternatives check on #7385 recorded verdict `none`: external OSV scanners (`osv-scanner`, `cve-lite-cli`) do not read `.devops/research-watch.toml` or map `osv_ecosystem`/`osv_name` onto container/chart pins without lockfiles or SBOMs. The implementation reuses the project's existing `mapped_inventory`, `read_watch_list`, and `OSVClient`.
