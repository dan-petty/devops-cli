# Tasks

## 1. Body key questions by number

- [x] Add failing tests: a body whose key questions are answered in place, by indented lines, or are statements sends no body question and has no open question; an unanswered body question that no answer names is open; an answer that names its number closes it
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Add `body_questions`, send `body_questions` in the proposal request, add `QuestionAnswer.body_question`, and check the numbers in `validate_proposal`; delete `_normalize_question` and the substring match
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`

## 2. Decisions with options and the person kind

- [x] Add failing tests: a sourced decision renders "(best practice)" with its chosen and rejected options and can be Ready; an unsourced decision renders "(proposed)"; a `person` question waits on a person with "(a person decides)"
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Add `DesignOption`, `QuestionAnswer.options` and the kind `person`; mark and render decisions; update `roadmap_refine_proposal.md` and its field test
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`

## 3. The investigation

- [x] Add failing tests: a fact that the investigation sources with a file read makes the item Ready; a proposal with nothing open makes no investigation request; a spent budget keeps the first proposal; the tools read only the pinned commit; web search is absent without a key and capped with one; the investigation's errors map to refine's classes; the run's usage reaches the spend ledger
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py`
- [x] Add `get_task_model` to the client factory, `refine_investigation.py` with its tools, and `roadmap_refine_investigation.md`; call the investigation from `refine_one_item`; let `ModelFake` answer a pydantic model as JSON text
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py`
- [x] Delete `ResearchPlan`, `run_research_step`, `roadmap_refine_research.md`, the `search_results` of the proposal request and their tests
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_common_tools.py tests/test_roadmap_dry_runs.py`
- [x] Add failing tests: the function tools go when the budget has room for no more than the answer; one turn whose calls pass the budget keeps the first proposal; `ModelFake` answers a request that takes only an output tool with the call of that tool; the entry point turns off pydantic-ai's banner
  - Verification: `uv run devops ci test tests/test_roadmap_refine_investigation.py tests/test_cli_startup_imports.py`
- [x] Answer through pydantic-ai's output tool, add the `PrepareTools` budget capability, and set `PYDANTIC_AI_NO_BANNER` in the entry point
  - Verification: `uv run devops ci test tests/test_roadmap_refine_investigation.py tests/test_cli_startup_imports.py tests/test_roadmap_refine.py`

## 4. Web search state and documentation

- [x] Add a failing test: a round on a public repository with no web search key reports that web search is off and why
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Add `RefinePlan.web_search_off` and its report line; update the module docstring, the `refine` help text and `common_tools.py`'s docstring
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 5. Web search through Firecrawl

- [x] Add failing tests: `firecrawl_search` posts the query and the limit with the key as a Bearer token and returns `data.web`, raises on an HTTP error and on a reply with no `data.web` list; the egress level, the secret registry, the audit keys and `devops k8s push-secrets` name `firecrawl.api_key`, `firecrawl_api_key` and `DEVOPS_CLI_FIRECRAWL_API_KEY`; a round with no Firecrawl key says so
  - Verification: `uv run devops ci test tests/test_common_tools.py tests/test_http_egress.py tests/test_secret_resolution.py tests/test_config_audit_keys.py tests/test_k8s_push_secrets.py tests/test_k8s.py tests/test_roadmap_refine.py`
- [x] Replace `tavily_search` with `firecrawl_search`, and Tavily's setting, variable, keyring entry and secret row with Firecrawl's; regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 6. Review fixes

- [x] Add failing tests: a wrapped question, a paragraph or a code block after the list, sub-headings and the next section follow CommonMark; a copied mark gives way to the earned one; only a quoted owner decision is the owner's; the investigation hears of a decision whose sources failed; a URL source keeps its closing bracket out of the link; each request of the run streams; a tool answers a binary file, a file that is not UTF-8 and a NUL byte as text; a stopped run keeps the first proposal; the tool-call half of the budget removes the tools; a public repository with a key settles a fact from the web; a gateway model's run is recorded under the gateway
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py`
- [x] Parse the body's key questions with markdown-it-py; strip copied marks; match an owner decision only when the answer quotes it; send unsourced decisions to the investigation; stream each request; make the tools raise nothing; return `InvestigationStopped` for a spent budget or a model that breaks the rules; record a gateway run under the gateway; let `ModelFake` resolve its request parameters
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py tests/test_model_contract.py tests/test_model_fixture.py`

## 7. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2398-refine-investigates-questions`
- Pending a person: set `firecrawl.api_key` with `devops config set` and add it to Secret `devops/devops-cli` with `devops k8s push-secrets`, so refine can search the web.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
