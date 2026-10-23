# Task: The Review Scanners Run Through the Tool Executor, Part B: the Executor Reaches the Scanners (#772)

**Issue**: [#772](https://github.com/dan-petty/devops-cli/issues/772)
**Scope**: scope/security, scope/review
**Feasibility**: I ran six real scans with the real tools: Bandit, Gitleaks, kube-linter, Pluto, Ruff and Semgrep. They scanned one git tree. I ran them with the code of the release tip and then with this change. The status, the findings and the reason were the same in both runs. The runs differed only in the names of temporary directories and in a time that Gitleaks prints. I also ran 39 scans with stand-in tools through three versions of the code. The section "Checked against the real system" has these checks and the others.

## Description

Issue #772 is too large for one pull request, so four parts deliver it. Part A added the seam. Part B moves the scanners and the review pipeline onto the seam. Part B is also too large for one pull request.

The code and the tests of the first slice change 889 lines, so the work stops at a coherent slice. This pull request delivers that slice. A second pull request of Part B delivers the rest. The bullets "Not done" name it.

A scanner builds the command of its tool. It now hands the command to a `ToolExecutor` as a `ToolRequest`. The executor starts the tool and answers with a `ToolResult`. A scanner that gets no executor starts a `DirectToolExecutor`. That executor starts the tool as a child process, as every scanner did before the seam. So a review runs the same tools in the same way until a later part of #772 switches it to the sandbox.

`ReviewPipelineOrchestrator` takes a `tool_executor`. It keeps one executor for the whole review and gives it to every analyzer: Bandit, kube-linter, Pluto, Trivy, osv-scanner, Gitleaks, Semgrep and Ruff. The scan of the base revision of a branch gets the same executor.

### Decisions

- The default executor is `DirectToolExecutor`. It is the smallest way to keep the behavior. It calls `run_subprocess` with the arguments that the scanners used before. The program is the name of the tool. The directory and the time limit are those of the scan. The tool reads an empty standard input (#1079).
- A scan must end as it ended before the executor existed. The default executor builds a `ToolRun` with `record_tool_run`, as the sandbox executor does. The review profile and `review.md` show the record (Part C). A record is no reason to stop a scan, so the record must never stop one.
- Git cannot read some checkouts. A checkout that another user owns is one example. `record_tool_run` takes `require_commit`. The sandbox executor and the fake keep the default, `True`, and they refuse such a checkout. `DirectToolExecutor` passes `False`. Then the record holds no commit, and the scan runs.
- The record has a cost. Each run reads the commit of the tree with two git commands. They took about 2 ms and 4 ms in this repository. The first run of a tool in a process also reads the binary of the tool for its digest. `_hash_binary_path` in the canary caches the digest for the process. The read took 0.20 s for the 173 MB Trivy binary and less than 0.07 s for each other tool.
- `ToolRequest` has a new field, `cwd`. A review scan starts in a scratch directory outside the tree, so that the tool reads no config file of the tree. `workdir` is the tree. The request needs both. `SandboxToolExecutor` starts the tool in `cwd` and binds a `cwd` outside the tree read-only.
- The tree of a scan is the checkout that holds its targets. If the targets are outside any checkout, the tree is their common directory. A target can name no path. An image name such as `ghcr.io/org/img:latest` is an example. Then the nearest directory that exists replaces the common directory.
- The targets of a request are absolute paths. A relative path stands in the current directory. The targets of an isolated Semgrep scan are the files of the tree, not their links in the scratch directory. The request of osv-scanner names all its lockfiles.
- The request derives its tree from its targets. Some scans take a `tree` argument. A caller can give a tree that does not hold a target. The executor then refuses the request, and a scan fails that did not fail before.
- `BaseSecurityScanner._run_tool` replaces `_run_subprocess`. It builds the request, runs it, and answers as a finished process. So the code that reads the output stays as it was. A result that timed out raises `subprocess.TimeoutExpired`, as the process did.
- Many tests patch `run_subprocess` in `security.base` or in a scanner module. 43 of these patches in 10 test files reach `_patched_run_subprocess`, and #1332 owns their migration. `_patched_run_subprocess` finds the patch. It uses the imported name, so the change adds no `noqa` suppression.
- `_start` in `tool_executor.py` is the one place that starts a command for both executors. It gives the command an empty standard input. The sandbox executor passed the standard input of the caller before. The new case `test_the_sandbox_gives_the_tool_an_empty_standard_input` showed it.
- `SandboxToolExecutor` imports `HostSandbox` when it starts. The sandbox pulls in the container engine, and a scanner that runs directly does not need it.
- Four existing tests gave `subprocess.run` a `MagicMock` with no exit code and no standard error. A `ToolResult` needs an integer and a string. So each mock now has `returncode=0` and `stderr=""`.
- Mypy and the canary stay outside this slice. Mypy starts `python -I -m mypy`, and the interpreter is the `.venv` of the reviewed repository when it has one. A request names a tool, and the executor finds its binary on the PATH of the host. A request cannot name that interpreter yet. The canary builds the same command for mypy. `run_mypy_scan` takes no executor yet, so mypy uses the default executor, also in a review.
- Two review tests set the mypy scan aside with a patch of `run_mypy_scan`, because mypy has no fake yet. The part that moves mypy onto the executor removes the patch.

### Checked against the real system

- Six real tools through the default executor give the same status, findings and reason as the code of the release tip. I ran both with one script. The script is in the scratch directory of the session and is not part of the repository.
- 39 scans with stand-in tools give the same status and reason in the release tip and in this change. The stand-ins are shell scripts with the names of the tools. The scans cover a clean checkout, a new checkout, a checkout that git cannot read and a directory that is no checkout. They also cover two checkouts in one scan, file names with a colon and with a space, links out of the tree and a file that does not exist. The last cases are an empty list, a relative path, an image name, two lockfiles, a tool that fails and a tool that runs out of time.
- The first version of this change failed five of the 39 scans that passed before. It failed three scans of a checkout that git cannot read, a Semgrep review of such a checkout and an image name outside a checkout. The final change fails none. Two tests pin the two causes: `test_a_scan_of_a_checkout_that_git_cannot_read_still_runs` and `test_a_scan_of_an_image_name_outside_a_checkout_runs_in_the_directory_it_started_in`.
- Gitleaks ends a scan that found a secret with exit code 1 and prints no report on standard output. The command has no `--report-path -`. So the scan ends as failed, with no finding, before and after this change. I confirmed it with the command by hand. This change does not touch it.
- `resolve_tool_binary` turns the name of the tool into lower case. A tool named by a path with a capital letter is not found. I checked it with a stand-in. This is one more reason why a request cannot name an interpreter by its path.
- `_hash_binary_path` caches the digest of a binary for the process. Three calls in one process gave one miss and two hits. So the executor needs no cache of its own.
- The floor of the test suite allows git, bubblewrap and the offline renderers of kubectl. It allows no other program. The floor refuses a stand-in that has the name of a locked tool. So the cases for `DirectToolExecutor` start git as the tool.
- Mutations: the tests fail when I change the code in any of these ways. I restored the code after each run:
  - The scanner does not use the executor it is given.
  - The scanner ignores a result that timed out.
  - The scanner drops the exit code, the standard output or the standard error of the result.
  - The default executor refuses a checkout that git cannot read.
  - The request names the scratch directory as the tree.
  - The request names the directory of a file, and not its checkout, as the tree.
  - The request names a directory that does not exist as the tree.
  - The request names a relative path, or the links of Semgrep, as a target.
  - The request of osv-scanner names only its first lockfile.
  - The scan of Gitleaks, the constructor of osv-scanner or the Semgrep helper of the pipeline does not pass the executor on.
  - The orchestrator does not give its executor to the analyzers, to the scan of the base revision or to Ruff.
  - The sandbox executor ignores `cwd`. Either executor passes the standard input of the caller.
  - The direct executor ignores `cwd`, does not replace `{targets}`, or drops the environment of the request.

### Existing tool considered

- `run_subprocess` starts a process. `record_tool_run` builds the record. `resolve_tool_version_and_sha` and `nearest_checkout` find the version and the checkout. Pydantic v2 holds the models. `DirectToolExecutor` and `_run_tool` call them. They do not do the work again.
- No open tool covers a Python protocol with a default implementation. ADR 0007 prescribes the seam.
- Cost of the build: the first slice needed about 360,000 tokens, most of it reading code (measured with the counter of the session). It needed about two hours of agent time (estimate). The fix pass after review needed about 250,000 tokens and about one hour (estimate).
- The maintenance is `DirectToolExecutor` (about 30 lines), `_run_tool` with its two helpers (about 70 lines) and the new fields that the scanners pass on.

## Acceptance Criteria

- [x] The scanners that `BaseSecurityScanner` serves start their tool through a `ToolExecutor`: Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner and Ruff. Checkov, Tflint and Kubeconform use the same base class, and their existing tests pass over the default executor. `test_each_review_scan_starts_its_tool_through_the_executor_it_is_given` runs the eight review scans over the fake.
- [x] A scanner that gets no executor starts `DirectToolExecutor`. The commands and the outcomes stay as they were. `tests/test_scanner_contract.py` holds the recorded commands of the real tools, and it passes with no change. `test_a_scan_of_a_checkout_that_git_cannot_read_still_runs` and `test_a_scan_of_an_image_name_outside_a_checkout_runs_in_the_directory_it_started_in` assert the two cases that failed in the first version.
- [x] `ReviewPipelineOrchestrator` takes a `tool_executor`. It gives the executor to each analyzer, to the evidence scan of Ruff and to the scan of the base revision. `test_a_review_starts_every_analyzer_through_its_executor` and `test_the_scan_of_the_base_revision_starts_its_analyzers_through_the_same_executor` assert it. Both start the review through `init_per_file_payloads`.
- [x] A request names the command, the tree, the directory, the targets and the time limit of the scan. `test_a_request_names_the_command_the_tree_the_directory_and_the_time_of_the_scan`, `test_the_tree_of_a_request_is_the_checkout_that_holds_the_targets` and `test_the_request_of_an_isolated_semgrep_scan_names_the_files_of_the_tree_not_their_links` assert it. `test_a_request_names_every_lockfile_that_osv_scanner_reads` and `test_a_request_names_a_relative_target_by_its_absolute_path` assert the two cases that the first version got wrong.
- [x] A scan reads the exit code, the output and the standard error of the executor. A result that timed out reads as `timed out after <n> s`. `test_a_scan_reads_the_report_a_tool_prints_whatever_its_exit_code_is`, `test_a_scan_of_a_tool_that_failed_says_its_exit_code_and_its_standard_error` and `test_a_scan_whose_tool_runs_out_of_time_says_how_long_it_had` assert it.
- [x] `ToolRequest.cwd` sets the directory where the tool starts. The sandbox executor honors it. `test_the_sandbox_starts_the_tool_in_the_tree_or_in_the_directory_the_request_names` and `test_the_direct_executor_starts_the_tool_with_the_arguments_in_the_directory_of_the_request` assert it.
- [x] Both executors give the tool an empty standard input, never the one of the caller. `test_the_sandbox_gives_the_tool_an_empty_standard_input` and `test_the_direct_executor_gives_the_tool_an_empty_standard_input` assert it.
- [x] `DirectToolExecutor` passes the environment of the request and replaces `{targets}`. It answers a failure of the tool as a result and records the run. It records no commit for a checkout that git cannot read. It refuses a target outside the tree. Six cases in `tests/test_tool_executor_contract.py` assert it.
- [x] `docs/TESTING.md` names the direct executor and the tests that give the scanners the fake.
- Not done: mypy and the canary runner take a `ToolExecutor`. A request must first name a program that is not a tool of the lock. The part that does this also removes the patch of `run_mypy_scan` from two review tests (a later Part of #772).
- Not done: no review or scanner module probes `Path.cwd()`. A new test file holds that rule. The three named pipeline tests pass a temporary workspace and run under 5 seconds (a later Part of #772).
- Not done: `scanner_fake` is rebuilt over the executor fake. Its recordings and `tests/test_scanner_contract.py` stay (a later Part of #772).
- Not done: the sandbox executor becomes the production default (a later Part of #772).
- Not done: `changelog.d/772.md` (the closing Part of #772 adds it).
- Pending a person: run `devops review path` over one small tree with the release tip and with this change. Compare the table of static analyzers in the two `review.md` files. The six-tool check above shows equal scans, but a full review also calls a model, and an agent does not run it.
- Pending a person: decide the fate of the Gitleaks command. It needs `--report-path -` to print its report, or the scan reads no secret. This change does not touch it.
