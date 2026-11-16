# Proposal

## Why

A repair round of an implement step sends the same inputs again with the text of the failure, so a second failure of the same kind repeats the strategy that failed. A stop with action `change_tier` on a ladder of one tier names no setting, so a person cannot see what to change. This change gives each attempt a strategy of its own and names the ladder at that stop (#3569).

## What Changes

- The `attempt` event of the trace holds the strategy of the attempt: `planned` on the first, `repo_map` on the second, and `tier` on the third and each later attempt.
- The second attempt adds a `# Repository map` section to its message, with one line for each file that the failure names and each file of the group, at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files.
- The third attempt runs on the next healthy tier when the ladder of the step class holds more than one tier, in a new conversation whose message is the repair message with the failure text, after the step discards the checkout back to its last kept commit, and it spends no repair round.
- A stop whose action is `change_tier` on a ladder of one tier names `roadmap.implement.ladder` and the tier of that ladder in its reason.
- `docs/roadmap/implement.md` states the strategy of each attempt and no longer says that a repair round stays on its tier.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/trace`: A step records each attempt
- `roadmap-implement-step/inputs`: The second attempt adds the repository map
- `roadmap-implement-step/model-calls`: The third attempt moves to the next tier, A stop on a ladder of one tier names the setting

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_strategy.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `tests/roadmap/implement/test_roadmap_implement_step_repair.py`, `tests/roadmap/implement/test_roadmap_implement_tier_move.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_one_tier.py`

## Feasibility

- The probes name the module that the issue cites as renamed, word for word: The path `src/devops_cli/roadmap/implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/support/implement_step.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan changes `src/devops_cli/roadmap/implement/implement_step.py` and opens no module at the old path.
- The probes name the test module that the issue cites as renamed, word for word: The path `tests/roadmap/test_roadmap_implement_step_attempts.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`. The new tests of this plan go in that folder, `tests/roadmap/implement/`, which the probes show.
- `list_files` on `src/devops_cli/roadmap/implement` showed the module `src/devops_cli/roadmap/implement/implement_step.py` and `src/devops_cli/roadmap/implement/implement_trace.py`, and no `src/devops_cli/roadmap/implement/implement_strategy.py`, so the plan creates that module. `list_files` on `tests/roadmap/implement` showed `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `tests/roadmap/implement/test_roadmap_implement_step_repair.py`, `tests/roadmap/implement/test_roadmap_implement_step.py` and `tests/roadmap/implement/test_roadmap_implement_step_parser.py`, and neither `tests/roadmap/implement/test_roadmap_implement_tier_move.py` nor `tests/roadmap/implement/test_roadmap_implement_one_tier.py`, so the plan creates those two.
- `read_file` on `docs/ENV_VARS.md` lines 140 to 148 showed the row of the setting, and `docs/ENV_VARS.md:144:one tier per attempt` and `docs/roadmap/implement.md:12:maps each class to a list of tiers` both hold the text that this line quotes, so the setting that the plan names exists and holds one or more tiers.
- `file_symbols` on `src/devops_cli/roadmap/implement/implement_trace.py` showed `217: def attempt(`, a method of `src/devops_cli/roadmap/implement/implement_trace.py:class ImplementTrace`, with the keyword-only `repair` at line 224, so group 1 cites that class and adds the keyword-only `strategy` to that method.
- `read_file` of `src/devops_cli/roadmap/implement/implement_step.py` lines 1830 to 1975 showed the symbols that the groups change: `src/devops_cli/roadmap/implement/implement_step.py:def _extra_ask`, `src/devops_cli/roadmap/implement/implement_step.py:def _moves_tier`, `src/devops_cli/roadmap/implement/implement_step.py:def _repair_rounds`, `src/devops_cli/roadmap/implement/implement_step.py:class _Rounds` and `src/devops_cli/roadmap/implement/implement_step.py:def _trace_attempt`, and lines 630 to 660 showed `src/devops_cli/roadmap/implement/implement_step.py:def _tier_for_attempt`.
- The premise holds in the code: the extra turn continues the first conversation, `src/devops_cli/roadmap/implement/implement_step.py:1860:the same conversation and the same limits as`, and its message is the failure text alone, `src/devops_cli/roadmap/implement/implement_step.py:1840:template = texts.implement_hook_turn if failure.hook else texts.implement_repair_turn`.
- The review finding holds, and group 3 fixes it: the first turn of each attempt of the tier loop sends the message of the step again, `src/devops_cli/roadmap/implement/implement_step.py:2051:agent, tier_model, log, inputs.message, source=source, usage_limits=usage_limits`, so the third attempt must take the message of `src/devops_cli/roadmap/implement/implement_step.py:def _extra_ask`, which holds the failure text, and its test asserts that text in the message of the third attempt.
- The stop of a one-tier ladder keeps the raw failure text: `src/devops_cli/roadmap/implement/implement_step.py:2083:if failure is None or not _moves_tier(run) or attempt + 1 >= len(tiers):`, and the helper `src/devops_cli/roadmap/implement/implement_step.py:def _tier_for_attempt` never leaves the one tier, as its last line reads, `src/devops_cli/roadmap/implement/implement_step.py:653:return tiers[min(attempt, len(tiers) - 1)], min(attempt, len(tiers) - 1)`.
- The `attempt` event holds no strategy today: its fields are `src/devops_cli/roadmap/implement/implement_trace.py:229:"number": number,` and `src/devops_cli/roadmap/implement/implement_trace.py:232:"next": "repair" if repair else "stop",`, and the writer `src/devops_cli/roadmap/implement/implement_step.py:1950:_trace_attempt(trace, number, tier, failure, repair=repair)` passes no strategy.
- The `attempt` event of a test compares every field: `read_file` of lines 150 to 175 of `tests/roadmap/implement/test_roadmap_implement_step_attempts.py` showed `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:166:assert _attempts(trace) == [`, whose entry holds `number`, `tier`, `outcome`, `next`, `class` and `evidence`, so that file is in the `changes` of group 1 and the entry gains the field `"strategy": "planned"`.
- The tests of the second attempt assert the whole message: `search_code` with the text `_prompt(script, 2) == ASK + END` showed `tests/roadmap/implement/test_roadmap_implement_step_repair.py:123:assert _prompt(script, 2) == ASK + END` and the same line at 235 and 301, so that file is in the `changes` of group 2 and the three assertions gain the map section.
- The parser stop of one tier unpacks the two lines of its reason: `read_file` of lines 1925 to 1945 of `tests/roadmap/implement/test_roadmap_implement_step.py` showed `tests/roadmap/implement/test_roadmap_implement_step.py:1934:first, named = outcome.reason.splitlines()`, so that file is in the `changes` of group 4 and the test reads the two first lines and asserts the new line last.
- The text of `A step records each attempt` is 472 characters and the text of `The third attempt moves to the next tier` is 437, each under the 500-character limit, and the detail that they drop sits in their scenarios: the strategy after a failure that selects `change_tier` is scenario `An attempt after a failure that selects change_tier`, and the later attempts are scenario `A ladder of one tier`.
- The scenario `The strategy of each attempt` names no code in a code span, and group 1 names `repo_map` in its test `tests/roadmap/implement/test_roadmap_implement_step_attempts.py::test_the_attempt_events_name_the_planned_and_repo_map_strategies`, so a behavior test names the strategy that the scenario asserts.
- The plan declares no new `CONST_ROADMAP_` name and only cites the staged one, whose registry entry is `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),`, and group 2 names `tests/roadmap/test_roadmap_limit_classes.py` in its `reads` and in its task, so no task of this plan leaves the prefix unregistered.
- The bound of the map is reused: `CONST_ROADMAP_STAGE_MAP_MAX_FILES` is 40 at `src/devops_cli/config/constants.py:3403:CONST_ROADMAP_STAGE_MAP_MAX_FILES: Final[int] = 40`, and the plan gives no new name to that bound.
- The map line reuses the form of the stage tool: `src/devops_cli/roadmap/stage/stage_tools.py:484:line = f"{path}: {', '.join(symbol.name for symbol in node.symbols)}"` renders one file as its path and the names of its top-level symbols.
- The bound of the extra turns is read at `src/devops_cli/roadmap/implement/implement_step.py:2015:budget = settings.roadmap.implement.repair_rounds`, and `src/devops_cli/roadmap/implement/implement_step.py:1949:repair = ask is not None and used < start.allowed` is the loop of the rounds that group 3 narrows.
- The document holds the sentence that the change removes, as `read_file` of lines 8 to 20 showed: `docs/roadmap/implement.md:14:A repair round stays on its tier.`
- `run_step` needs a checkout of the repository, because it reads the change folder and the files of the group; each test passes the fixture `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:58:def checkout(implement_checkout: Path) -> Path:`, and `run_step` takes the ladder and the model of each tier at `src/devops_cli/roadmap/implement/implement_step.py:2183:ladder: Sequence[str] | None = None,` and `src/devops_cli/roadmap/implement/implement_step.py:2184:model_for_tier: Callable[[str], Any] | None = None,`.
- `build_step_inputs` needs a checkout of the repository, because it reads the change folder and the files of the group, `src/devops_cli/roadmap/implement/implement_step.py:def build_step_inputs`.
- `named_files` needs a checkout of the repository, because it resolves the paths of the group against the checkout, `src/devops_cli/roadmap/step_files.py:def named_files`.
- `parse_file_symbols` needs a checkout of the repository, because it parses a file of the checkout, `src/devops_cli/ai/repomap.py:def parse_file_symbols`.
- `_gateway_tier_health` needs a client of the gateway over the network, `src/devops_cli/roadmap/implement/implement_step.py:def _gateway_tier_health`; every test passes its own `tier_health`, which `src/devops_cli/roadmap/implement/implement_step.py:2185:tier_health: Callable[[Sequence[str]], Mapping[str, bool]] | None = None,` takes.
- The plan introduces no command and no program: each verify runs `uv run devops ci test` or `uv run devops ci docs`, and the runner image holds `uv`, `devops` and `pytest` as runner tools. The tests double the process edges with `tests/support/fakes` and reach no network, no cluster and no real scanner, so no failure class is new and no pod setting changes.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tier_move.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_one_tier.py` and `uv run devops ci docs`.

## Existing Tool Considered

pydantic-ai covers the retries and the message history of a model call but changes no strategy between rounds, so the step builds its own round strategy: about 70k tokens to build, 3k tokens a quarter to keep, 10k tokens to fix one miss, and about 4 hours.

## Dependencies

None.
