# Design

## Context

The review orchestrator, the review runner and the security scanners read the working directory of the process in 11 places. A test that gave the orchestrator a temporary workspace still had its scanners resolve paths against the checkout that pytest runs in, and a review started outside the reviewed checkout named some findings wrong. The command layer is the one place that knows the directory that the user starts a command in. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- No module under `src/devops_cli/ai/review/`, `src/devops_cli/review/` or `src/devops_cli/security/` reads `Path.cwd()` or `os.getcwd()`, and a rule holds this.
- The orchestrator takes its workspace and its tool executor through its constructor alone.
- A rule that reads the working directory keeps its meaning: the command gives the directory.
- The review tests give the orchestrator the executor fake, and the root conftest wraps no executor.

**Non-Goals:**

- The enrichers of a review, the threat-intel lookups of Shodan and Cloudflare Radar, through the constructor. See Decisions.
- A read of the working directory through a default of a helper in `core/repo`, such as `get_repo_origin_name()` for the repository of a PR review, and the relative `.` default of a scanner entry point. These modules are outside the rule. See Workflow follow-up in tasks.md.
- The sandbox as the default executor (#2096).

## Decisions

- **The workspace is a path, not a file-system object.** The orchestrator takes `target_dir`, and finds the reviewed tree, the files and their siblings, the manifests and the review config from it. docs/TESTING.md makes the filesystem under `tmp_path` real, so a test gives a temporary directory. Rejected: a `ReviewWorkspace` protocol with list and read methods. It would be a second seam for an edge that the test conventions do not double, and every reader in the pipeline would change for no test that needs it.
- **The constructor is the one place for the workspace.** `run_pre_analysis_refresh` and `init_per_file_payloads` lost their `target_dir`, which reset the attribute that the constructor set. `_run_profiled_session` and `_run_orchestrator_review` lost theirs too. The layer test of #1100 now also checks that no stage takes a `target_dir`.
- **A boundary keeps its rule, and the command gives the directory.** The review boundary allows a target under the working directory, the repository that holds it, the repository of the target and the repos base directory. `_is_allowed_review_boundary`, `_prepare_path_content` and `_prepare_branch_content` take `working_directory`. The feedback export allows a reviews directory and an output path under the workspace, the data root and the temporary directory, and `export_invalidated_feedback` takes `workspace_root`. In each case the command gives `Path.cwd()`, so the command keeps its behavior. Rejected: a default of the working directory in these functions, which is the read that this change removes.
- **The session directory check drops the working directory.** No caller under `src/` gives the orchestrator a `session_dir`: a review writes its session in the reviews directory. A test gives a directory under `tmp_path`, inside the temporary directory. So the allowed roots are the reviews directory and the temporary directory, which is stricter. Rejected: a working directory through the constructor only for this check.
- **A scanner finds its directory from its targets or its caller.** Kube-linter names a manifest relative to the working tree that holds the manifest (`find_worktree_root` of the manifest). From inside the checkout, this is the old name. From outside, the old name was the file name alone, and the review lost the finding from the payload of the manifest. `run_mypy_scan` and `run_osv_scan` require `tree`, which every caller gives. `run_popeye_scan` requires `workdir`: Popeye reads the cluster and needs a directory to start in only. `relativize_scan_path` requires its root, and a path outside it stays absolute: every caller gives the scanned tree. A scan that is not isolated starts in the nearest directory that holds its targets. A relative target, such as an image name, is a path relative to the directory of the caller, so the scan of an image starts there, as before. A scan with no target starts in the temporary directory. Rejected: a temporary directory for every target that names no file. Trivy then no longer reads the `.trivyignore` of the directory that a user runs `devops scan trivy <image>` in.
- **The rule is an ast-grep rule.** ast-grep already holds the network constructs of `src/` and the elapsed-time bounds of `tests/` in the `constructs` row and in the `ast-grep-scan` commit hook. The rule `review-cwd-read` names the three packages in `files`, and matches the attributes `Path.cwd`, `pathlib.Path.cwd`, `os.getcwd` and `os.getcwdb`, and a call of a bare `getcwd`. Rejected: an AST walk in `tests/test_architectural_invariants.py`. It would be a second mechanism for a construct rule, and only the full gate would run it.
- **The scanner fake answers the canaries.** A review runs the canary of each tool on its own executor (#1978). `ScannerFake` answers a run in a working directory named with `CONST_CANARY_WORKDIR_PREFIX` with the recorded canary output, keeps it in `canaries.requests`, and keeps it out of `runs` and `requests`. The `scanner_fake` fixture sends a canary run of `DirectToolExecutor` to the fake too. Rejected: a plain `ToolExecutorFake` scripted with the canary outputs for every test. It answers a request by its tool, so a scan of Bandit or Semgrep would get the canary output of the tool. A test whose scans reach a patched `run_subprocess` uses `recorded_canary_answers()`, which is that plain fake, because no scan reaches it.
- **Enrichers stay out of this change.** The only enrichers are the threat-intel lookups, which the orchestrator builds when `threat_intel` is true. No caller under `src/` sets it, the three named tests never reach it, and the lookups build their own HTTP clients until #1381. A constructor parameter for them needs a fake of that HTTP edge, and docs/TESTING.md asks a contract suite of every fake. That is a change of its own.

## Risks / Trade-offs

- [The working directory still reaches a scanner through a relative target, which pathlib resolves.] → The caller gives the target, and the review gives absolute paths. The rule holds the explicit reads, which were defaults that no caller asked for.
- [A test that builds an orchestrator and gives it no fake starts a real canary.] → The floor refuses a real scanner at `subprocess.Popen` and fails the test with a message that names the fake to use.
