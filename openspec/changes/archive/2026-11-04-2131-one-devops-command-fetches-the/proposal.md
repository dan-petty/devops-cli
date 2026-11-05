# Proposal

## Why

Issue #2131: a review runs osv-scanner and Trivy in a sandbox with no network (#2096). The sandbox binds their databases read-only. No devops command fetches those databases. Without them, osv-scanner gives no advisory, and Trivy gives no finding on a new host. Today the scan then reports no finding, or a failure, and the report does not say what to do.

The issue asks for two results:

- One devops command fetches the osv-scanner offline databases and the Trivy database and checks, outside the sandbox, into the directories that the review binds read-only.
- A review that finds a database missing or older than its limit reports a coverage gap that names the command.

## What Changes

- New command `devops review fetch-databases [PATH]`. It starts the tools outside the sandbox, as `devops review rules fetch` is the one step that reaches the Semgrep registry:
  - `osv-scanner scan source --offline-vulnerabilities --download-offline-databases --format json` over the lockfiles of `PATH`. osv-scanner fetches the database of each ecosystem that the lockfiles use.
  - `trivy fs --download-db-only` for the Trivy vulnerability database, and `trivy config` over an empty directory for the Trivy checks bundle.
  - Each tool gets the directory variable of `OsvScanner.data_dirs()` and `TrivyScanner.data_dirs()`. So the command writes exactly the directories that the sandbox binds.
  - `--dry-run` lists the commands and the directories, and starts nothing.
- A run of osv-scanner or Trivy in the sandbox that stops for want of its database gives a coverage gap whose reason names `devops review fetch-databases`. osv-scanner gives the gap for the error `no offline version of the OSV database is available`. Trivy gives it for the error `failed to download vulnerability DB`, which it also gives when its database is past its `NextUpdate`.
- A run of osv-scanner whose database for an ecosystem of the report is older than 24 hours (`CONST_OSV_OFFLINE_DB_TTL_SECONDS`) gives a coverage gap that names the command. The gap keeps the findings. The command sets the modified time of each database file that it confirmed, because osv-scanner rewrites no file that did not change.
- A file is a lockfile for osv-scanner only when its name is in `CONST_LOCKFILE_NAMES`. A file such as `rules.lock` stops osv-scanner with exit code 127, and the fetch names the same lockfiles as the scan.
- The command is a new observable behavior, so the change has a spec delta: the new capability `review-tool-databases`.
- `docs/SELF_IMPROVEMENT.md`, `SECURITY.md` and the generated command documents say the fetch step.
- The change fits one pull request.

## Acceptance

- Criterion 1, the command fetches both databases into the directories that the review binds: group 2 and group 3. A scan in the sandbox then reads them with no network, because the directories are the ones that `data_dirs()` names.
- Criterion 2, a review with no database reports a coverage gap that names the command: group 1.

## Feasibility

All commands ran on 2026-11-04 on `origin/main` with osv-scanner 2.6.0 and Trivy 0.75.0, which `tools.lock` pins.

- The directories are known. `OsvScanner.data_dirs()` binds `osv-scalibr` below `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY`, else below the user cache directory. `TrivyScanner.data_dirs()` binds `TRIVY_CACHE_DIR`, else `~/.cache/trivy`. This answers the first open question of the issue.
- osv-scanner fetches the database of the ecosystems that it meets. `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=<scratch> osv-scanner scan source --offline-vulnerabilities --download-offline-databases --lockfile requirements.txt` wrote `<scratch>/osv-scalibr/PyPI/all.zip` (37630473 bytes), and nothing for another ecosystem. There is no flag that fetches every ecosystem, so the command reads the lockfiles of a tree.
- The exit code of that run is 1 when the lockfile has a vulnerable package (`requests==2.0.0`), and 0 when it has none. So the fetch cannot take exit 1 as a failure. It takes 0 and 1 as success and reads the report, which names the ecosystems. A second run with a current database exits 0 and leaves the modified time of `all.zip` as it was (`ls -l --time-style=full-iso` before and after). So the age of a database cannot come from the modified time alone, and the command sets it after a run.
- With no database, osv-scanner scans `requirements.txt`, prints `could not load db for PyPI ecosystem: unable to fetch OSV database: no offline version of the OSV database is available` on stderr, exits 127, and still prints a JSON report that has the package and no vulnerability. So today the scan can read as clean. This is why the gap must come from the error.
- The report names an ecosystem only with `--all-packages`. Without it, `results[].packages` holds the vulnerable packages only, so a clean lockfile names no ecosystem. The fetch command and the scan both use the flag.
- A file that ends in `.lock` can stop the fetch. `OsvScanner` takes every file that ends in `.lock` or `.lockb` as a lockfile. `osv-scanner scan source --offline-vulnerabilities --download-offline-databases --lockfile uv.lock --lockfile src/devops_cli/review/rules/rules.lock` printed `could not determine extractor suitable to this file` and exited with 127, in a checkout of devops-cli. The `rules.lock` of devops-cli is no lockfile. So `_is_lockfile` takes a file by its name in `CONST_LOCKFILE_NAMES` alone, and the fetch and the scan of `OsvScanner` use the same list (`lockfiles_of`). The review pipeline has the same suffix rule for the lockfiles that it hands to osv-scanner (`_classify_scanner_files`). That is a separate defect with its own fix: issue #3536.
- Trivy fetches the database alone. `TRIVY_CACHE_DIR=<scratch> trivy fs --download-db-only` wrote `<scratch>/db/metadata.json` and `<scratch>/db/trivy.db`. `TRIVY_CACHE_DIR=<scratch> trivy config <empty directory>` wrote `<scratch>/policy/metadata.json` and the bundle.
- With no database and no network, Trivy stops with `DB error: failed to download vulnerability DB` and exit 1 (`--db-repository` set to a closed local port). With `--skip-db-update` and no database it stops with `--skip-db-update cannot be specified on the first run`. The sandbox cannot reach a registry, so a database past its `NextUpdate` gives the first error as well. Trivy owns the age limit of its database.
- A scan with the checks bundle missing works: `trivy config` uses the checks in the binary (`data_dirs()` already says so).
- Nothing newer did this work. `git grep -n "download-offline-databases\|download-db-only" -- src` finds only a comment in `constants.py`. The open-issue search finds only #2131 and its tracker #772.

## Existing Tool Considered

- `osv-scanner --download-offline-databases` and `trivy --download-db-only` are the fetch steps of the tools. The command starts them through `run_subprocess` and writes no downloader of its own.
- `devops review rules fetch` is the model for the command, the dry run and the coverage gap that names the command (`_registry_rules_missing` in `src/devops_cli/security/semgrep.py`).
- `BaseSecurityScanner.coverage_gap` is the existing hook for a run that stopped for a cause outside the tool (#2129).
- `json` from the standard library reads the report of osv-scanner. No new dependency.
- Code removed: none. The comment in `constants.py` that says the database was fetched by hand on 2026-10-24 stays true.
- Cost: about 250 lines of source and 300 lines of tests. No maintenance tool is built: the two upstream tools do the download.
