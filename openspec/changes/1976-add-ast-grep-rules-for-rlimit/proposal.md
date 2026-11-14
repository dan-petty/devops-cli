# Proposal

## Why

ARCHITECTURE.md section 7.3 holds three process-safety rules that an agent reads only when it opens that section, and no ast-grep rule enforces them. #1976 adds the three rules, their cases and their entries in the construct gate.

## What Changes

- Add `.ast-grep/rules/process-setrlimit-nproc.yml`, which reports a `resource.setrlimit` call whose limit argument is `resource.RLIMIT_NPROC`.
- Add `.ast-grep/rules/process-nonblocking-std-fd.yml`, which reports `os.set_blocking` on a literal descriptor 0, 1 or 2 with `False`, and `fcntl.fcntl` on those descriptors with `fcntl.O_NONBLOCK` among its flags.
- Add `.ast-grep/rules/process-killpg-guarded.yml`, which reports an `os.killpg` call outside the four guard-holding functions of the core process module.
- Add one case file for each rule under `.ast-grep/rule-tests/`, with a valid and an invalid case, including the descriptor 3 case that no rule reports.
- Register the three ids in `CONST_AST_GREP_RULE_FILES` with `src/**`, and add one `Violation` for each in `VIOLATIONS` of `tests/gate/construct_gate.py`.
- Name the three rules beside the process-safety rules of `ARCHITECTURE.md` section 7.3.
- The change alters what the `constructs` row of `devops ci` refuses, so it carries a spec delta on `ci-gate-rows`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: The constructs row refuses the process-safety calls, Each process-safety rule joins the construct gate

## Impact

- Code: `.ast-grep/rules/process-setrlimit-nproc.yml`, `.ast-grep/rules/process-nonblocking-std-fd.yml`, `.ast-grep/rules/process-killpg-guarded.yml`, `.ast-grep/rule-tests/process-setrlimit-nproc-test.yml`, `.ast-grep/rule-tests/process-nonblocking-std-fd-test.yml`, `.ast-grep/rule-tests/process-killpg-guarded-test.yml`
- Documents: `ARCHITECTURE.md`
- Tests: `tests/gate/construct_gate.py`

## Feasibility

