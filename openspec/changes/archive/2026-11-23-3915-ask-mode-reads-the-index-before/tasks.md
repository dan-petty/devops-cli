# Tasks

## 1. Make the ask-mode call limit and the answer expiry roadmap settings

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`, `tests/config/test_roadmap_research_settings.py` (new).
Adds: `RoadmapResearchConfig`, `DEFAULT_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN`, `DEFAULT_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS`

- [x] 1.1 `tests/config/test_roadmap_research_settings.py` fails first: `roadmap.research.max_calls_per_run` reads `DEVOPS_CLI_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN` and defaults to `DEFAULT_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN` of 20, `roadmap.research.answer_expiry_days` reads `DEVOPS_CLI_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS` and defaults to `DEFAULT_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS` of 30, and `tests/security/test_config_declarations.py` fails until both variable names join `_VARIABLES_OF_LATER_SETTINGS`
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_research_settings.py` fails on the base
- [x] 1.2 Add `DEFAULT_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN` and `DEFAULT_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS` to `src/devops_cli/config/defaults.py`, and the class `RoadmapResearchConfig` with the fields `max_calls_per_run` and `answer_expiry_days`, each `Annotated[int, Variable()]`, to `src/devops_cli/config/settings.py` beside `src/devops_cli/config/settings.py:2103:class RoadmapConfig(BaseModel):`, which gains `research: RoadmapResearchConfig = Field(default_factory=RoadmapResearchConfig)`. Add both defaults to the limits table of `tests/roadmap/test_roadmap_limit_classes.py` and both variable names to `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_research_settings.py` passes

## 2. Hand the fetched page back from the page fetch boundary

Kind: behavior. Reads: `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/ai/page_text.py`, `tests/roadmap/test_roadmap_page_fetch.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/page_fetch.py`, `tests/roadmap/test_roadmap_page_fetch.py`.
Adds: `page_of`, `TOOLSET_STAGE`

- [x] 2.1 `tests/roadmap/test_roadmap_page_fetch.py` fails first: `page_of` answers the `PageText` of an https URL that a search of the run offered, refuses a URL that nothing named before any request, answers the limit once the run reaches `CONST_ROADMAP_PAGE_FETCH_MAX` fetches, a `page_of` call of a page fetch labeled `TOOLSET_STAGE` counts one point with the toolset `stage`, which is the scenario A page read of the stage planner is counted, and `fetch` frames the same page and gives the same refusals as before
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py` fails on the base
- [x] 2.2 Move the body of `src/devops_cli/roadmap/page_fetch.py:93:def fetch(self, url: str) -> ToolReturn:` into `page_of`, which keeps the https check, the named-URL check, the count against `CONST_ROADMAP_PAGE_FETCH_MAX` at `src/devops_cli/roadmap/page_fetch.py:102:if self.fetches >= CONST_ROADMAP_PAGE_FETCH_MAX:`, the call of `fetch_page_text`, the `fetched` set and the `ROADMAP_PAGE_FETCHES_TOTAL` counter, and answers `PageText | ToolReturn`. Add `TOOLSET_STAGE` beside `src/devops_cli/roadmap/page_fetch.py:49:TOOLSET_REFINE: Final[str] = "refine"` and `src/devops_cli/roadmap/page_fetch.py:50:TOOLSET_ALTERNATIVES: Final[str] = "alternatives"`, and make `fetch` call `page_of`, frame the page it answers, and answer a refusal or an error unchanged
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py` passes

