# Proposal

## Why

The research sweep finds advisories and releases that mention a component, and a raw match says nothing about how this project uses that component (#3909). A list of every match makes noise, and a person stops reading it. The judge reads the store, the repository and the component list with four read-only tools and returns one typed judgment for each record. A plain function checks every cited record id and URL against the store and files the intake candidate, so a finding that the store does not support never reaches intake.

## What Changes

- Add `src/devops_cli/research/judge.py` with `build_judge_toolset` and `build_judge_agent`, which build a pydantic-ai agent on the project's `build_agent` with four read-only tools, and with `JudgeFinding`, which holds affects_us, why, severity, action, evidence record ids and evidence URLs.
- Add the plain citation check: `check_judged_citations` drops a finding whose record id or URL the store does not hold and counts the drop, and `file_judged_findings` files the candidate through the roadmap intake entry point that the caller passes in.
- Add `INSTRUCTION_OVERRIDE_PATTERN` and `_scan_instruction_override` to `src/devops_cli/security/prompt_injection.py`; the detector matches an override addressed to the reader and leaves each existing detector's answer unchanged.
- Add `judge_records`, `withheld_record_ids`, `JudgeLimits`, `JudgeStop` and `JudgeReport`, so a flagged record reaches no model call and no finding, and a limit stop names its setting and value.
- Register `research.judge.record_limit` and `research.judge.daily_token_limit` in `src/devops_cli/config/settings.py` and `src/devops_cli/config/defaults.py`, add their two variables to `tests/security/test_config_declarations.py`, and regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`.
- Add the 20 labeled findings, `false_negative_ids` and `judge_agreement_rate`, plus a marked live run that prints the rate for the pull request comment.
- The judge reads the records that the store of #3906 holds, and no group of this change creates that store.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-judge`: Read-only tool set, No write tool, Typed finding, Only the citation check files a candidate, Unknown record id, Unknown URL, Injection before the model, Record limit, Daily token limit, Limits are settings, Labeled evaluation

### Modified Capabilities

- `prompt-injection-detection`: Instruction override detection

## Impact

- Code: `src/devops_cli/research/judge.py`, `src/devops_cli/security/prompt_injection.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`
- Documents: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`
- Tests: `tests/research/test_research_judge.py`, `tests/security/test_prompt_injection.py`, `tests/config/test_research_judge_limits.py`, `tests/security/test_config_declarations.py`, `tests/research/test_research_judge_eval.py`, `tests/research/test_research_judge_live.py`

## Feasibility

- The probes confirm the premise of the issue: "The path `src/devops_cli/research/sweep.py` is a file of the staging commit." and "The path `src/devops_cli/security/prompt_injection.py` is a file of the staging commit."
- `file_symbols` on `src/devops_cli/research/models.py` listed the pin model, the inventory models, the advisory finding and the sweep report, so the component list that the judge reads exists at the staging commit; `read_file` line 48 showed the frozen shape at `src/devops_cli/research/models.py:48: model_config = ConfigDict(frozen=True)`.
- `file_symbols` on `src/devops_cli/research/sweep.py` listed `finding_candidate` and `run_sweep`, and `read_file` lines 101-133 showed `src/devops_cli/research/sweep.py:101:def finding_candidate(finding: AdvisoryFinding)`, which builds the intake candidate of an actionable finding with `filed_by=Filer.AGENT`; the plain function follows its title and body rule.
- `search_code` for `def intake_candidate` found `src/devops_cli/roadmap/intake/intake.py:1601:def intake_candidate(`, the filing callable that the plain check receives as an argument; no group changes that file.
- `file_symbols` and `read_file` lines 144-234 of `src/devops_cli/security/prompt_injection.py` showed `scan_injection_line` at line 207 with the four detectors `_scan_unicode_tags`, `_scan_format_characters`, `_scan_delimiters` and `_scan_markdown_exfil`, and `scan_injection_text` at line 217; none of the four matches a plain instruction, so the change adds one narrow detector.
- The new detector keeps every existing case: it requires the second person ("your rules", "your instructions"), so the phrase of the INJ002 case still yields one finding, as `tests/security/test_prompt_injection.py:49:assert len(findings) == 1` requires; group 3 adds a case that pins this narrowness, and no group edits an existing test case.
- `file_symbols` on `src/devops_cli/ai/client/factory.py` listed `get_task_model` at line 142 and `build_agent` at line 252, and `read_file` lines 252-304 showed that `build_agent` takes `output_type`, `instructions`, `tools` and `toolsets`; `tests/ai/client/test_agent_factory.py:206: agent = build_agent(FunctionModel(reply), tools=[lookup])` showed the offline pattern with a FunctionModel.
- `search_code` for `TestModel` found `tests/ai/agents/test_ai_agent_capabilities.py:105: from pydantic_ai.models.test import TestModel`, so the tool-inventory and typed-output tests run on pydantic-ai's own test model with no network and no token spend.
- `read_file` lines 350-373 of `src/devops_cli/ai/toolsets/__init__.py` showed the helper `create_function_toolset`, which builds a toolset from a sequence of tools or callables, and `tests/roadmap/test_roadmap_mcp.py:206: tools = await toolset.list_tools()` showed that a toolset lists its tools by name, which the tool-inventory test uses to count the four and refuse a fifth.
- `references` for `withheld_record_ids` answered "No line of the commit holds 'withheld_record_ids'." and `references` for `LABELED_FINDINGS` answered the same, so both names are new; `references` for `agreement_rate` answered "src/devops_cli/ai/run_store.py: 1 (line 620)", which is why the rate function is named `judge_agreement_rate` and a decision leaves that module unchanged.
- The declaration test compares the variables of the settings: `read_file` line 136 showed `tests/security/test_config_declarations.py:136:_VARIABLES_OF_LATER_SETTINGS = frozenset(`, whose comment says that each setting added after the declaration moved onto the fields has its variable by the rule, so group 6 adds the two new variable names there.
- `CONTRIBUTING.md:204:| Environment variable |` says that a settings field declares its variable on the field and its description with `Field(description=...)`, and that `tests/security/test_config_declarations.py` holds the set of variables while `docs/ENV_VARS.md` is generated from the declarations, so each new setting declares its variable on its field.
- `read_file` lines 1448-1460 of `src/devops_cli/config/settings.py` showed a settings section whose fields each carry an environment-variable annotation and a `Field(description=...)` default, the pattern that the two new research judge fields follow.
- `search_code` for `docs generate` and `read_file` lines 58-84 of `src/devops_cli/commands/docs.py` showed `src/devops_cli/commands/docs.py:60:def generate(` with only the options `--output-dir`, `--format` and `--check`, so group 8 regenerates the two documents with `uv run devops docs generate` and no option.
- Precondition of `rag_search` of `src/devops_cli/ai/tools/builtin_tools.py`: a client of the Qdrant service and a network. The repository-search tool wraps it; the tests pass a fake corpus and reach neither.
- Precondition of `build_agent` and `get_task_model` of `src/devops_cli/ai/client/factory.py`: a client of the model gateway. The judge builds its agent on the model they return, and each test passes a `FunctionModel` or a `TestModel` in place of it.
- Precondition of `intake_candidate` of `src/devops_cli/roadmap/intake/intake.py`: a client of the GitHub API and the roadmap intake store. The plain check takes it as an argument, and the test passes a recorder in place of it.
- Precondition of the store that #3906 delivers: a client of the Qdrant service. It satisfies the `ReadOnlyCorpus` protocol at the call site, and no test reaches it.
- The verifies run `uv run devops ci test <path>` and `uv run devops ci docs` with the uv, python and pytest of the runner image, so no program is NOT_IN_RUNNER; the pod keeps runAsNonRoot true, readOnlyRootFilesystem true, capabilities.drop ALL, allowPrivilegeEscalation false and seccompProfile RuntimeDefault.
- The live evaluation is NOT_IN_RUNNER, because the runner holds no model gateway client; its failure class is provider with the action retry, and it is a manual process that no verify runs.
- The first check against the real system is `uv run devops ci test tests/research/test_research_judge.py` after group 1, and the last is `uv run devops ci docs` after group 8.
- The two limits are the settings `research.judge.record_limit` and `research.judge.daily_token_limit`, each declared with a default, and each stop reports the setting name and its value.
- The last review asked for a code span of a class name in three feasibility lines and two design texts, and for the fifth acceptance criterion; those lines now name no class, and group 9 delivers the criterion with the words "PR comment" copied from the issue.

## Existing Tool Considered

pydantic-ai 2.59.0 with pydantic-ai-harness 0.59.0, both pinned in the staged tree, with the project's own `build_agent` factory, `create_function_toolset`, the injection scanner and pydantic-ai's `TestModel` and `FunctionModel`, cover the agent loop, the typed output, the tool schema, the offline test models and the scan. They lack the judgment prompt, the four read-only record tools, the citation check, the two limit stops and the labeled fixture, which this change adds at about 70k tokens to build and check, about 3k tokens a year to keep and fix, and about 6 hours elapsed. It deletes no code.

## Dependencies

- #3906: the judge reads the records that the store of #3906 holds and checks every cited record id and URL against it, so that item comes first.
