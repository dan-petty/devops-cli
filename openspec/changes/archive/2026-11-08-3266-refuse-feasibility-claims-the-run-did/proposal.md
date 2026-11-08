# Proposal

## Why

#3266 reports two plans whose `## Feasibility` cites `read_file` and `search_code` results while the stage comment says the run made no tool call. Nothing compares the claims of a plan with the trace of the run that wrote it, so a plan presents an unchecked premise as checked. The premise probe of #3176 checks that a cited path exists, and not that the run read it.

## What Changes

- Add `TraceFacts` to `src/devops_cli/roadmap/agent_run.py`: the tool names and the `path`, `directory` and `paths` values of each call argument, read from a `RunTrace`.
- Add a `trace` keyword to `check_proposal` and `check_gates` in `src/devops_cli/roadmap/stage/stage_change.py`, and refuse an affirmative tool name or code-span read claim that the facts do not support.
- Pass the facts of the reply's run to the gates in `src/devops_cli/roadmap/stage/stage.py`, and add `trace` to the keyword inputs of `gate_arguments` in `src/devops_cli/roadmap/stage/stage_request.py`.
- Read the `trace` fact of a case in `src/devops_cli/roadmap/stage/stage_eval_cases.py` and pass it to `check_proposal` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`, so the replay judges the rule with no run.
- State the rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and in `docs/roadmap/stage.md`.
- Add a golden-set replay case from #3205 under `tests/fixtures/roadmap_eval/stage/` whose facts give a trace of zero calls, and the unit tests of each branch of the check.
- The change adds a refusal that the stage job reports, which a consumer observes, so it carries a delta of `roadmap-stage` and of `roadmap-stage-eval`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Feasibility cites only what the plan run did, Trace facts of a run, The planner prompt cites only the run
- `roadmap-stage-eval`: The golden set holds a plan whose read claim its trace does not support

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/ai/client/test_roadmap_agent_run.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/case.json`, `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/issue.txt`, `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/plan.json`, `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/facts.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`

## Feasibility

- The probe confirms the cited paths, with two corrections: `The path `tests/roadmap/test_roadmap_stage_prompt_rules.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` So the prompt-rule test lives at `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, and the modules that the issue cites under `src/devops_cli/roadmap/` now sit under `src/devops_cli/roadmap/stage/`.
- `list_files` of `src/devops_cli/roadmap/stage` shows `stage_change.py`, `stage_tools.py`, `stage_toolbox.py`, `stage_eval_cases.py`, `stage_eval_gates.py` and `stage_request.py`, so every module of the plan is a file of the staging commit.
- The premise holds at the moved path: `file_symbols` of `src/devops_cli/roadmap/stage/stage_change.py` shows `def content_problems` at line 1101, `class ProposalGate` at line 1131, `def check_gates` at line 1155 and `def check_proposal` at line 1203, so one function collects the problems of a reply and one place takes the new keyword.
- The premise holds: `src/devops_cli/roadmap/stage/stage_change.py:160:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` with `_SELF_ACCEPTANCE_MARKS` at line 161 shows that a plan adding a rule of the check gives a group test that builds its own `StageProposal`, so this plan gives that test.
- The premise holds: `src/devops_cli/roadmap/stage/stage_change.py:110:_TOKEN_COST` holds `r"\d+(?:[.,]\d+)*\s*k?\s*tokens?\b"`, and `content_problems` refuses a plan that `builds_own` and gives no cost, so this plan states `80k tokens` and `4 hours` in `existing_tool`.
- The premise holds: `src/devops_cli/roadmap/stage/stage_toolbox.py:116` holds `self.traces: list[RunTrace] = [] if traces is None else traces` and `src/devops_cli/roadmap/stage/stage_toolbox.py:141` holds `self.traces.append(trace)`, so the client appends one trace for each ask.
- The premise holds: `src/devops_cli/roadmap/stage/stage.py:910` holds `self._traces.clear()`, and `src/devops_cli/roadmap/stage/stage.py:924` holds `proposal = self._ask(StageProposal, _CHANGE_TASK, request.for_model())` under `_gated`, so the planner reads the trace of the reply's ask after the ask returns.
- The premise holds: `src/devops_cli/roadmap/stage/stage_request.py:def gate_arguments` returns the keyword arguments of `check_proposal`, and `src/devops_cli/roadmap/stage/stage.py:1164` holds `**gate_arguments(`, so one keyword reaches every gate call of the job.
- The premise holds: `src/devops_cli/roadmap/stage/stage_eval_cases.py:70` holds `CASES_DIRECTORY: Final[Path] = Path("tests/fixtures/roadmap_eval/stage")`, `class CaseFacts` at line 157 holds `tracked`, `capabilities`, `search_evidence` and `constants`, and `src/devops_cli/commands/roadmap_eval_stage.py:34` holds `report = replay_all(select_cases(load_cases(cases_dir), names, limit))`, so the replay judges every case of the folder with no model and no git.
- The callers of `check_proposal` are `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/implement/implement.py` and `src/devops_cli/roadmap/plan_check.py`, and each keeps its call with no facts, because the keyword defaults to `None`.
- The first checks of the implementation, each on the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` for the gate, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` for the case, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` for the prompt rule, and `uv run devops roadmap eval stage --replay` for the score before and after, as `docs/ROADMAP_WORKFLOW.md` requires.
- Each function that the plan calls and that needs a checkout, a client or a network: `TraceFacts.of(trace)` needs no checkout, no client and no network, because it reads a `RunTrace` in memory. `StageTools.tools()` needs a checkout of the repository, because the tools read the commit at `sha`. `ToolboxClient.__init__` needs a checkout of the repository and, for `read_issue` and `find_issues`, a client of the GitHub service. `checkout_problem()` needs a checkout of the repository, because it runs `git rev-parse` and `git status`. `_read_staged_file` needs a checkout of the repository, because it runs `git show` on the staged commit. `replay_case` and `devops roadmap eval stage --replay` need no client and no network: they read the case files and call no model.

## Existing Tool Considered

No open, maintained tool or library covers the need. The check compares this repository's stage reply with this repository's `RunTrace`, and no upstream project holds either. The change builds its own code, about 60 lines of `TraceFacts` and one check function, and deletes no internal code. Written cost: 80k tokens to build, 20k tokens to keep and fix, and 4 hours of elapsed work.

## Dependencies

- #4142: `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` — the open pull request of #4142 changes the same two documents, so it merges before this plan writes its sentence into them.
