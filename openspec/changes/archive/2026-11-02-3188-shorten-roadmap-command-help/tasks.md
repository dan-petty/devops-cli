# Tasks

Every command runs from the root of the clone.

## 1. The help of the six commands is a short summary

Kind: behavior. Reads: `src/devops_cli/lang/en/help.py` (class `RoadmapCommandHelp`), `src/devops_cli/commands/roadmap.py`. Changes: `tests/roadmap/test_roadmap_command_help.py`, `src/devops_cli/lang/en/help.py`.

- [x] 1.1 Write the failing test `tests/roadmap/test_roadmap_command_help.py`: for each of `intake`, `refine`, `alternatives`, `stage`, `implement` and `inbox`, the help has at most three sentences, and it names `docs/roadmap/<command>.md`, which is a file. Verify that it fails on the base with `git stash push -- src/devops_cli/lang/en/help.py && uv run devops ci test tests/roadmap/test_roadmap_command_help.py; git stash pop` (12 failures)
- [x] 1.2 Cut the six strings of `RoadmapCommandHelp` to two sentences and one sentence that names the page. Keep the strings of the options. Verify with `uv run devops ci test tests/roadmap/test_roadmap_command_help.py` (it passes)

## 2. The pages of the jobs

Kind: documents. Reads: the removed help strings (`git show origin/main:src/devops_cli/lang/en/help.py`), `openspec/specs/roadmap-*/spec.md`. Changes: `docs/roadmap/intake.md`, `refine.md`, `alternatives.md`, `stage.md`, `implement.md`, `inbox.md`.

- [x] 2.1 Write the six pages, with the facts of the removed help text in the order of the work of the job and a table that names the specs. Verify with `ls docs/roadmap/*.md | wc -l` (it prints 6)
- [x] 2.2 Add the glob `docs/roadmap/*.md` to the hand-written class of `CONST_DOCS_INVENTORY` in `src/devops_cli/config/constants.py`. Verify with `uv run devops ci test tests/docs/test_docs_inventory.py`
- [x] 2.3 Link the pages from `docs/index.md`, and replace the two bullets of `docs/ROADMAP_WORKFLOW.md` that repeat the help of `inbox` and `refine` with a pointer. Verify with `uv run devops docs check`

## 3. The inbox request count moves from the help to the plan and the spec

Kind: behavior. Reads: `src/devops_cli/roadmap/request_plan.py` (`inbox_requests`), `openspec/specs/roadmap-inbox/spec.md`. Changes: `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_inbox_command.py`.

- [x] 3.1 Add the test of the plan of the reads to `tests/roadmap/test_roadmap_inbox_requests.py`: three listings that repeat for each page, one read of the labels file, and one commit read that only differing labels make. Verify with `uv run devops ci test tests/roadmap/test_roadmap_inbox_requests.py`
- [x] 3.2 Delete `test_the_help_states_how_many_requests_a_run_sends` from `tests/roadmap/test_roadmap_inbox_command.py`, because it asserted a sentence of the long help. Verify with `! git grep -n 'how_many_requests' tests/` (it exits 0)

## 4. The generated documents

Kind: documents. Reads: `devops docs generate`. Changes: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/MCP_TOOLS.md`.

- [x] 4.1 Regenerate the documents with `uv run devops docs generate --sync-readme`. Verify with `uv run devops ci docs` (it passes) and `git diff origin/main --stat -- README.md docs/CLI_REFERENCE.md docs/commands docs/MCP_TOOLS.md` (it names the four files and no other generated file)
- [x] 4.2 Run the tests that read the help or the generated files: `uv run devops ci test tests/ai tests/commands tests/docs tests/lang tests/roadmap tests/invariants`. Verify that the only failures are the `kubectl` ones of `tests/invariants/test_k8s_*.py`, which need a cluster tool that this sandbox lacks
