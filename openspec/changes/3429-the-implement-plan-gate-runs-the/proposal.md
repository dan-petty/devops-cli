# Proposal

## Why

The implement plan gate runs only `check_proposal` (#3393), so a plan that passes it and fails `openspec validate --strict` still starts a runner Job and spends model calls on a plan that cannot be archived (#3429). The stage job refuses such a plan at `src/devops_cli/roadmap/stage/stage.py:1695:def _validate(self, change: str, files: Mapping[str, str]) -> str | None:`, and the two gates must agree.

## What Changes

- The implement plan gate calls `validate_change` on the change files of an item whose plan passes `check_proposal`.
- The gate leaves the item out with the first issue of the validation as its reason, under the existing message `implement_left_plan`.
- `plan_implement` enters the `openspec_tool()` context once for each plan run and gives the tool to the judge.
- A host with no `openspec` binary skips the validation, as the stage job does.
- A validation that raises leaves that item out with the first line of the error, and the run goes on with the other items.
- The job world answers the tool's `validate` command on its existing process fake, and the modules that plan without that fake take the existing `openspec_fake` fixture.
- The shared `OpenSpecFake` answers a `validate <change> --strict --json` command that no `script` names, through a new `script_validate` method.
- The tests cover a refused plan, a run of two items with one refused, one tool context for a run, no binary, and a validation that raises.
- The spec delta modifies the requirement `The job leaves out an item whose plan fails the check` of `roadmap-implement-job`, so the living spec names both gates.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job leaves out an item whose plan fails the check

## Impact

- Code: `src/devops_cli/roadmap/implement/implement.py`
- Tests: `tests/support/fakes/openspec.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/implement/test_roadmap_implement_planned.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_plan_reason.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- The premise holds at the staged commit: the plan gate runs `check_proposal` and no OpenSpec check. I read `src/devops_cli/roadmap/implement/implement.py` from line 385 to line 407: it holds `src/devops_cli/roadmap/implement/implement.py:404:problems = check_proposal(` and `src/devops_cli/roadmap/implement/implement.py:407:return texts.implement_left_plan.format(problem=problems[0]) if problems else None`, and no call of `validate_change` between them.
- `file_symbols` of `src/devops_cli/roadmap/implement/implement.py` lists `385:def _plan_reason(self, item: Item, rev: str) -> str | None:` and `291:def judge(self, item: Item) -> ImplementTarget | str:`; the probe says `_Judge` defines no field `judge` in `src/devops_cli/roadmap/implement/implement.py`, so the issue names a method, and its intent is clear.
- The probe shows that the cited source path moved, word for word: `The path `src/devops_cli/roadmap/implement.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The plan uses the current path, so the issue is buildable.
- The probe shows that the cited test path moved, word for word: `The path `tests/roadmap/test_roadmap_implement_job.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_job.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The plan uses the current path.
- The probe shows that the cited stage paths moved, word for word: `The path `src/devops_cli/roadmap/stage_validate.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_validate.py`.` and `The path `src/devops_cli/roadmap/stage.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/spend/stage.py`, `src/devops_cli/roadmap/stage/stage.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The plan uses the current paths.
- The stage gate that the issue points to exists: `src/devops_cli/roadmap/stage/stage.py:1695:def _validate(self, change: str, files: Mapping[str, str]) -> str | None:` skips the check at `src/devops_cli/roadmap/stage/stage.py:1698:if self._tool is None:` and runs it at `src/devops_cli/roadmap/stage/stage.py:1700:return validate_change(self._tool, self._source, change, files)`.
- `validate_change` is the existing wrapper, cited by symbol as `src/devops_cli/roadmap/stage/stage_validate.py:def validate_change`: it writes the change files and the base specs into a scratch directory, runs the tool, and drops the note that a change needs no spec delta, which `src/devops_cli/roadmap/stage/stage_validate.py:def _issues_of` filters. Its problem is one line per issue, joined at `src/devops_cli/roadmap/stage/stage_validate.py:148:problem = "\n".join(issues) if issues else ""`, so the first line is the first issue.
- `openspec_tool` yields the tool or None: `src/devops_cli/roadmap/stage/stage.py:1704:def openspec_tool() -> Iterator[OpenSpecTool | None]:` answers None at `src/devops_cli/roadmap/stage/stage.py:1706:if shutil.which(BIN_OPENSPEC) is None:`, and otherwise enters `isolated_openspec`, which runs `src/devops_cli/openspec/tool.py:120:tool.run_checked(["config", "set", setting, value], Path(scratch))` for each isolated setting. The constant that the check relies on is `src/devops_cli/config/commands.py:41:BIN_OPENSPEC: str = "openspec"`.
- The tool's own run goes through the process runner: `src/devops_cli/openspec/tool.py:57:return run_subprocess(`. The job world installs a process runner fake at `tests/support/fakes/process.py:453:set_process_runner(fake)`, and its `which` answers `tests/support/fakes/process.py:461:return f"/usr/local/bin/{cmd_name}"` for `openspec`, so in the world the tool's commands are answered by that fake. The world answers `git` at `tests/support/roadmap_implement.py:603:programs.answer("git", ProcessAnswer(side_effect=git_for_real))` and reaches `plan_implement` at `tests/support/roadmap_implement.py:518:return plan_implement(`; the change name is `tests/support/roadmap_implement.py:37:CHANGE = "1-the-job-drops-a-comment"`.
- `search_code` for `plan_implement(` found the call in `tests/support/roadmap_implement.py`, in `tests/roadmap/implement/test_roadmap_implement_job.py` twice, and in three modules that plan without the world's process fake: `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/implement/test_roadmap_implement_planned.py` and `tests/roadmap/implement/test_roadmap_implement_submit.py`. Those three take the existing `openspec_fake` fixture at `tests/support/fakes/openspec.py:219:def openspec_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> OpenSpecFake:`.
- The OpenSpec fake fails a command it cannot answer, at `tests/support/fakes/openspec.py:134:if argv not in runs:`, and its `script` keys an answer by the exact argv at `tests/support/fakes/openspec.py:95:def script(`. The stage tests script the validation this way, at `tests/roadmap/stage/test_roadmap_stage_job.py:57:def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:`, with the passing report `tests/support/roadmap_stage.py:35:VALID_REPORT = json.dumps({"items": [{"id": "x", "valid": True, "issues": []}]})`.
- The message that the gate reuses is pinned at `tests/roadmap/implement/test_roadmap_implement_plan_reason.py:24:REFUSED = f"Its plan fails the stage check: {FIRST_PROBLEM}"`, and the module installs its fixtures at `tests/roadmap/implement/test_roadmap_implement_plan_reason.py:17:pytestmark = pytest.mark.usefixtures("keyring_store")`.
- This reply answers the three faults. The gate reuses the existing message `implement_left_plan`, named without the dotted module, so no group changes `src/devops_cli/lang/en/messages.py`. The test-only group names the test it keeps passing, `test_a_staged_low_effort_p1_bug_is_selected_with_its_branch_and_pull_request`. The stage validator is cited by symbol, `src/devops_cli/roadmap/stage/stage_validate.py:def validate_change` and `src/devops_cli/roadmap/stage/stage_validate.py:def _issues_of`, so the citation holds when the lines move.
- Precondition of `plan_implement`: a checkout of the repository, from `inspect_checkout(checkout, repo)`, and a client of the GitHub service, from `client = get_github_session().client`; the plan reads both at `src/devops_cli/roadmap/implement/implement.py` line 518 and line 519.
- Precondition of `validate_change`: a checkout of the repository that holds the base specs of each capability that the change touches, which is the clone that `plan_implement` already has.
- Precondition of `openspec_tool`: the `openspec` binary on PATH and no network; it runs the binary under an isolated configuration in a scratch directory.
- The change introduces no command and no verify program: both `verify` values are `uv run devops ci test` on paths that the commit holds, so no failure class and no runner capability is new. Those verifies need `uv` and `python`, and the new code starts `openspec`; all three are runner image tools, so the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The dependency #3393 is not checked in this run, and the gate it adds is present: `src/devops_cli/roadmap/implement/implement.py:385:def _plan_reason(self, item: Item, rev: str) -> str | None:`.

## Existing Tool Considered

Fission-AI/OpenSpec, MIT, maintained. The repository already wraps it in `validate_change` and `openspec_tool()`, and the stage job calls both at `src/devops_cli/roadmap/stage/stage.py:1700:return validate_change(self._tool, self._source, change, files)`. The change adds one caller and builds no new rule, so it deletes no internal code.

## Dependencies

None.