- `probes` says: "The path `AGENTS.md` is a file of the staging commit." and "The path `ARCHITECTURE.md` is a file of the staging commit." A `read_file` of `ARCHITECTURE.md` lines 196 to 204 showed the process-group rule at `ARCHITECTURE.md:200:Do not signal a pid below 2` and the shared-container rule at `ARCHITECTURE.md:201:Linux counts it for the real user across the container`, so the three rules of the issue sit in section 7.3.
- `probes` says: "The path `sandbox/host.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/sandbox/host.py`. No commit in the history deleted or renamed it." The plan cites `src/devops_cli/sandbox/host.py` and plans no edit of it.
- `search_code` for `os.killpg` returned 7 lines. The set that the new rule allows has 1 member under `src/`: `src/devops_cli/core/process.py:1205:os.killpg(pgid, sig)`, inside `src/devops_cli/core/process.py:def _signal_process_group`. The other 6 lines are prose in `ARCHITECTURE.md` and in an archived design, and calls in test files that the `src/**` tree of the rule does not hold.
- `search_code` for `setrlimit` returned 4 lines, and each is a comment or a docstring: `src/devops_cli/config/constants.py:4927:# devops-cli calls setrlimit.`, `src/devops_cli/sandbox/host.py:254:RLIMIT_NPROC via setrlimit is per-real-UID`, one line of `src/devops_cli/security/tool_executor.py` and one line of an archived design. The count of `setrlimit` calls under `src/` is 0, so that rule reports nothing on the source tree.
- `search_code` for `set_blocking` returned no match, so the tree holds no `os.set_blocking` call and that part of the rule reports nothing on `src/`.
- `search_code` for `O_NONBLOCK` returned 4 lines, and the plan decides each one: `ARCHITECTURE.md` line 201 is prose, `src/devops_cli/roadmap/implement/git_isolation.py:205` is a docstring, `src/devops_cli/roadmap/implement/git_isolation.py:209:handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)` opens a fresh descriptor and is no `fcntl.fcntl` call, and `tests/ai/test_review_defects.py:565:os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))` is outside the `src/**` tree. The count of `fcntl.fcntl` calls that set `fcntl.O_NONBLOCK` under `src/` is 0.
- `list_files` of `.ast-grep/rules` listed 20 rule files and of `.ast-grep/rule-tests` 20 case files. None names `resource.setrlimit`, `os.set_blocking`, `fcntl.fcntl` or `os.killpg`, so the premise that these calls have no check holds.
- `read_file` of `sgconfig.yml` showed `sgconfig.yml:2:- .ast-grep/rules` and `sgconfig.yml:4:- testDir: .ast-grep/rule-tests`, so a new rule and its case join the scan and the rule test run with no configuration change.
- `read_file` of `tests/gate/construct_gate.py` showed the rule table `CONST_AST_GREP_RULE_FILES`, the `tests/gate/construct_gate.py:class Violation` table built by `tests/gate/construct_gate.py:def violation_table_problems`, the twin map at `tests/gate/construct_gate.py:97:"src": "tests",`, and the case check of `tests/gate/construct_gate.py:def _rule_test_case_escapes`, which requires a valid case and an invalid case for each rule.
- `read_file` of `tests/invariants/test_construct_gate_check.py` showed that it imports the rule table and the violation table from the gate module at `tests/invariants/test_construct_gate_check.py:18:CONST_AST_GREP_RULE_FILES,`, so the new ids enter its cases with no edit there.
- The issue cites line 952 of `src/devops_cli/core/process.py` for `_signal_process_group`; the staged file holds that function at `src/devops_cli/core/process.py:def _signal_process_group` and its `os.killpg` call at line 1205, so the plan cites the symbol and not the line.
- The plan relies on no new bound: the scan bound of the construct gate stays as the staged tree defines it, at `tests/gate/construct_gate.py:91:_SCAN_TIMEOUT_SECONDS = 120`.
- The plan answers the finding of `problem`: the group that changes the gate table is a `manifest` group, so its `verify` is now `uv run devops ci test tests/gate/construct_gate.py`, a path of that group, and no longer the invariants path. `list_files` of `tests/gate` showed no test module there, and `devops ci test` expands a helper module under `tests/` to the test modules that import it, which is `tests/invariants/test_construct_gate_check.py` for this table.
- The plan calls no function whose arguments need a checkout, a client or a network. Each command reads the checkout of the repository and no service.
- Runner capability and failure class: `uv run ast-grep test --skip-snapshot-tests` runs `ast-grep`, which the image holds for `ci:constructs` and `hook:ast-grep-scan` and which no `NOT_IN_RUNNER` entry lists, and a red group carries the failure class `test`. `uv run devops ci test tests/gate/construct_gate.py` runs `uv` and `pytest`, both in the image, and `uv run devops ci docs` runs `devops`. The pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and drops all capabilities, so a step writes only the checkout and the uv cache and needs no network.
- First checks against the real system: `uv run ast-grep test --skip-snapshot-tests` shows each new case pass; `uv run devops ci --only constructs` shows the row green over `src/` and `tests/`; `uv run devops ci test tests/gate/construct_gate.py` shows the rule table and the gate check in step.

## Existing Tool Considered

ast-grep, the open scanner that the `constructs` row of `devops ci` and the `ast-grep-test` hook already run. The change adds three rule files, their cases and their gate entries, and builds no program code.

## Dependencies

- Pull request #5547 changes `docs/TESTING.md`, a path that the issue cites; this plan changes no line of that file, so the two do not conflict.
- Pull request #5575 changes `docs/TESTING.md`, a path that the issue cites; this plan changes no line of that file, so the two do not conflict.