## 3. Store each fetched page under the question it answered

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/roadmap/page_fetch.py`. Changes: `src/devops_cli/roadmap/ask_index.py` (new), `tests/roadmap/test_roadmap_ask_index.py` (new).
Adds: `IndexedAnswer`, `ResearchIndex`

- [x] 3.1 `tests/roadmap/test_roadmap_ask_index.py` fails first and holds the scenario A new answer writes page fields only: a written row holds the page text, the fetch URL and the fetch date with the question, the hash and the expiry, and holds no title, snippet, rank or age; a row is fresh while its expiry is in the future and its hash matches, a row is read back by its question, and an exact term and a regular expression match the stored text
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ask_index.py` fails on the base
- [x] 3.2 Add `IndexedAnswer` and `ResearchIndex` to `src/devops_cli/roadmap/ask_index.py`. The store opens the SQLite file `<data.dir>/research/index.sqlite3` under `src/devops_cli/config/settings.py:2182:dir: Annotated[Path, Variable()] = Field(`, creates the folder on the first write, and keeps one row for each question and URL. `src/devops_cli/roadmap/body_hash.py:43:def hash_text(text: str) -> str:` gives the SHA-256 digest of the question and the page text, and the module matches a term with `LIKE` and an `ESCAPE` and a pattern with `re`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ask_index.py` passes

## 4. Answer a question from the index before the web

Kind: behavior. Reads: `src/devops_cli/ai/web_search.py`, `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/roadmap/ask_index.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/ask_tools.py` (new), `tests/roadmap/test_roadmap_ask_tools.py` (new).
Adds: `ResearchAsk`, `ResearchToolset`, `research_ask`, `research_lookup`, `research_grep`

- [x] 4.1 `tests/roadmap/test_roadmap_ask_tools.py` fails first and holds the scenarios A fresh record answers the lookup, An expired record causes one web call, A query with a private address, A regular expression over stored text and The limit stops a run: `research_lookup` answers a fresh record with zero `web_search` calls, an expired record makes one `web_search` call and one `page_of` call and writes the new row, a term with an RFC 1918 address is refused before any request, `research_grep` returns the one matching page with its URL, and one call over `roadmap.research.max_calls_per_run` answers that the limit is reached
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ask_tools.py` fails on the base
- [x] 4.2 Add `ResearchAsk`, the mixin `ResearchToolset` and `research_ask` to `src/devops_cli/roadmap/ask_tools.py`. `ResearchAsk` holds the `ResearchIndex`, the run's page fetch, `max_calls` from `roadmap.research.max_calls_per_run` and the count of calls: `lookup` answers a fresh record with no request, else calls `src/devops_cli/ai/web_search.py:318:def web_search(query: str, *, limit: int = DEFAULT_WEB_SEARCH_LIMIT) -> list[SearchHit]:` once, offers the hit URLs to `page_of` of `src/devops_cli/roadmap/page_fetch.py`, writes the row and answers the text with its URL and date, and it answers the refusal of `src/devops_cli/ai/web_search.py:405:def _guard(query: str) -> None:` and the message of the limit. `grep` answers each stored page that holds the term or matches the pattern with its URL. `ResearchToolset` declares `research` and the two tools `research_lookup` and `research_grep`, and `research_ask` answers None when the run has no page fetch
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ask_tools.py` passes

## 5. Measure the candidate against the chain's web search

Kind: behavior. Reads: `src/devops_cli/roadmap/ask_tools.py`, `src/devops_cli/ai/web_search.py`, `src/devops_cli/roadmap/ask_index.py`. Changes: `src/devops_cli/roadmap/research_measure.py` (new), `tests/roadmap/test_roadmap_research_measure.py` (new).
Adds: `ResearchQuestion`, `ResearchMeasure`, `recorded_questions`, `measure_research`

- [x] 5.1 `tests/roadmap/test_roadmap_research_measure.py` fails first and holds the scenario The measure runs on the recorded questions: `recorded_questions` answers at most 10 questions from the comment texts and dates that the test hands it, `measure_research` runs each question through a fresh `ResearchAsk` and through `web_search` of `src/devops_cli/ai/web_search.py:318:def web_search(query: str, *, limit: int = DEFAULT_WEB_SEARCH_LIMIT) -> list[SearchHit]:`, and `ResearchMeasure` holds the hit rate and the cost per question of each side
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_research_measure.py` fails on the base
- [x] 5.2 Add `ResearchQuestion`, `ResearchMeasure`, `recorded_questions` and `measure_research` to `src/devops_cli/roadmap/research_measure.py`. `recorded_questions` takes the comment texts and their dates that the caller read and answers at most 10 questions of the last 30 days, `measure_research` runs each question through the candidate of `src/devops_cli/roadmap/ask_tools.py` and through the chain's `web_search` with no index, counts the hits, the provider requests and the elapsed time of each side, and `ResearchMeasure` reports the hit rate and the cost per question as a list of markdown lines for the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_research_measure.py` passes

