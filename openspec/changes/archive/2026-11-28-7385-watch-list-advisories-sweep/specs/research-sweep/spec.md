## ADDED Requirements

### Requirement: Sweep reads mapped inventory and watch list
`devops research sweep` SHALL build its inventory with `mapped_inventory`, read `.devops/research-watch.toml`, pass `watch` to `sweep_dry_run` for `--dry-run` and to `find_advisories` for real runs, and pass the findings through `run_sweep` to `record_open_findings`.

#### Scenario: Sweep checks mapped watch entries and records critical findings
- **WHEN** `devops research sweep` runs on a repository with a `[[watch]]` entry carrying an `osv_ecosystem` and `osv_name` or a `repo`
- **THEN** `find_advisories` receives the mapped inventory and parsed `WatchList`, and `record_open_findings` records the severities from `run_sweep`

#### Scenario: Sweep dry run lists OSV and GitHub requests for the watch list
- **WHEN** `devops research sweep --dry-run` runs on a repository with a `[[watch]]` entry carrying `osv_ecosystem`, `osv_name`, and `repo`
- **THEN** the dry-run requests list both `api.osv.dev/v1/querybatch` and the repository `security-advisories` endpoint
