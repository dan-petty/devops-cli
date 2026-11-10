# Design

## Decisions

- **Run Gitleaks once over the materialized scratch directory for list targets**: `GitleaksScanner.scan` delegates list targets to `super().scan(files, isolated=True)` instead of looping over files. This eliminates N separate sandbox initializations and runs Gitleaks once.
- **Materialize targets using `materialize_targets`**: `isolated_targets` links or copies reviewed files into the isolated temporary directory. Files that resolve outside the tree are excluded.
- **Map finding locations back to reviewed files**: `_parse_materialized_output` resolves finding file paths against `MaterializedTargets.origins`. It replaces scratch directory locations with the original reviewed file paths.
- **Filter findings to reviewed files**: Findings on isolation files (`gitleaks.toml`, `.gitleaksignore`) in the scratch directory are excluded. Only findings matching scannable target files are retained.
- **Map scratch directory to `{targets}` in command template**: In `src/devops_cli/security/tool_executor.py`, include `base` in target placeholders when `request.cwd` is set. This ensures the command argument matching `workdir` becomes `{targets}` in the recorded `argv_template`.
- **Pass `tree` from review pipeline to `run_gitleaks_scan`**: `_scan_static_analysis` passes `tree=tree` through `_call_scanner_helper` to `_scan_secrets`. `run_gitleaks_scan` accepts `tree` and passes it to `GitleaksScanner.scan`.

## Rejected alternatives

- **Keep per-file scans and parallelize them**: Running N sandbox processes in parallel increases CPU and memory consumption. Each sandbox setup has overhead. Running one scan over a directory is faster and uses fewer resources.
- **Pass all file paths directly to `gitleaks dir`**: Gitleaks `dir` accepts a single directory or file path argument. It does not accept multiple separate file arguments.
- **Scan the entire repository checkout**: A review often checks a subset of files from a pull request or path. Scanning the whole repository runs rules over unreviewed files and takes more time.
- **Remap paths in the review pipeline only**: Mapping paths inside `GitleaksScanner.parse_output` ensures any caller of `run_gitleaks_scan` receives findings with valid file locations.
