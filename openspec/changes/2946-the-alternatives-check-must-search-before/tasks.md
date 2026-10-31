# Tasks

## 1. Add skip-class constant and classification

Reads: none. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/test_roadmap_alternatives.py`.

- [ ] 1.1 Write a table test that covers each skip class: test, docs, refactor, chore, ci, perf, and fix-with-stack-trace. For each, assert the verdict is not-applicable, the comment names the class as the reason, and no model call is made, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` fails on the base
- [ ] 1.2 Add a SKIP_CLASSES constant list in the alternatives module. Add a classify_skip_class function that takes an item and returns the class name or None. In the check entry point, call classify_skip_class before any model call. When it returns a class, write the not-applicable verdict with the class as reason and return without calling the model, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Enforce search-before-verdict for non-skip items

Reads: none. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/test_roadmap_alternatives.py`.

- [ ] 2.1 Write a test with a scripted model that answers a feat item with a verdict and no search. Assert the check rejects the reply. Assert the model gets one more turn. Assert a second answer without a search ends as a failed check for that item, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` fails on the base
- [ ] 2.2 In the model reply handler, check whether a search was recorded for the item. If no search was recorded and this is the first reply, reject the reply and give the model one additional turn. If no search was recorded and this is the second reply, end the check as failed for that item, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Verify Firecrawl counter rises in replay

Reads: none. Changes: `tests/test_roadmap_alternatives.py`.

- [ ] 3.1 Write a replay test that runs the check on a feat item. Assert that devops_cli_firecrawl_searches_total increases by at least 1 after the model performs a search, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` fails on the base
- [ ] 3.2 Ensure the search path in the alternatives check increments the Firecrawl counter defined in docs/TELEMETRY.md. Verify the test asserts the counter delta is at least 1, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
