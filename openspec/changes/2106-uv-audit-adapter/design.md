# Design

## Decisions

- **The adapter is a `BaseSecurityScanner`.** It gets the pre-flight checks (dry run, a missing program), the `ToolExecutor` seam with an empty standard input, the timeout and the reading of the exit code and the JSON output that every other adapter gets. `run_uv_audit_scan(target, tool_executor=None)` has the shape of `run_kubelinter_scan`, so `_run_adapter_scan` of the agent tools calls it as it calls the others.
- **uv starts in the scanned directory.** uv finds the project from its working directory, and `BaseSecurityScanner._resolve_cwd` starts a scan in the directory of its target. The command names no path.
- **`--frozen`.** The scan audits the lockfile as it is, and never writes the tree. Without the flag, uv 0.12.23 rewrote a stale `uv.lock` before the audit.
- **`--quiet`.** uv writes two preview warnings on stderr in each run, about 270 characters, before an error. The reason of a failed `ScanOutcome` is cut at 256 characters, so without the flag the reason never showed the error. With the flag, uv still writes the report and the error.
- **The JSON report, read with Pydantic models.** The models hold the fields that the adapter reads, and ignore the others, such as `aliases` and `published`. uv writes the `vulnerabilities` and `adverse_statuses` lists in each project report, also when they are empty, so the models require both. A report that does not match the models raises in `parse_output`, and `BaseSecurityScanner` gives a `failed` outcome with the error as the reason. Thus a change of the preview schema of uv gives a failed scan, and not a clean scan.
- **The default severity.** uv gives no severity in the JSON report, and its SARIF report gives the level `error` to each result. The finding model accepts only `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` and `INFO`, and gives `MEDIUM` to any other value. The adapter gives no severity, so each finding is `MEDIUM`, as each finding of the kube-linter adapter is.
- **Adverse statuses are findings.** uv reports them in the same report as the vulnerabilities. uv exits 0 when it finds only adverse statuses, but a project that its index quarantines is a supply-chain risk that the agent must see.
- **The location is `uv.lock:<package>`.** The JSON report names no path. The lockfile is the `uv.lock` of the project that uv found from the scanned directory. Trivy names a package of a lockfile in the same form.
- **The scanner registry does not hold the adapter.** A review runs the scanners of the registry in a sandbox with no network (`SECURITY.md`), and uv audit queries OSV over the network. osv-scanner audits the lockfiles of a review from its offline database. The agent tools run their scans on `DirectToolExecutor`, which has the network.

## Rejected alternatives

- **Keep `requirements_file` and pass it to `--script`.** `--script` audits a PEP 723 script that `uv lock --script` locked. A requirements file is not such a script. uv 0.12.23 and 0.13.6 have no option that audits a requirements file.
- **Run `uvx pip-audit -r <file>` for a requirements file.** pip-audit is not in `tools.lock`, and `uvx` fetches it from PyPI each time. The issue asks for uv audit only.
- **Run the command of the issue, `uv audit --output-format json`, with no other flag.** It rewrites a stale `uv.lock`, and the reason of a failed run holds only the preview warnings. The two flags keep the scan read-only and its reason useful.
- **`--locked` in place of `--frozen`.** `--locked` refuses a stale lockfile, so the scan gives no result for a project whose `pyproject.toml` changed after the last lock. `--frozen` audits the versions that the lockfile pins, which `uv sync --frozen` installs, as osv-scanner audits a lockfile.
- **The SARIF report.** It gives the same data with no severity, and the level `error` for each result. The base class and the other adapters read JSON.
- **A severity from OSV for each advisory.** It needs one more request for each advisory. The agent can look up an advisory with `scan_osv`.
- **A severity for each adverse status, such as `HIGH` for `quarantined`.** uv gives none, and the adapter does not make one.
- **The `audit` check of `devops ci` runs `build_uv_audit_cmd`.** The check reads only the exit status of `uv audit`, and prints its text report for a person (`devops_cli.core.dependency_audit`). It needs no JSON report, and this change does not change it.

## Non-goals

- A uv audit scan in a review or in `devops scan report`.
- Severities for the findings of uv audit.
