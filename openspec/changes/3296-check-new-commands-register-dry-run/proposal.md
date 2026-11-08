# Proposal

## Why

`check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py` refuses a plan that breaks a rule of the repository, but it holds no rule for the registrations that a new `devops` command needs. In #3237 the stage plan added `devops pr evidence` and named neither the dry-run class, nor the dry-run callback test, nor the two documentation commands. The dry-run ratchet and `uv run devops ci docs` then fail after the merge, and a person finds the gap, not the planner. This change reports each missing companion registration to the stage model before it writes the change. It delivers #3296.

## What Changes

- `src/devops_cli/roadmap/stage/stage_companions.py` gains `companion_problems`, which reports each missing companion registration of a `devops` command that a plan adds.
- `src/devops_cli/roadmap/stage/stage_change.py` gains the `ProposalGate.COMPANIONS` member and its line in `check_gates`, and `stage_companions.py` joins `STAGE_EVAL_TRIGGER_PATHS`.
- `src/devops_cli/lang/en/messages.py` gains the problem texts that name the new command, its dry-run class, its callback test file and each missing documentation command.
- `tests/roadmap/stage/test_roadmap_stage_companions.py` pins the rule with and without each companion registration, and pins that `content_problems` finds no problem in the plan of this change.
- `docs/roadmap/plan-recheck.md` gains the row of the `companions` gate in the table of the gates of `check_proposal`.
- No MCP requirement is planned: the merged #3204 test requires no exposure entry and no exclusion entry for a new command, so the MCP half of the issue has no check to serve.
- The change adds a requirement to the existing `roadmap-stage` capability, so it is not a test-only or document-only change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan registers the companions of a new command

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_companions.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/plan-recheck.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_companions.py`

## Feasibility

- The premise holds, and `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:1203:def check_proposal(` with `src/devops_cli/roadmap/stage/stage_change.py:1238:found = check_gates(`. `check_gates` returns the spec-delta, content, citation, form, eval-replay, paths, what-changes, move-prefix, move-verify, search, criteria, dependencies, creates, registry and constants problems, and no rule for a new command.
- The probe confirms the path that the issue cites, word for word: The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The rule goes in the candidate path.
- The probe confirms the files that the plan reads, word for word: The path `tests/commands/test_pr_dry_run.py` is a file of the staging commit. The path `src/devops_cli/config/constants.py` is a file of the staging commit. The path `docs/CLI_REFERENCE.md` is a file of the staging commit.
- The probe gives the MCP half of the issue no file, word for word: The path `tests/ai/mcp/test_mcp.py` is no file of the staging commit. Commit 2475fa2c 2026-11-06 test(mcp): MCP, toolset and tool tests are named by behavior (#3872) deleted or renamed it. The plan adds no MCP rule and no code that compensates for it.
- `read_file` of `tests/ai/mcp/test_mcp_exposure_table.py` showed `tests/ai/mcp/test_mcp_exposure_table.py:96:assert exposed_paths - all_cli_commands == set()` under the docstring `a new command needs no entry (#3204)`, so the test that the issue names is gone and the current test fails only on an exposure entry that names no command.
- `search_code` of `"evidence"` showed `src/devops_cli/commands/pr.py:468:@app.command("evidence", help=HELP.pr.evidence)`, so a command of a module is registered by a quoted literal, and a module of the staged commit that holds no such literal holds no such command.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:1131:class ProposalGate(StrEnum):` and `src/devops_cli/roadmap/stage/stage_change.py:1181:ProposalGate.EVAL_REPLAY: eval_replay_problems(proposal.groups),`, so a new rule is one member of the enum and one line of `check_gates`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:205:REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate --sync-readme"`, so the documentation command of the new rule reuses the constant that the stage already holds.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:208:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (`, so the module that holds the new check joins the paths whose change a plan must measure.
- `read_file` of `src/devops_cli/roadmap/stage/stage.py` showed `src/devops_cli/roadmap/stage/stage.py:1179:read_text=partial(_read_staged_file, self._source, self._sha),`, so the rule reads the command module of the staged commit and not of the running process.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` showed `src/devops_cli/roadmap/stage/stage_eval_gates.py:171:return check_proposal(` under `_path_gate` and `src/devops_cli/roadmap/stage/stage_eval_gates.py:203:Gate(GateName.PATHS, "#3010", DefectType.MISSING_PATH, _path_gate),`, so the replay judges the new rule as its one `paths` gate and the nine defect types stay as they are.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_gates.py` showed `tests/roadmap/stage/test_roadmap_stage_gates.py:34:assert set(found) == set(ProposalGate)`, so the new member needs no edit of that test, and `src/devops_cli/roadmap/plan_recheck.py` prints it under its own name.
- `read_file` of `docs/roadmap/plan-recheck.md` showed `docs/roadmap/plan-recheck.md:112:| Gate | What it refuses |`, so the new gate gets one row of that table.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:825:def _self_acceptance_problems(` and its call in `content_problems`, so the test of group 1 names `StageProposal`, `content_problems` and `no problem` for the plan of this change.
- `search_code` of `_adds_plan_rule` showed `src/devops_cli/roadmap/stage/stage_change.py:819:def _adds_plan_rule(group: StageGroup) -> bool:`, the shape of a rule that reads the `changes` of a group; the new rule reads the same paths and no new plan field.
- First check against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_companions.py` fails on the base because `companion_problems` does not exist.
- Second check against the real system: `uv run devops roadmap plan-recheck --source . --branch HEAD` lists no refusal under `companions` on the base and lists each merged plan that adds a command without its companions after the change.
- Third check against the real system: `uv run devops roadmap eval stage --replay` gives the score of the recorded cases, which the pull request states before and after the change.
- Fourth check against the real system: `uv run devops ci docs` shows the documents in step with the code and the new gate row in place.
- Precondition of `_read_staged_file` and of `read_text`: a checkout of the repository at the staged commit. The call reads the text of `src/devops_cli/commands/pr.py` from that commit and gives None when the commit holds no such file.
- Precondition of `companion_problems`: a checkout of the repository only, through `read_text`. It calls no client of a service and reaches no network.
- Precondition of `uv run devops roadmap plan-recheck --source . --branch HEAD`: a checkout of the repository. It reads the change folders of the branch, calls no model and reaches no network.
- Precondition of `uv run devops roadmap eval stage --replay`: a checkout of the repository. The replay calls no model and reaches no network.

## Existing Tool Considered

No open, maintained tool or library covers this need. The rule reads the task groups of this project's stage plan, its `command-dry-run-class` spec delta and the command modules of the staged commit, so no external code answers it. The change extends the gate list of `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py` with a new module `src/devops_cli/roadmap/stage/stage_companions.py`. Written cost to build, keep and fix that code: about 6,000 tokens and 45 minutes of elapsed time. The change deletes no internal code.

## Dependencies

None.
