# Task: Review Tools Run Through One Injectable Executor, Part A: the Executor Seam (#772)

**Issue**: [#772](https://github.com/dan-petty/devops-cli/issues/772)
**Scope**: scope/security, scope/review
**Feasibility**: On this host, bubblewrap 0.13.1 and `prlimit` from util-linux 2.42.4 work together. I ran the command that the executor builds and read the limits and the network inside the sandbox. I checked each claim of the #772 survey on the release tip. I read the SARIF 2.1.0 JSON schema and ran git in three kinds of directory. The section "Checked against the real system" has the details and the mutation runs.

## Description

Issue #772 is too large for one pull request, so four parts deliver it. This is Part A, the seam. A review tool is a program of another project, such as Semgrep or Trivy. Code that runs one builds a `ToolRequest` and calls `ToolExecutor.run`. The answer is a `ToolResult` with the output of the tool and a `ToolRun`, the record of what ran.

`SandboxToolExecutor` is the real executor. It builds one command from three programs that already do the work:

- Bubblewrap, through `HostSandbox`, gives no network, a cleared environment, a read-only tree and read-only inputs, and a private temporary HOME.
- `prlimit` of util-linux sets a CPU limit of 600 seconds and an address space limit of 2 GiB. The environment gets `GOMEMLIMIT=1GiB`, which only Go tools read.
- `run_subprocess` of `core.process` starts the command and ends it at the wall-clock limit, 300 seconds by default.

The executor sets no limit on processes. RLIMIT_NPROC counts every process of the user, so a limit inside the sandbox would starve the host. The module docstring, the constants and `_run_sandbox_process` in `sandbox/host.py` give the reason.

`ToolExecutorFake` is the shared fake. The fake builds its record with the same `record_tool_run` as the real executor. So both refuse a target outside the tree, and both read the digests and the commit from real files and a real git tree. The tests script only the version and the binary digest of the tool, its exit code and its output.

### Checked against the real system

- The command: a script built it with `HostSandbox.build_bwrap_args` and a `prlimit --cpu=7 --as=2147483648 --` prefix, and ran it. Inside the sandbox, `/proc/self/limits` showed an address space limit of 2147483648 bytes and the process limit of the host. `ip link` listed only `lo`.
- The survey: no `ToolExecutor` existed, and no production code started `HostSandbox`. The canary identity helpers were private.
- The kill: `run_subprocess` raises `subprocess.TimeoutExpired` and kills only its direct child. With `--die-with-parent` removed, a child of the tool survived the kill of the sandbox, and the live timeout test failed. So bubblewrap ends the whole tree.
- SARIF: the SARIF 2.1.0 schema gives an artifact the properties `hashes` and `roles`. The roles include `userSpecifiedConfiguration`, `toolSpecifiedConfiguration`, `policy` and `analysisTarget`.
- Git: `git rev-parse --verify --quiet HEAD` exits with 1 in a checkout with no commit. It exits with 128 outside any checkout and in a checkout that git does not trust. A plain `git status` rewrites `.git/index` when the file times are stale. `git --no-optional-locks status` leaves the index as it is.
- Mutations: the contract suite fails when I change the code in any of these ways. I restored the code after each run:
  - The CPU limit or the address space limit ignores the request.
  - The code drops the environment of the request, or lets it win over `GOMEMLIMIT`.
  - The target check compares text, not resolved paths.
  - A digest includes the path of the file, or depends on the order of the files.
  - The code skips the regular file check, the size cap or the check of the tree.
  - The code refreshes the index of the checkout.
  - The code drops the `-dirty` marker, skips untracked files, or reads the status of the whole tree.
  - The code reads a git failure as no commit, raises for a new checkout, or skips the checkout test.

### Decisions

- A request holds the arguments as a template. The element `{targets}` stands for the target paths. `ToolRun.argv_template` records the template, so the record holds no temporary path.
- `ToolRun` holds eight values, because the criterion lists "config and ruleset digests" as two. They are `tool`, `version`, `binary_sha256`, `config_digest`, `ruleset_digest`, `argv_template`, `targets_digest` and `commit`. The names follow SARIF 2.1.0 where it has one, and the module docstring maps them. SARIF holds the three groups of files as `run.artifacts` with `hashes` and `roles`. `ToolRun` keeps one digest for each group, and a later part can map the digests to artifacts.
- The config digest and the ruleset digest are digests of named files. They cover the content, not the paths or the order, so the same rules in two checkouts give the same digest. The executor refuses a file that is missing, is no regular file, or is larger than `DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES`. One file names a ruleset, such as a rule pack or the metadata file of a database. The database itself is bound read-only through `read_only_binds`, and Part D decides how a large database enters the record.
- The targets digest covers the names of the targets relative to the tree. The commit names the content that the checkout holds, and `-dirty` shows that a target differs from it, as `source_commit` does for devops-cli. A tree outside any git checkout, and a checkout with no commit, record no commit. A checkout that git cannot read raises `SandboxError`. `nearest_checkout` of `core/repo.py` is now public, because it tells these cases apart.
- The executor reads the commit with `--no-optional-locks`. A plain `git status` writes the index of the reviewed tree, and a run must not write to it.
- The executor runs `prlimit` by its full path. The sandbox PATH starts with the `.venv/bin` of the reviewed tree. A tree could put its own `prlimit` there and run the tool with no limit.
- A host without bubblewrap, without `prlimit`, or without the tool raises `SandboxError` before anything starts. No new exception class exists.
- The limit values are mine. I did not measure them against the pinned tools. The person-run check below confirms or changes them.
- `resolve_tool_binary` and `resolve_tool_version_and_sha` in `review/canary.py` are now public. The executor and the canary share them.
- `HostSandbox.build_bwrap_args` takes `read_only_binds`. The command prefix needs no change in `host.py`, because the caller passes it as part of `command_args`.
- `tools_lock_digest()` does not fit a `ToolRun`. It digests the whole lock and its requirement files, so any change to any tool changes it. A `ToolRun` names one tool, with its locked version and the digest of its binary. The review profile already records `tools_lock_digest()`.
- `own_source_state()` does not fit either. It describes the checkout of the running devops-cli, not the reviewed tree.
- Seven modules call `git rev-parse HEAD`, each with its own wrapper. The wrappers differ in what they return and how they fail. `_tree_commit` is one more copy. One shared helper is a refactor beyond this Part.

### Existing tool considered

- Bubblewrap, `prlimit`, `run_subprocess`, `HostSandbox`, `run_store.digest`, `is_safe_subpath`, `nearest_checkout`, `load_tools_lock` and pydantic v2 cover confinement, limits, process start, digests, path checks, checkout detection, versions and models. No new code does their work.
- SARIF 2.1.0 names most facts of a `ToolRun`. No SARIF library is a dependency, so the module uses the names only.
- `setrlimit`, `preexec_fn`, a new kill loop and `RLIMIT_NPROC` are not used. `prlimit` and the process namespace of bubblewrap cover them, and AGENTS.md forbids the last one.
- GitPython would give the commit, but it starts `git` itself. That breaks the rule that processes start only through `core/process`.
- A Workspace Protocol is a build with no need. ADR 0007 treats `tmp_path` as real.
- No open tool covers the `ToolExecutor` protocol or its fake. ADR 0007 prescribes both.
- Cost of the build: the three new files hold 47.7 KB, about 12,000 tokens to read (estimate). The first pass took about one hour of agent time, and the fix pass after review took about one hour more (estimate). The maintenance is the 358 lines of `tool_executor.py`, which change when a tool needs a new input kind.

## Acceptance Criteria

- [x] One `ToolExecutor` protocol in `src/devops_cli/security/tool_executor.py`. The tests inject the fake, and `test_the_sandbox_confines_the_tool_to_the_tree_and_the_files_it_needs` asserts the bubblewrap command.
- [x] Production uses `HostSandbox`: `--unshare-all`, `--clearenv`, a read-only tree, a temporary HOME, and the tools, rules and databases read-only. The live test `test_the_tool_sees_no_network_no_host_environment_and_only_read_only_inputs` shows the result inside the sandbox.
- [x] The executor starts processes only through `core/process`. It adds no kill or timeout code. `test_a_tool_that_runs_out_of_time_ends_with_its_whole_process_tree` shows that the child of the tool ends with the sandbox.
- [x] Limits: a CPU limit, a wall-clock limit, an address space limit of at least 2 GiB, and `GOMEMLIMIT`. No limit on processes. `test_the_sandbox_starts_the_tool_under_a_cpu_and_an_address_space_limit` asserts the default limits and the limits of a request. `test_the_environment_of_a_request_reaches_the_tool_but_cannot_lift_the_collector_limit`, `test_the_sandbox_sets_no_limit_on_the_number_of_processes` and `test_the_tool_runs_under_the_limits_and_none_on_processes` assert the rest.
- [x] Each `ToolRun` records the tool, its version, its binary digest, the config digest, the ruleset digest, the argument template, the targets digest and the commit. `test_a_run_records_the_tool_the_files_it_read_and_the_commit` and `test_each_digest_follows_the_content_it_names` assert them.
- [x] The digests cover content, not paths or order. The executor refuses a file that is missing, is no regular file, or is too large. `test_a_digest_names_the_content_of_its_files_not_their_paths_or_order` and `test_a_file_that_cannot_be_digested_is_refused` assert both.
- [x] The executor refuses a target that leaves the tree, also through a link or a `..` path, and a tree that is no directory. `test_a_target_that_leaves_the_tree_is_refused` and `test_a_tree_that_is_no_directory_is_refused` assert it. `test_a_target_that_is_a_link_to_a_place_in_the_tree_is_accepted` is the control.
- [x] The commit shows a dirty target. A new checkout records no commit. A checkout that git cannot read stops the run. A run leaves the index of the tree as it was. `test_the_commit_is_marked_dirty_when_a_target_differs_from_it`, `test_a_checkout_without_a_commit_records_no_commit`, `test_a_checkout_that_git_cannot_read_is_refused_and_not_recorded_as_no_commit` and `test_reading_the_commit_does_not_write_to_the_tree` assert it.
- [x] The fake is in `tests/support/fakes/tool_executor.py`, and `tests/support/bootstrap.py` registers it. The contract suite in `tests/test_tool_executor_contract.py` runs each shared case over the fake and over the real executor. The real side carries the `bwrap` mark and tests skip it where bubblewrap is missing.
- [x] `docs/TESTING.md` names the seam, the fake and the contract suite.
- Not done: the orchestrator takes its workspace, scanners and enrichers through its constructor. No review module probes `Path.cwd()`. The three named pipeline tests run under 5 seconds. A later Part of #772 does this.
- Not done here: the canary runner and mypy take a `ToolExecutor`, and `scanner_fake` is rebuilt over the executor fake (a later Part of #772). The scanners and the review pipeline take the executor in the Part that `task-772-the-review-scanners-run-through-the-tool-executor.md` describes.
- Not done: the `ToolRun` records and the limits in force enter the review profile, `review.md` and `SECURITY.md`. A later Part of #772 does this.
- Not done: the sandboxed executor becomes the production default. A later Part of #772 does this. That part needs the Semgrep registry consumer of #1144. It needs a fetch step for the OSV database and one for the Trivy database. It needs a decision for popeye and a decision for hosts without bubblewrap.
- Not done: `changelog.d/772.md` (the closing Part of #772 adds it).
- Pending a person: run every pinned tool (Semgrep, Bandit, Gitleaks, OSV-Scanner, Trivy, kube-linter and Pluto) through `SandboxToolExecutor` on the loop input with no network. Record the result, including the address space limit of 2 GiB on the Go tools. This run also confirms or changes the floor of the address space limit, which has no measurement behind it yet.
- Pending a person: edit the text of #772 with a mutating roadmap command, because GitHub suspended the machine account of `roadmap-service` (#1562). Criterion 2 names #775, which this work does not need. The workspace criterion should say `target_dir`. The timing criterion for the three pipeline tests is stale. The claim "Fits in one pull request" is wrong.
- Pending a person: decide the policy for hosts without bubblewrap and for popeye, which needs the cluster network. The decision gates the last Part of #772.
