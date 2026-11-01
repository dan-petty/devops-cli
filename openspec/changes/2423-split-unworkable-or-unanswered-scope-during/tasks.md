# Tasks

## 1. Add scope-splitting instructions to the refine prompt

Reads: none. Changes: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`.

- [ ] 1.1 Write a test that reads the refine prompt file and asserts it contains the words 'split_issues', 'unworkable', and instructions to list each removed part with a title and body, and verify that `uv run pytest tests/test_roadmap_refine_prompt.py -k scope_splitting` fails on the base
- [ ] 1.2 Add a section to the prompt after the existing instructions. The section instructs the model: when the issue contains parts that cannot be implemented as written or have unresolved questions, remove those parts from the core proposal. List each removed part in a split_issues array. Each entry has a title and a body that states the problem and the acceptance criteria for that part. The remaining proposal covers only the workable scope, and verify that `uv run pytest tests/test_roadmap_refine_prompt.py -k scope_splitting` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Process split_issues in the refine orchestrator

Reads: none. Changes: `src/devops_cli/roadmap/refine.py`.

- [ ] 2.1 Write a test that mocks the model response with a split_issues list of two entries. Assert the orchestrator calls the intake function once per entry with the correct title and body. Assert a comment is added to the original issue naming each new issue number, and verify that `uv run pytest tests/test_roadmap_refine_orchestrator.py -k split_issues` fails on the base
- [ ] 2.2 After the model response is parsed, check for the split_issues field. For each entry, call the existing intake function with the entry title and body. Collect the new issue numbers. Add a comment on the original issue that lists each new issue number as a link. The original issue's remaining scope proceeds toward Ready as normal, and verify that `uv run pytest tests/test_roadmap_refine_orchestrator.py -k split_issues` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Add integration test for the full scope-splitting flow

Reads: none. Changes: `tests/test_roadmap_refine_split.py`.

- [ ] 3.1 Write a test that simulates a refine run on an issue with mixed workable and unworkable scope. Assert the original issue proceeds toward Ready. Assert two new issues appear with the correct titles and bodies. Assert links are recorded on the original issue, and verify that `uv run pytest tests/test_roadmap_refine_split.py` fails on the base
- [ ] 3.2 The test doubles the model response and the GitHub API. It sets up an issue with one workable part and two unworkable parts. It runs the refine orchestrator. It asserts the original issue status moves toward Ready, the two new issues exist with correct content, and the original issue has a comment linking to both new issues, and verify that `uv run pytest tests/test_roadmap_refine_split.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