## 6. Give refine's investigation the two ask-mode tools

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/ask_tools.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`.

- [x] 6.1 `tests/roadmap/refine/test_roadmap_refine_investigation.py` fails first and holds the scenario The refine, alternatives and stage toolsets hold the new tools for refine's side: `InvestigationTools` offers `research_lookup` and `research_grep` after `fetch_page` when the round has a page fetch, and offers neither when it has none
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py` fails on the base
- [x] 6.2 Make `src/devops_cli/roadmap/refine/refine_investigation.py:211:class InvestigationTools:` extend `ResearchToolset` and append `self.research_lookup` and `self.research_grep` in `tools()` when `research` is set, beside the page fetch at `src/devops_cli/roadmap/refine/refine_investigation.py:391:if self.pages is not None:`. `src/devops_cli/roadmap/refine/refine.py:3097:tools = InvestigationTools(source=source, sha=sha, web=web.on, pages=pages)` gains `research=research_ask(pages, TOOLSET_REFINE)`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py` passes

## 7. Give the alternatives check the two ask-mode tools

Kind: behavior. Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/ask_tools.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`, `tests/roadmap/test_roadmap_alternatives_job_result.py`, `tests/roadmap/test_roadmap_alternatives_one_write.py`, `tests/roadmap/test_roadmap_alternatives_project_facts.py`, `tests/roadmap/test_roadmap_alternatives_recheck.py`, `tests/roadmap/test_roadmap_alternatives_reply_fixable.py`, `tests/roadmap/test_roadmap_alternatives_search.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_run_adapter_imports.py`, `tests/roadmap/test_roadmap_run_row_cadence.py`, `tests/roadmap/test_roadmap_trust.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 7.1 `tests/roadmap/test_roadmap_alternatives.py` fails first and holds the scenario The refine, alternatives and stage toolsets hold the new tools for the check's side: `AlternativesTools` offers `research_lookup` and `research_grep` after `fetch_page` when the check has a page fetch, and offers neither when it has none
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 7.2 Make `src/devops_cli/roadmap/alternatives.py:320:class AlternativesTools:` extend `ResearchToolset`, keep its `pages` field, and append both tools in `tools()` when `research` is set, beside the page fetch at `src/devops_cli/roadmap/alternatives.py:485:if self.pages is not None:`. The place that builds the tools at `src/devops_cli/roadmap/alternatives.py:1258:tools = AlternativesTools(store=store, pages=pages)` passes `research=research_ask(pages, TOOLSET_ALTERNATIVES)`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 8. Name the two ask-mode tools in the extended prompt

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 8.1 Add two bullets to the `When to call them` list of `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`: call `research_lookup` for a question that an earlier round may have answered, and `research_grep` for an exact term or a pattern over the pages that the index holds. Name both tools in the list of the first line and change that line to `Five more tools are on for this run:`. Add the assertion of the two names, with the first line, to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. This group lands before the registry group, because `tests/roadmap/stage/test_roadmap_stage_toolbox.py` compares the tools of the toolbox with the names of the prompt
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 9. Name the two ask-mode tools in the stage registry

Kind: behavior. Reads: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/tools.py`, `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.

- [x] 9.1 `tests/roadmap/stage/test_roadmap_stage_tools.py` fails first: `_EXTENDED_TOOL_NAMES` holds `research_lookup` and `research_grep` after `find_issues`, so the base, extended and research toolsets hold 10, 15 and 16 names at `tests/roadmap/stage/test_roadmap_stage_tools.py:160:assert [tool.name for tool in tools.tools()] == _EXTENDED_TOOL_NAMES`; `_EXTENDED_TOOLS` of `tests/roadmap/stage/test_roadmap_stage_toolbox.py` holds the same two names, so the extended prompt names every tool that the toolbox offers; and the count set of `tests/roadmap/test_roadmap_tools.py` is `{10, 15}`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py` fails on the base
- [x] 9.2 Add `research_lookup` and `research_grep` to `TOOLS` of `src/devops_cli/roadmap/tools.py` with the holder `_STAGE_EXTENDED` and a one-line purpose each, after `find_issues` and before `search_web`, so `src/devops_cli/roadmap/stage/stage_tools.py:488:names = tool_names(holder)` offers them through the methods that the investigation tools hold. Add the two names to `_EXTENDED_TOOL_NAMES` of `tests/roadmap/stage/test_roadmap_stage_tools.py` and to `_EXTENDED_TOOLS` of `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, raise the count set of `tests/roadmap/test_roadmap_tools.py` at `tests/roadmap/test_roadmap_tools.py:99:assert (check_tables(tables), {len(names) for names in tables.values()}) == ([], {10, 13})` to `{10, 15}`, and correct the counts that the two test names and the docstring state
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py` passes

