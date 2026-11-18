# Proposal

## Why

Refine, the alternatives check and the stage planner ask the same kinds of questions again each round, and nothing reads a stored answer first, so every round pays again for the same web search (#3915). This change gives those three jobs ask-mode tools that answer from an index of fetched pages before they reach the web, stores each new answer with its question, URL, date, hash and expiry, and measures the candidate on recorded questions.

## What Changes

- Add `RoadmapResearchConfig` with `max_calls_per_run` and `answer_expiry_days` to `src/devops_cli/config/settings.py`, the two defaults to `src/devops_cli/config/defaults.py`, and both names to the limits test and the config-declaration test.
- Add the method `page_of` and the label `TOOLSET_STAGE` to `src/devops_cli/roadmap/page_fetch.py`, so the https check, the named-URL check and the cap of `CONST_ROADMAP_PAGE_FETCH_MAX` stay in one boundary and a caller can hold the `PageText` of a fetch.
- Add `src/devops_cli/roadmap/ask_index.py` with `ResearchIndex` and `IndexedAnswer`: one SQLite file under `data.dir` that holds the question, the page text, the fetch URL, the fetch date, the SHA-256 hash and the expiry, and matches an exact term and a regular expression over the stored text.
- Add `src/devops_cli/roadmap/ask_tools.py` with `ResearchAsk`, the mixin `ResearchToolset` and `research_ask`: `research_lookup` answers a fresh record with no request and makes one `web_search` call and one page fetch on a miss or a stale row, `research_grep` matches stored text, and both stop at `roadmap.research.max_calls_per_run`.
- Add `src/devops_cli/roadmap/research_measure.py` with `recorded_questions` and `measure_research`, which report the hit rate and the cost per question of the candidate against the chain's web search on the 10 recorded questions.
- Give the two ask-mode tools to `InvestigationTools` of `src/devops_cli/roadmap/refine/refine_investigation.py` and to `AlternativesTools` of `src/devops_cli/roadmap/alternatives.py`.
- Name `research_lookup` and `research_grep` in `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md` before the registry names them, because `tests/roadmap/stage/test_roadmap_stage_toolbox.py` compares the prompt with the tools of the toolbox.
- Name both tools in `TOOLS` of `src/devops_cli/roadmap/tools.py` with the holder `_STAGE_EXTENDED`, and raise the pinned tool counts of `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py` and `tests/roadmap/stage/test_roadmap_stage_toolbox.py` to fifteen and sixteen.
- Build the research index of a plan run in `src/devops_cli/roadmap/stage/stage_toolbox.py`, so the stage planner reaches the two tools through its `extended` toolset and no second toolset path.
- Regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` with `uv run devops docs generate`, and describe the ask-mode tools, the index, the per-run limit and the `stage` toolset label in `docs/TELEMETRY.md`, `docs/CLUSTER.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md` and `docs/roadmap/stage.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-ask-tools`: A fresh answer makes no web call, An expired answer refreshes once, A query is refused before any request, The index holds pages, not search results, research_grep matches exact text and a pattern, The tools register through the toolset path, The per-run limit is a setting, The measure reports the hit rate and the cost per question

### Modified Capabilities

- `roadmap-page-fetch`: Each call is counted
- `roadmap-stage/toolbox`: The setting toolset chooses the tools of a plan run

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/roadmap/ask_index.py`, `src/devops_cli/roadmap/ask_tools.py`, `src/devops_cli/roadmap/research_measure.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`, `docs/CLUSTER.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`, `tests/config/test_roadmap_research_settings.py`, `tests/roadmap/test_roadmap_page_fetch.py`, `tests/roadmap/test_roadmap_ask_index.py`, `tests/roadmap/test_roadmap_ask_tools.py`, `tests/roadmap/test_roadmap_research_measure.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`

## Feasibility

- The probe confirms the cited paths word for word: The path `src/devops_cli/ai/web_search.py` is a file of the staging commit. The path `src/devops_cli/roadmap/page_fetch.py` is a file of the staging commit. The path `src/devops_cli/ai/page_text.py` is a file of the staging commit. The path `SECURITY.md` is a file of the staging commit.
- The probe confirms that the setting is new word for word: The path `roadmap.research.max_calls_per_run` is no file of the staging commit. No commit in the history deleted or renamed it, so the field is a thing this change creates.
- The staged chain holds three providers and no Brave provider: `src/devops_cli/ai/web_search.py:291:PROVIDERS: Final[dict[str, SearchProvider]] = {` builds its entries from `src/devops_cli/ai/web_search.py:293:for provider in (SearxngProvider(), DuckDuckGoProvider(), FirecrawlProvider())`.
- The staged `web_search` takes no keep argument: `src/devops_cli/ai/web_search.py:318:def web_search(query: str, *, limit: int = DEFAULT_WEB_SEARCH_LIMIT) -> list[SearchHit]:`, so the owner decision of 2026-11-07 that drops `keep` already holds in the code.
- The staged guard refuses the query before any provider runs: `src/devops_cli/ai/web_search.py:405:def _guard(query: str) -> None:` raises `src/devops_cli/ai/web_search.py:425:raise SearchQueryRefused(f"The search was refused: {reason}.")` after it finds a secret, a private address, an e-mail address or an internal host name.
- The page fetch boundary is the class at `src/devops_cli/roadmap/page_fetch.py:76:class PageFetch:`, beside the two labels `src/devops_cli/roadmap/page_fetch.py:49:TOOLSET_REFINE: Final[str] = "refine"` and `src/devops_cli/roadmap/page_fetch.py:50:TOOLSET_ALTERNATIVES: Final[str] = "alternatives"`. It refuses a URL that is not https at `src/devops_cli/roadmap/page_fetch.py:98:if urlsplit(key).scheme != "https":` and holds the cap at `src/devops_cli/roadmap/page_fetch.py:102:if self.fetches >= CONST_ROADMAP_PAGE_FETCH_MAX:`, with the staged cap `src/devops_cli/config/constants.py:3456:CONST_ROADMAP_PAGE_FETCH_MAX: Final[int] = 3` and `src/devops_cli/config/constants.py:3457:CONST_ROADMAP_PAGE_FETCH_MAX_CHARS: Final[int] = 8000`.
- The investigation tools are the class at `src/devops_cli/roadmap/refine/refine_investigation.py:211:class InvestigationTools:`, and it offers `fetch_page` only with a page fetch at `src/devops_cli/roadmap/refine/refine_investigation.py:391:if self.pages is not None:`; refine builds it with `src/devops_cli/roadmap/refine/refine.py:3097:tools = InvestigationTools(source=source, sha=sha, web=web.on, pages=pages)`.
- The stage tools read their names from the registry: `src/devops_cli/roadmap/stage/stage_tools.py:488:names = tool_names(holder)`, and `src/devops_cli/roadmap/stage/stage_tools.py:121:class StageTools(InvestigationTools):` shows that a method of the investigation tools is a tool of the planner once the registry names it.
- The registry holds one holder set per toolset: `src/devops_cli/roadmap/tools.py:46:_STAGE_EXTENDED: Final[frozenset[str]] = frozenset({HOLDER_STAGE_EXTENDED, HOLDER_STAGE_RESEARCH})`, and the staged research tool is `src/devops_cli/roadmap/tools.py:116:"search_web": _read(`.
- The staged counts of the two stage toolsets are pinned by `tests/roadmap/test_roadmap_tools.py:99:assert (check_tables(tables), {len(names) for names in tables.values()}) == ([], {10, 13})`, so the registry group raises the second count to 15 and the extended toolset to fifteen tools.
- The finding is a defect at its place, and the quotes show it: `tests/roadmap/stage/test_roadmap_stage_tools.py:52:_EXTENDED_TOOL_NAMES = [*_TOOL_NAMES, "references", "read_issue", "find_issues"]` and `tests/roadmap/stage/test_roadmap_stage_tools.py:53:_RESEARCH_TOOL_NAMES = [*_EXTENDED_TOOL_NAMES, "search_web"]` pin thirteen and fourteen names, and `tests/roadmap/stage/test_roadmap_stage_tools.py:160:assert [tool.name for tool in tools.tools()] == _EXTENDED_TOOL_NAMES` fails once the registry names fifteen. The registry group now changes that file, and its test names it.
- The same defect holds in a second file, so the registry group covers it too: `tests/roadmap/stage/test_roadmap_stage_toolbox.py:82:_EXTENDED_TOOLS = [*_TOOLS, "references", "read_issue", "find_issues"]` feeds `tests/roadmap/stage/test_roadmap_stage_toolbox.py:349:_TOOLS, _EXTENDED_TOOLS, [], [], []`, which compares the tools of the toolbox with the names of the prompt. So the prompt group lands before the registry group, and the toolbox file changes in the registry group.
- The extended prompt opens with a count that the registry group would make wrong: `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md:1:Three more tools are on for this run:`, so the prompt group states five and names both tools.
- The staged settings hold one member per job config: `src/devops_cli/config/settings.py:2103:class RoadmapConfig(BaseModel):` with `src/devops_cli/config/settings.py:2106:alternatives: AlternativesConfig = Field(default_factory=AlternativesConfig)`, so `research` joins the same class. The staged `data.dir` is `src/devops_cli/config/settings.py:2182:dir: Annotated[Path, Variable()] = Field(`, so the index file goes under `<data.dir>/research/index.sqlite3`.
- The staged digest is `src/devops_cli/roadmap/body_hash.py:43:def hash_text(text: str) -> str:`, the SHA-256 of a stripped text.
- `read_issue` for #3906 answers open with status/new, so its Qdrant store is not delivered and this change reads and writes its own SQLite file under `data.dir`. `read_issue` for #3877 answers closed and completed by merged pull request #6147.
- `references` and `search_code` answer that no file holds `research_lookup`, `research_grep`, `ResearchAsk`, `ResearchMeasure`, `RoadmapResearchConfig`, `recorded_questions`, `IndexedAnswer`, `ResearchIndex`, `research_ask` or `TOOLSET_STAGE` at the staged commit, and no file under `src/` defines `page_of`, so each is a name that this change adds.
- `web_search` of `src/devops_cli/ai/web_search.py` needs a network at the call, which `research_lookup` makes on a miss or a stale row and `measure_research` makes for the baseline.
- `fetch_page_text` of `src/devops_cli/ai/page_text.py` needs a client of the Crawl4AI service and a network at the call, which the page fetch at `src/devops_cli/roadmap/page_fetch.py:76:class PageFetch:` makes.
- `load_settings` of `src/devops_cli/config/settings.py` needs a configuration file at the call, which `research_ask` makes to read `data.dir` and `roadmap.research`.
- `recorded_questions` takes the comment texts and their dates that its caller read, so it needs no client of a service at the call.
- The verify programs are `uv run devops ci test <path>` and `uv run devops ci docs`. Both use `uv`, `python`, `pytest` and `devops`, which are in the runner image, under the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. A failing test is the class `test` with the action `repair`, and a failing docs row is the class `lint` with the action `repair`.
- The first checks against the real system are `uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py`, `uv run devops ci test tests/config/test_roadmap_research_settings.py`, `uv run devops ci test tests/roadmap/test_roadmap_ask_index.py`, `uv run devops ci test tests/roadmap/test_roadmap_ask_tools.py`, `uv run devops ci test tests/roadmap/test_roadmap_research_measure.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`, `uv run devops ci docs`, and the live check `uv run devops k8s searxng-check` of the search that the tools call.

## Existing Tool Considered

No open, maintained library covers the need: SearXNG, DuckDuckGo and Crawl4AI run a query or fetch a URL on every call, and SQLite and `re` of the standard library give only the rows and the match, not the store keyed by the question with a hash, an expiry and a refusal. The project builds the index and the tools: 60k tokens to build, keep and fix, and 2 hours of elapsed work.

## Dependencies

None.
