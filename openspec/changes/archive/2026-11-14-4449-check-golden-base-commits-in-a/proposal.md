# Proposal

## Why

One pytest test of the golden stage eval set starts a real `git` with `subprocess.run` against the repository root and skips when the clone is shallow, and `docs/TESTING.md` forbids a test of `src/` that starts a system program and a skip that reads host state, so the check of the base commits becomes a row of `devops ci` that may read the git history (#4449).

## What Changes

- Create `tests/gate/roadmap_stage_eval_commits.py`: it reads the golden cases and the git history, and it fails on a base commit that is not a full hash of a commit of the repository, on a `NO_COMMIT` case with no note that it reads no commit, and on a shallow clone.
- Create `tests/invariants/test_roadmap_stage_eval_commits_check.py` first, which gives the row verdict canned git answers for a shallow clone, an unresolvable commit, a `NO_COMMIT` case with no note and the real cases, and starts no program.
- Add the row `roadmap-stage-eval-commits` to the table of `devops ci` in `src/devops_cli/commands/ci.py`, after the `domain` row, with its title in `src/devops_cli/lang/en/messages.py`, and add the row case to `tests/commands/test_ci_gate_rows.py`.
- Edit `docs/TESTING.md`: the row list gains `roadmap-stage-eval-commits`, and the invariant test list gains `test_roadmap_stage_eval_commits_check.py`.
- Remove `_git` and `test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none` from `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, with the `subprocess` import.
- Keep `test_each_merge_commit_of_the_set_is_a_full_hash_or_the_case_reads_none` in pytest, because it reads loaded data and no git history.
- Add `fetch-depth: 0` to the checkout of the `static` job of `.github/workflows/ci.yml`. That job runs the new row, and its default clone of depth 1 has no history. Change the contract test of that checkout in `tests/invariants/test_workflow_contracts.py` from shallow to full history.
- Add three requirements to `ci-gate-rows` for the row, and change the requirement `Each commit of the set is a real commit or the case reads none` of `roadmap-stage-eval` to the row and the merge-hash test, under its own name.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: The roadmap-stage-eval-commits row checks the base commit of each golden case, The roadmap-stage-eval-commits row fails on a base commit that it cannot resolve, The roadmap-stage-eval-commits row fails on a shallow clone
- `roadmap-stage-eval`: Each commit of the set is a real commit or the case reads none

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/TESTING.md`
- Workflows: `.github/workflows/ci.yml`
- Tests: `tests/invariants/test_roadmap_stage_eval_commits_check.py`, `tests/gate/roadmap_stage_eval_commits.py`, `tests/commands/test_ci_gate_rows.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/invariants/test_workflow_contracts.py`

## Weakened checks

- **`tests/roadmap/stage/test_roadmap_stage_eval_cases.py::test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none`**: Stopped: a golden case whose base commit is not a full hash of a commit of the repository, and a `NO_COMMIT` case with no note that it reads no commit. Safeguard: The `devops ci` row `roadmap-stage-eval-commits` makes the same checks on the git history and fails on a shallow clone. `tests/invariants/test_roadmap_stage_eval_commits_check.py` proves each verdict of the row with canned git answers.

## Feasibility

- The premise of the issue is the test that starts git in the eval case file. The probes confirm the paths of the change, word for word: "The path `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` is a file of the staging commit.", "The path `docs/TESTING.md` is a file of the staging commit." and "The path `tests/gate/roadmap_stage_eval_commits.py` is no file of the staging commit." So group 1 creates the check module and group 2 changes the cited test file.
- `read_file` on lines 185-215 of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` showed the helper `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:192:def _git(*args: str) -> subprocess.CompletedProcess[str]:`, the test `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:198:def test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none(`, its git call `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:194:["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False` and the skip `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:202:pytest.skip("A shallow clone lacks the old commits that the cases name.")`.
- The rule that the test breaks is in `docs/TESTING.md`, which says "A test of `src/` starts no system program", "A test must not skip based on host state" and "A check of committed files or of tool configuration is a row of `devops ci`, not a pytest test. The code of these rows is in `tests/gate/`, one module for each row". The same paragraph lists the rows and ends with `domain`, so the row list gains the new row.
- The count of the set that the issue names, the tests of that file that start git, is one: the input's code of the file holds one `_git` helper and one test that calls it, and `references` with `test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none` answered "files 1, lines 1" with `tests/roadmap/stage/test_roadmap_stage_eval_cases.py: 1 (line 198)`. That member is removed in group 2, and the merge-commit test at line 217 names no git call and stays.
- `references` with `roadmap-stage-eval-commits` was not needed: the probes show that the module path is no file of the commit, so the row name is new and no other file needs an edit for it.
- The count of the golden cases that the new row reads is 59: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:72:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 59, 6)`. Each case is decided by the same rule, so the row decides every member of the set.
- The constants that the plan relies on are `src/devops_cli/roadmap/stage/stage_eval_cases.py:72:CASES_DIRECTORY: Final[Path] = Path("tests/fixtures/roadmap_eval/stage")`, `src/devops_cli/roadmap/stage/stage_eval_cases.py:75:NO_COMMIT: Final[str] = "0" * 40` and `src/devops_cli/config/constants.py:2532: "import sys; from tests.gate.{module} import main; sys.exit(main())"` as the value of `CONST_GATE_ROW_SCRIPT`.
- `read_file` on lines 236-275 of `src/devops_cli/roadmap/stage/stage_eval_cases.py` showed `src/devops_cli/roadmap/stage/stage_eval_cases.py:266:def load_cases(directory: Path | None = None) -> list[StageCase]:` and `src/devops_cli/roadmap/stage/stage_eval_cases.py:202:notes: tuple[str, ...] = ()`, so the row loads the cases with no argument and reads the notes of each case.
- The row table is `get_check_specs`: `read_file` on lines 985-1016 of `src/devops_cli/commands/ci.py` showed the last row `src/devops_cli/commands/ci.py:1011:cmd=_python_check_cmd("configured_domain"),` and the command builder `src/devops_cli/commands/ci.py:798:return ["uv", "run", "python", "-c", CONST_GATE_ROW_SCRIPT.format(module=module)]`; the title of that row is `src/devops_cli/lang/en/messages.py:2150:configured_domain: str = (`.
- `read_file` on `tests/commands/test_ci_gate_rows.py` showed the gate rows `tests/commands/test_ci_gate_rows.py:16:"domain": "configured_domain",`, the check of each row command at line 25 and the order test `tests/commands/test_ci_gate_rows.py:44:assert names[-len(_GATE_ROWS) :] == list(_GATE_ROWS)`, so the new row is registered last and added to that dict last.
- `file_symbols` on `tests/gate/configured_domain.py` showed the shape of a row that prints its own message: `tests/gate/configured_domain.py:111:def outcome(log: str, domains: Mapping[str, str]) -> tuple[int, list[str]]:` gives the verdict from canned input and `tests/gate/configured_domain.py:135:def main(argv: list[str] | None = None) -> int:` supplies the real answers, so the new row takes the git answers as arguments.
- `read_file` on `tests/invariants/test_configured_domain_check.py` showed the file of the same shape for the `domain` row, which imports the row logic as `tests/invariants/test_configured_domain_check.py:15:from tests.gate.configured_domain import findings, main, named_setting, outcome` and starts no program, so group 1 writes the same kind of file for the new row.
- The row needs no change to the runner tool table: `read_file` on lines 185-206 of `tests/roadmap/test_roadmap_runner_tools.py` showed `tests/roadmap/test_roadmap_runner_tools.py:203:and program not in {"uv", "python", "git", "devops"}`, and `src/devops_cli/roadmap/runner_tools.py:123:_apt("git", "ci:git", "ci:lint", "ci:constructs", "ci:domain", "job"),` already holds `git` for the gate.
- The invariant test list rule holds the new test file: `docs/TESTING.md` line 95 lists every file of `tests/invariants/` one by one, `test_configured_domain_check.py` among them, and the archived change folder `openspec/changes/archive/2026-11-13-5295-refuse-configured-domain/` added its new invariant file to that list in the group that created it, so group 1 edits the list in the group that creates the file.
- `load_cases()` needs a checkout of the repository, and no client and no network.
- The row's `_git("rev-parse", "--is-shallow-repository")` and `_git("cat-file", "-e", <sha>^{commit})` need a checkout of the repository and the `git` program on PATH, and no client and no network.
- `get_check_spec("roadmap-stage-eval-commits")` needs a checkout of the repository, and no client and no network.
- `outcome(cases, shallow, resolves)` needs no checkout, no client and no network: it is a pure function of its arguments.
- The programs of the new row are `uv`, `python` and `git`, and each of them is a tool of the runner image, so no program of the row is `NOT_IN_RUNNER` and the image needs no change. The failure class of a failing row is `test`, and the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` all hold, because the row writes no file.
- The first checks against the real system are `git rev-parse --is-shallow-repository`, which must print `false` on the checkout that runs the row, and `uv run devops ci --check --no-cache --only roadmap-stage-eval-commits`, which must read the cases, print their count and exit 0.
- The next check is `uv run devops ci test tests/invariants/test_roadmap_stage_eval_commits_check.py tests/commands/test_ci_gate_rows.py tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, which must pass after the two groups.
- The review finding `task_order` is answered: group 1 now writes `tests/invariants/test_roadmap_stage_eval_commits_check.py` first, so the verdict logic of the check has its failing test before the code, and group 2 only removes the old pytest test.
- The review finding `spec_delta_wrong` is answered: the requirement keeps its own name `Each commit of the set is a real commit or the case reads none`, which fits a text that covers the base commit and the merge commit, so `specs` holds no `renamed` entry.
- No input shows that the issue cannot be built as written: the cited test file exists, the check module path is free, and the row table and the row list are open to a new row.

## Existing Tool Considered

The open, maintained `git` tool reads a commit object and reports a shallow clone, and the row adopts it; the row adds about 90 lines of its own code at about 20k tokens to build, keep and fix, over about 1 hour.

## Dependencies

- Pull request #5554 also changes `docs/TESTING.md`; its edit is the elapsed-line section, and this plan edits the row list and the invariant list, so the two changes sit in different sections and neither waits.