## 10. Give the stage planner a research index of its run

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/ask_tools.py`, `src/devops_cli/roadmap/page_fetch.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/telemetry/test_roadmap_stage_steps.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_jev_screen.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, `tests/roadmap/stage/test_roadmap_stage_review_rounds.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/roadmap/stage/test_stage_jev_shadow.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_bounds.py`, `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/steps/test_roadmap_fix_plan_trace.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.

- [x] 10.1 `tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails first and holds the scenario The refine, alternatives and stage toolsets hold the new tools for the planner's side: a plan run with `crawl4ai.url` set answers a fresh stored record from `research_lookup` with no `web_search` call, makes one `web_search` call and one page fetch on an expired record, and refuses a term with an RFC 1918 address before any request; a plan run without `crawl4ai.url` answers that the index is off; a run whose `roadmap.stage.toolset` is unset offers fifteen tools under the value `extended`, and a run of `research` offers sixteen with `search_web`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [x] 10.2 In `ToolboxClient` of `src/devops_cli/roadmap/stage/stage_toolbox.py`, build a page fetch labeled `TOOLSET_STAGE` and `research_ask` of it when the settings name `crawl4ai.url`, and pass it as `research` to the `StageTools` that the client makes at `src/devops_cli/roadmap/stage/stage_toolbox.py:147:self._tools = StageTools(`. The two tools answer that the index is off when `research` is None, as `search_web` answers for a run that has no web
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` passes

## 11. Regenerate the settings documents

Kind: other. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/docs/generator.py`. Changes: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 11.1 Run `uv run devops docs generate` with no extra option, so `docs/CONFIGURATION.md` lists `roadmap.research` with its two keys and `docs/ENV_VARS.md` lists `DEVOPS_CLI_ROADMAP_RESEARCH_MAX_CALLS_PER_RUN` and `DEVOPS_CLI_ROADMAP_RESEARCH_ANSWER_EXPIRY_DAYS` with their descriptions
  - Verification: `$ uv run devops ci docs` passes
- [x] 11.2 Run `uv run devops docs generate` and commit the two regenerated documents
  - Verification: `$ uv run devops ci docs` passes

## 12. Describe the ask-mode tools, the index and the stage label

Kind: other. Reads: `docs/TELEMETRY.md`, `docs/CLUSTER.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/stage.md`. Changes: `docs/TELEMETRY.md`, `docs/CLUSTER.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/stage.md`.

- [x] 12.1 Edit the counter row of `docs/TELEMETRY.md` so that the label `toolset` names `refine`, `alternatives` and `stage`. Edit `docs/CLUSTER.md` and `docs/roadmap/stage.md` so that the toolset `extended` names `research_lookup` and `research_grep`, and describe `research_lookup`, `research_grep`, the store-first rule, the refusal of the query guard and the per-run limit in `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md` and `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs` passes
- [x] 12.2 Edit `docs/TELEMETRY.md`, `docs/CLUSTER.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md` and `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: Tests that fail on the base: a fresh stored answer means no web call; an expired one means one web call and an update.
- Group 4: A test: a query that holds a secret pattern, a private address or an e-mail address is refused before any request.
- Group 5: Measure moved from #3877: the candidate runs on 10 recorded questions from the alternatives and refine comments of the last 30 days. The PR comment gives the hit rate and the cost per question against the Firecrawl search of today.
- Group 6: The tools register for the jobs through the existing toolset path; the per-run limit is a setting.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
