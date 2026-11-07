# Tasks

## 1. Add the tool fetch_page to refine and to the alternatives check

Reads: `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/web_search.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`. Changes: `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_investigation.md`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_page_fetch.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_page_fetch.py`, write the cases of the tool: a fetch of a URL that a search returned, the frame of a page that says to ignore the instructions, the cut, a URL that nothing named, a URL that the item text names, the URLs that a text names, a URL that is not https, a private host, the fetch after the last one, a fetch error, a missing token, a page with no text and the counter
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py`
- [x] 1.2 In `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine.py` and `tests/roadmap/test_roadmap_alternatives.py`, write the cases of the gate and of the tool lists: the tool is in the list for a public repository with `crawl4ai.url`, and not for a private repository, an empty setting or the stage planner
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py tests/roadmap/refine/test_roadmap_refine.py tests/roadmap/test_roadmap_alternatives.py`
- [x] 1.3 In `src/devops_cli/roadmap/page_fetch.py`, add `PageFetch` and `named_urls`, and the counter `ROADMAP_PAGE_FETCHES_TOTAL`, the constants and the messages. Give `InvestigationTools`, `AlternativesTools` and `WebSearch` the tool and the gate, and name the tool in the two task prompts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py tests/roadmap/refine tests/roadmap/stage tests/roadmap/test_roadmap_alternatives.py`

## 2. Update the documents

Reads: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md`.

- [x] 2.1 Describe the tool, its guards, its limit and its counter in the three documents, and regenerate the telemetry document
  - Verification: `uv run devops docs generate --sync-readme && git diff --exit-code docs README.md`

## Criteria

- Group 1: The tool `fetch_page` SHALL be in the tool list of refine's investigation and of the alternatives check for a public repository with a set `crawl4ai.url`, and in no other case.
- Group 1: A URL that no search result of the run returned and that the item text does not name SHALL be refused with a message, and no request SHALL be sent.
- Group 1: The fetch after the last one of a run SHALL be refused.
- Group 1: The text of a page SHALL reach the model inside a frame that says it is data and names the source URL and the fetch date.
- Group 1: A failed fetch SHALL be a tool answer and SHALL use one fetch.
- Group 1: `StageTools` SHALL NOT have the tool.
- Group 2: The generated telemetry document SHALL list `devops_cli_roadmap_page_fetches_total`.

## Workflow follow-up

- Pending a person: set `crawl4ai.url` in the live ConfigMap to turn the tool on. It is new egress, and the cluster is not changed by this change.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
