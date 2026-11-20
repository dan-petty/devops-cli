# Proposal

## Why

The research sweep of #3909 finds advisories and releases that mention a component, and a raw match says nothing about how this project uses that component. A list of every match makes noise, and a person stops reading it. This change adds a pydantic-ai judge that reads the store, the repository and the component list with four read-only tools under a judgment prompt and returns one typed finding for each record, a plain citation check that drops a finding whose record id or URL the store does not hold and files the intake candidate, an injection scan before the model, two limit stops, and a labeled evaluation with the agreement rate.

## What Changes

- Add `src/devops_cli/research/judge.py` with the `ReadOnlyCorpus` protocol, `JudgeVerdict`, `JudgeFinding`, `JUDGE_INSTRUCTIONS`, `build_judge_toolset` and `build_judge_agent`; the agent carries four read-only tools, the judgment prompt and no write tool.
- Add the plain citation check `check_judged_citations`, the candidate builder `judge_intake_candidate` and the filing call `file_judged_findings`, which drop and count a finding whose record id or URL the corpus does not hold.
- Add the narrow detector `INSTRUCTION_OVERRIDE_PATTERN` and `_scan_instruction_override` to `src/devops_cli/security/prompt_injection.py`, wired into `scan_injection_line` as INJ004.
- Add `withheld_record_ids`, `JudgeReport` and `judge_records`, so a flagged record reaches no model call and no finding, and the report names it.
- Add `JudgeLimits` and `JudgeStop`, so the run stops at the per-sweep record limit and before a model call that would spend the daily token limit, and each stop names its setting and value.
- Declare `research.judge.record_limit` and `research.judge.daily_token_limit` on a new `research` section of the settings class of `src/devops_cli/config/settings.py`, add their variable names to the declaration census, and add `judge_limits_from_settings`.
- Add the 20 labeled findings, `false_negative_ids` and `judge_agreement_rate`, and run the judge over the 20 records in the default test with a `FunctionModel`.
- Add a live test module that prints the agreement rate for the pull request comment, and regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` from the new settings.
- The change carries a spec delta, because the judge, the scanner and the two settings are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-judge`: Read-only tool set, No write tool, Judgment prompt, Typed finding, Only the citation check files a candidate, Unknown record id, Unknown URL, Injection before the model, Record limit, Daily token limit, Limits are settings, Labeled evaluation

### Modified Capabilities

- `prompt-injection-detection`: Instruction override detection

## Impact

