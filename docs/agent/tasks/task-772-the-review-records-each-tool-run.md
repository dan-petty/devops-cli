# Task: The Review Records Each Tool Run, Part C: the Record Reaches the Profile and the Report (#772)

**Issue**: [#772](https://github.com/dan-petty/devops-cli/issues/772)
**Scope**: scope/security, scope/review
**Feasibility**: I ran the eight real review tools under `strace` over one small git tree. The tree held a decoy config file for each tool. I read which files each tool opened. Then I ran the same eight scans through the new recording executor with the real tools. Every tool ran, and each record named the files that `strace` showed. I read the SARIF export of the review, `ToolRun`, and the schema rules of SARIF 2.1.0 to decide the SARIF mapping. The section "Checked against the real system" has the details.

## Description

Issue #772 is too large for one pull request, so four parts deliver it. Part A added the seam. Part B moved the scanners and the review pipeline onto the seam. Part C records the runs, and Part D switches the sandbox on.

Before this part, each executor built a `ToolRun`, and nothing read it. This part carries each record to the review. The review profile and `review.md` show it. The record also names the files that the tool reads, so its two digests mean something.

### What a review does now

- `ReviewPipelineOrchestrator` wraps its executor in a `RecordingToolExecutor`. Each scanner, the evidence scan of Ruff and the scan of the base revision start their tool through it. The recorder keeps the `ToolRun` of every run, in the order the runs start.
- `ReviewProfile.tool_runs` holds one row for each run. A row holds nine values. They are the tool, its version, the digest of its binary and how it ran. The rest are the config digest, the ruleset digest, the argument template, the targets digest and the commit.
- `review.md` has a "Tool Runs" table. It holds one row for each distinct record and counts its runs. Gitleaks scans one file at a time, so one row can stand for hundreds of runs. `profile.json` keeps each record.
- `SECURITY.md` states the limits of each executor. `docs/SELF_IMPROVEMENT.md` describes the record and lists the files that each tool reads.

### Decisions

- The recorder wraps the executor. It does not travel on the `ScanOutcome`. Five places rebuild an outcome and lose what it carries: `merge_outcomes`, the test filter of Gitleaks, the advisory filter of Ruff, `_registry_rules_missing` and `_batch_outcome`. The Ruff evidence scan and the scan of the base revision never reach `_observe_outcome`. The executor sees each run at the one place where it starts.
- `ToolRun` has one new field, `executor`. A reader needs it to see whether a run was confined. Its values are `direct`, `sandbox` and, in tests, `fake`. Part D can add a field for the popeye network profile, which the issue asks for.
- The direct executor must not fail a scan for a record. It already records no commit for a checkout that git cannot read. It now records the digest `unavailable` for a config file or a ruleset file that it cannot read as a regular file. The sandbox executor and the fake keep refusing such a file. The sandbox must bind the file.
- A request names the config files of a scan in two ways. A review hands most tools their own config file in a scratch directory. The scanner declares the file in `isolation_files`, and the request names it. The digest covers the content, so the scratch path does not matter. Ruff and osv-scanner find a config file of their own in the tree. The scanner declares the names in `config_names`, and `config_search_upward` says whether the tool looks above the directory of the target. The names are in `config/constants.py`.
- A scanner names its ruleset files in `ruleset_files`. Semgrep names the rule pack of devops-cli, which `discover_pack_rules` lists, and each file that a `--config` names from the directory where it starts. Trivy names the metadata file of its checks bundle for a `config` scan, and the metadata file of its vulnerability database for any other scan. A tool whose rules are in its binary names none. Its version and binary digest name the rules.
- The scanner finds the files after the check for a test patch, in `_run_tool`. A test that patches `run_subprocess` with an odd target does not reach the code.
- The argument template holds a placeholder where the command names a path. `{targets}` stands for the targets, `{config}` for a config file and `{ruleset}` for a ruleset file or a rule pack. Before this change the template held the paths of the reviewed files and of a scratch directory that differs in each run. Two runs of one scan could not record the same template. Adjacent placeholders of one kind stand once.
- A record is read before the tool starts. A tool that fetches its rules during the run, such as Trivy with an old cache, may use newer rules than the record names. The docs say so. Part D moves the fetch outside the sandbox.
- The record stays. The Part B bullet "a scan that needs no record skips it" no longer applies: the profile and the report read the record now. The cost stays low. A scan of 300 Python files adds about 30 ms to find the config files of Ruff, once for each run of Ruff.
- Trivy keeps its cache in `TRIVY_CACHE_DIR` or in the user cache directory of the platform. `platformdirs` names that directory as Go does for Trivy. It is a new direct dependency. It was in `uv.lock` already, for FastMCP.
- The default executor stays `DirectToolExecutor`. Part D switches the sandbox on.

### Checked against the real system

- I ran the eight tools under `strace -f` and read each file that each tool opened. A review hands the tool its config file in a scratch directory, and runs the tool from there. The table lists what each tool read.

| Tool | Config files it read | Ruleset files it read |
| :--- | :--- | :--- |
| Bandit 1.9.4 | the `.bandit` that devops-cli hands it. Not the `.bandit` of the tree. | none: the rules are plugins of the package |
| Gitleaks 8.30.1 | the handed `gitleaks.toml` and `.gitleaksignore`. Not the `.gitleaks.toml` of the tree. | none: the default rules are in the binary |
| Semgrep 1.179.0 | none. It reads `~/.semgrep/settings.yml`, which is state and not config. It applies no `.semgrepignore` to a file named on the command line. | the rule pack of devops-cli, and the copy of the registry ruleset in the scratch directory |
| Trivy 0.75.0 | the handed `trivy.yaml` and `.trivyignore` | for `config`: `policy/metadata.json` and the Rego files of `policy/content` in the cache. It did not open `db/`. |
| kube-linter 0.8.3 | the handed `kube-linter.yaml` | none: the checks are in the binary |
| Pluto 5.24.4 | none | none: the deprecated APIs are in the binary |
| osv-scanner 2.6.0 | `osv-scanner.toml` in the directory of the lockfile, from the tree | none yet: it tried to open `~/.cache/osv-scalibr/npm/all.zip`, which has no metadata file |
| Ruff 0.16.8 | `pyproject.toml` and `ruff.toml` of the tree, and files above the tree and in the user config directory (see below) | none: the rules are in the binary |

- osv-scanner reads `osv-scanner.toml` from the directory of its lockfile only. I put config files one and two directories above a lockfile. It looked for the file in the directory of the lockfile and nowhere else.
- Ruff reads the nearest `.ruff.toml` or `ruff.toml` above the file that it checks. It also read the nearest `pyproject.toml` above the file, also when a nearer `.ruff.toml` held the settings. So the request names every candidate from the directory of the file up to the tree. Ruff does not stop at the tree. It applied a `ruff.toml` in a directory above the tree. When no project config file existed, it applied `ruff/ruff.toml` in `$XDG_CONFIG_HOME`. A request does not name these two files. The sandbox executor binds each file that a request names outside the tree, so Ruff would read it there. While the direct executor runs, the config digest of Ruff does not cover a config file above the tree or in the user config directory.
- `ruff check --show-settings` prints the settings path, but only for the first file that I gave it. A review gives Ruff many files, and a second start of the tool for each scan needs its own request and record. So the scanner uses the names that the Ruff documentation gives.
- Ruff writes `.ruff_cache` into the reviewed tree. The sandbox of Part D binds the tree read-only, so Part D must give Ruff a cache directory outside the tree.
- I ran the eight real scans through a `RecordingToolExecutor` over `DirectToolExecutor`. Every tool ran with `executor` set to `direct`. The osv-scanner scan failed, as it did before this change, because the host has no OSV database. The templates held no path. Pluto had two empty digests. Trivy had a ruleset digest, and Ruff had a config digest.
- The binary digest of Bandit and Semgrep names a launcher script of 320 and 379 bytes. It does not name the package. The version from the tools lock names the package. Part A built this digest, and this part leaves it as it is.
- Import cost: `ReviewProfile` now imports `ToolRun`. `len(sys.modules)` after `devops review --help` rises from 918 to 920.
- SARIF: the review writes `findings.sarif` with `to_sarif`, which builds the dicts by hand. No SARIF library is a dependency. A mapping of the records does not fit the export. SARIF requires `invocation.executionSuccessful`, and a `ToolRun` holds no exit code. SARIF requires `versionControlProvenance.repositoryUri`, and a `ToolRun` holds no repository. The group digests are not file hashes. `to_sarif` also writes a run only for a tool that has a finding. A run for a clean tool would close the open alerts of that tool in code scanning. A person decides that change. One fact maps without a change: the binary hash, as an artifact with the role `driver`. That one fact does not justify a half-mapped export.
- Mutations: the tests fail when I change the code in any of these ways. I restored the code after each run:
  - The recorder keeps no record, swallows a refused request, or changes the answer of the executor.
  - The scanner does not name its handed config files, the config files that Ruff or osv-scanner find, or its ruleset files. Semgrep drops the rule pack or the file of its `--config`. Trivy names no metadata file, names a file that does not exist, or reads the checks bundle for every scan.
  - The search for the config file of Ruff does not go up, goes above the tree, or osv-scanner looks above the directory of the lockfile.
  - A digest follows the path of a file, or the digest of no files is an empty string.
  - The template is the raw command, keeps the targets that a scratch directory names, or does not join adjacent placeholders.
  - The direct executor requires its files, or names the sandbox.
  - The profile gets no rows, requires its rows, or loses the executor when written. The report has no table, prints an empty table, leaves out a column, or counts each run on its own row.
  - The scan of the base revision does not use the executor of the orchestrator.
  - Semgrep reads the registry ruleset from the cache directory in a review, drops the ruleset of the scan, or looks for its file from the directory of the process.
  - The direct executor requires a ruleset file, a ruleset file wins over a target in the template, Ruff over a directory looks beside it, a pipe in a cell is not escaped, or a record may name no executor.

### Existing tool considered

- `strace` gave the survey of the files. `collections.Counter` groups the rows. Pydantic v2 holds the models. `run_store.digest` and `file_digest` make the digests. `discover_pack_rules` lists the rule pack. `os.path.normpath` compares the paths. `platformdirs` finds the cache directory of Trivy. No new code does their work.
- `ruff check --show-settings` could ask Ruff for its config file. I rejected it. It names one file for a start, and it needs a second start of the tool.
- No open tool covers a recording wrapper for a Python protocol, or a template of a command with placeholders. I built both. The wrapper has 20 lines, `_argv_template` has 35 lines, and `tool_runs.py` has 70 lines.
- Cost of the build: this part needed about 500,000 tokens (measured with the counter of the session). Most of it went to the survey and to reading code. It needed about three hours of agent time (estimate). The maintenance is the three functions above, and the `config_names` of Ruff and osv-scanner. They change when a tool changes the files that it reads.

## Acceptance Criteria

- [x] Each `ToolRun` reaches the review. The orchestrator keeps the records, and `ReviewProfile.tool_runs` holds one row for each run with every field. `test_a_review_profile_holds_one_row_per_tool_run_with_every_field` asserts it, and `test_the_scan_of_the_base_revision_adds_its_rows_with_no_commit` asserts the scan of the base revision.
- [x] A record names how the tool ran. `test_each_executor_names_itself_in_the_record_of_its_run`, `test_the_sandbox_names_itself_in_the_record_of_its_run` and `test_a_record_that_names_no_executor_is_no_record` assert it.
- [x] `review.md` shows a "Tool Runs" table with one row for each distinct record and the number of its runs. `test_the_report_shows_a_row_for_each_distinct_record_and_counts_its_runs` asserts it. `test_a_report_of_a_review_that_ran_no_tool_has_no_tool_runs_section` asserts the empty case. `test_a_pipe_in_a_record_does_not_split_its_row_in_the_report` asserts that a pipe stays in its cell.
- [x] A request names the config files and the ruleset files that its tool reads, for each of the eight review tools. `test_each_review_scan_names_the_config_files_and_the_ruleset_files_its_tool_reads` asserts the table above. A tool that reads none names none. `test_semgrep_names_the_registry_ruleset_that_a_review_writes_to_its_scratch_directory` and `test_semgrep_outside_a_review_names_the_registry_ruleset_in_the_cache_directory` assert the cached registry ruleset of Semgrep.
- [x] The digests follow the content of the files. `test_a_changed_config_file_of_the_tree_changes_the_config_digest`, `test_a_config_that_devops_cli_hands_the_tool_gives_one_digest_that_follows_its_content` and `test_a_changed_ruleset_file_changes_the_ruleset_digest` assert it, also for a scratch path that differs in each run. `test_the_ruleset_digest_of_a_semgrep_scan_follows_the_bytes_of_the_registry_ruleset` asserts it for the registry ruleset.
- [x] Ruff names its config files from the directory of each file up to the tree. osv-scanner names the config file beside each lockfile. Trivy names the metadata file of the checks bundle or of the database. `test_ruff_names_every_config_file_it_may_read_from_the_nearest_directory_up_to_the_tree`, `test_ruff_over_a_directory_looks_for_its_config_file_in_that_directory`, `test_osv_scanner_names_the_config_file_beside_each_lockfile_and_none_above_it`, `test_a_scan_that_is_no_config_scan_reads_the_metadata_of_the_trivy_database` and `test_a_trivy_without_a_cache_reads_no_ruleset_file` assert it.
- [x] The argument template holds no path and counts no file. `test_the_argument_template_of_a_record_holds_no_path`, `test_the_argument_template_marks_where_the_targets_and_the_files_of_a_scan_stand` and `test_the_files_that_a_command_names_one_after_the_other_stand_once_in_the_template` assert it. `test_a_path_that_is_a_target_and_a_file_the_tool_reads_stands_as_a_target_in_the_template` asserts that a target wins over a file.
- [x] A record does not fail a scan. The direct executor records `unavailable` for a file that it cannot read, and the recorder passes the answer of the executor on. `test_the_direct_executor_records_a_file_it_cannot_digest_and_still_starts_the_tool` (for a config file and for a ruleset file), `test_the_recording_executor_answers_as_the_executor_it_wraps_and_keeps_each_record` and `test_a_request_that_the_executor_refuses_leaves_no_record` assert it.
- [x] `SECURITY.md` states the limits of the direct and the sandbox executor. `docs/SELF_IMPROVEMENT.md` describes the record and the files that each tool reads. `docs/TESTING.md` names the recorder and the name of the fake.
- Not done: the SARIF export lists the records with the names of SARIF 2.1.0. A person first decides whether a clean tool gets a run. A record also needs the exit code of the run (a later Part of #772).
- Not done: the ruleset digest of osv-scanner. The OSV database has no metadata file, and a fetch step before the sandboxed run places it. The fetch step is part of Part D (a later Part of #772).
- Not done: the binary digest of a Python tool names the package and not its launcher script (a later Part of #772).
- Not done: Ruff gets a cache directory outside the tree. The sandbox also binds the cache of Trivy and the database of osv-scanner. A later Part of #772 does this, with the part that switches the sandbox on.
- Not done: a scan outside a review lets its tool find the config of the tree. Its record names only the files that devops-cli hands the tool. Nobody reads the record of such a scan (a later Part of #772).
- Not done: mypy and the canary runner take a `ToolExecutor`. No module probes `Path.cwd()`. `scanner_fake` is rebuilt over the executor fake. The sandbox executor becomes the production default. `task-772-the-review-scanners-run-through-the-tool-executor.md` keeps these bullets (a later Part of #772).
- Not done: the config digest of Ruff covers a config file above the tree and the user config file of Ruff. The direct executor does not record them, and Ruff applies them. The sandbox of Part D decides what Ruff can see, and the request then names what it binds (a later Part of #772).
- Not done: `src/devops_cli/review/canary.py` writes the digest `unavailable` for a missing binary as a literal. It takes `CONST_TOOL_DIGEST_UNAVAILABLE` in a later part that edits that module (a later Part of #772).
- Not done: `changelog.d/772.md` (the closing Part of #772 adds it).
- Pending a person: run `devops review path` over one small tree with the release tip and with this change. Compare the table of static analyzers and the new Tool Runs table in the two `review.md` files. A full review also calls a model, and an agent does not run it.
- Pending a person: decide whether a review hands osv-scanner and Ruff their own config file. Both read the config file of the reviewed tree, so a change under review can set their rules. A review hands every other tool its own file (#972). A config file handed to Ruff would also end its search for a config file above the tree and in the user config directory, so the config digest would then cover all that Ruff reads.