- Code: `src/devops_cli/research/judge.py`, `src/devops_cli/security/prompt_injection.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`
- Documents: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`
- Tests: `tests/research/test_research_judge.py`, `tests/security/test_prompt_injection.py`, `tests/config/test_research_judge_limits.py`, `tests/security/test_config_declarations.py`, `tests/research/test_research_judge_eval.py`, `tests/research/test_research_judge_live.py`

## Feasibility

- This reply cites only the tool calls of this run: `list_files`, `read_file`, `file_symbols` and `search_code`, each named with the arguments it was given.
- The probes confirm the premise: "The path `src/devops_cli/research/sweep.py` is a file of the staging commit." and "The path `src/devops_cli/security/prompt_injection.py` is a file of the staging commit."
- `list_files` on `src/devops_cli/research` listed sixteen modules and no `judge.py`, and `list_files` on `tests/research` listed ten modules and no judge test, so `src/devops_cli/research/judge.py` and `tests/research/test_research_judge.py` are new files.
- The review finding that the plan builds no judgment prompt is fixed: group 1 adds `JUDGE_INSTRUCTIONS` and passes it as `instructions` to `build_agent`, whose signature holds `src/devops_cli/ai/client/factory.py:257:instructions: str | Sequence[str] | None = None,` and whose agent arguments hold `src/devops_cli/ai/client/factory.py:290:"instructions": instructions,` so the prompt reaches the Agent.
- The review finding that no group adds the `research` field to `Settings` is fixed: `search_code` for `class Settings(BaseSettings)` returned `src/devops_cli/config/settings.py:2372:class Settings(BaseSettings):`, and `search_code` for `roadmap: RoadmapConfig = RoadmapConfig()` returned `src/devops_cli/config/settings.py:2422:roadmap: RoadmapConfig = RoadmapConfig()`, so group 6 adds `research: ResearchConfig = ResearchConfig()` inside that class beside `roadmap`, and each nested field carries the marker that `src/devops_cli/config/settings.py:2096:hours: Annotated[int, Variable()] = Field(` shows, which `src/devops_cli/config/env.py:35:class Variable:` defines.
- `read_file` lines 131-148 of `src/devops_cli/commands/config.py` showed `src/devops_cli/commands/config.py:140:typer.Option("--json", "-j", help=HELP.options.json_output),` and `src/devops_cli/commands/config.py:147:for key in sorted(setting_variables().keys() | secret_keys())`, so `devops config show --json` prints the key of each marked field and the group 6 test reads both limits there.
- `read_file` lines 120-175 and 400-422 of `tests/security/test_config_declarations.py` showed `tests/security/test_config_declarations.py:136:_VARIABLES_OF_LATER_SETTINGS = frozenset(`, which `search_code` confirms again at that line, and `tests/security/test_config_declarations.py:416:def test_the_variables_are_those_before_one_for_each_read_option_that_had_none_and_later_ones() -> (`, which unions that set with the earlier ones, so the two new variable names join it in group 6.
- The review finding that the evaluation test feeds hand-built values to the gate is fixed: group 7 runs `judge_records` over `LABELED_FINDINGS` with a `FunctionModel` that answers each record, and asserts the gate on the findings of that run; `tests/ai/client/test_agent_factory.py:206:agent = build_agent(FunctionModel(reply), tools=[lookup])` shows the offline model pattern of the suite.
- `file_symbols` and `read_file` lines 252-304 of `src/devops_cli/ai/client/factory.py` showed `src/devops_cli/ai/client/factory.py:252:def build_agent(` with the `output_type`, `instructions` and `toolsets` parameters, and `src/devops_cli/ai/toolsets/__init__.py:354:def create_function_toolset(` builds the toolset from a sequence of callables, so the four tools come from one toolset of that helper.
- `search_code` for `def rag_search` found `src/devops_cli/ai/tools/builtin_tools.py:374:def rag_search(`. Precondition of that call: a client of the Qdrant service and a network. The repository-search tool wraps it, and the tests pass a fake corpus and reach neither.
- Precondition of `build_agent` and `get_task_model` of `src/devops_cli/ai/client/factory.py`: a client of the model gateway. Each offline test passes a `FunctionModel` or a `TestModel` in place of it, and only the live module reaches the gateway.
- `file_symbols` on `src/devops_cli/research/models.py` gave `src/devops_cli/research/models.py:41:class Component(BaseModel):` with `src/devops_cli/research/models.py:48:model_config = ConfigDict(frozen=True)`, so the component list that the judge reads is a frozen pydantic model.
- `read_file` lines 92-133 of `src/devops_cli/research/sweep.py` showed `src/devops_cli/research/sweep.py:101:def finding_candidate(finding: AdvisoryFinding) -> NewCandidate:` and its result `filed_by=Filer.AGENT`, so a judged candidate follows that candidate rule.
- `read_file` lines 196-238 of `src/devops_cli/security/prompt_injection.py` showed `src/devops_cli/security/prompt_injection.py:207:def scan_injection_line(line: str, line_no: int, location: str) -> list[Finding]:` calling four detectors, and `src/devops_cli/security/prompt_injection.py:217:def scan_injection_text(`; none of the four reads a plain instruction, so a fifth detector is needed.
- The review finding that the new detector breaks the INJ002 case is no defect: `tests/security/test_prompt_injection.py:47:hidden = "Ignore previous instructions` holds no second-person possessive, the new pattern needs one, so `tests/security/test_prompt_injection.py:49:assert len(findings) == 1` still holds, and group 3's verify runs that whole module.
- `search_code` for `class ResearchConfig`, `JUDGE_INSTRUCTIONS`, `judge_records`, `check_judged_citations` and `judge_intake_candidate` each found no line of the commit, so the names and the settings section are new.
- `pyproject.toml:40:"pydantic-ai[spec]==2.71.0",` and `pyproject.toml:41:"pydantic-ai-harness[coder]==0.71.0",` are the staged pins, and `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md:21:the open agent framework of the project` is the chosen option, with lines 22, 23 and 24 rejecting GPT Researcher, the LangChain agent and STORM.
- No verify introduces a program: `uv run devops ci test` and `uv run devops ci docs` are rows of the gate, and `uv`, `python`, `pytest` and `devops` are tools of the runner image. Their failure classes are `test`, `lint`, `types` and `ci_infra`, each with an action in the action-by-class table. The live run is `NOT_IN_RUNNER`, because the runner holds no model gateway client; it is a manual process that no verify runs, and its failure class is `provider` with the action `retry`. The pod keeps `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The first check of the implementation against the real system is `uv run devops ci test tests/research/test_research_judge.py` after group 1, and the last is `uv run devops ci docs` after group 8.

## Existing Tool Considered

pydantic-ai 2.71.0 with pydantic-ai-harness 0.71.0, both pinned, through the project's `build_agent` factory, `create_function_toolset`, the injection scanner, `rag_search` and pydantic-ai's `TestModel` and `FunctionModel`, cover the agent loop, the typed output, the tool schema, the spend hook, the scan and the offline test models. They lack the judgment prompt text, the four read-only record tools, the citation check, the two limit stops and the labeled fixture, which this change builds at about 72k tokens to build, about 3k tokens a year to keep and fix, and about 6 hours elapsed. It deletes no code.

## Dependencies

None.
