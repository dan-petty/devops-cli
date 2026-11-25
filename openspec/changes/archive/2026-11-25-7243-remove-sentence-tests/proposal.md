# Proposal: #7243

## Why

Issue #7243: many tests read a real document, instruction file, prompt, template or skill of the repository and assert that it holds a specific sentence, heading, phrase or count. Such a test fails on each edit of that text, although no code changed. PR #7218 changed one sentence of `AGENTS.md` and of its template, and two tests had to change with it. The owner direction of 2026-11-25, after #7229, is to remove these sentence tests as well.

## What Changes

- Remove 195 test functions. Four test files go whole: `tests/invariants/test_configmap_rollout_rule.py`, `tests/invariants/test_roadmap_stage_measure_doc.py`, `tests/k8s/test_k8s_retain_migration_docs.py` and `tests/openspec/test_qdrant_retry_spec.py`. The largest groups are in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` (57), `tests/roadmap/implement/test_roadmap_implement_prompt.py` (21), `tests/invariants/test_agents_md.py` (18) and `tests/invariants/test_roadmap_workflow_doc.py` (13).
- Change 7 tests that check code and held one sentence of a prompt or a document. `tests/invariants/test_skills.py` becomes one generic rule: each project skill holds the same text in each root.
- Remove the helpers that only these tests used, one snapshot file and the duration records of the deleted files.
- Correct `docs/TESTING.md` and `docs/ROADMAP_WORKFLOW.md`, which named removed tests.
- Five requirements of living specs had a removed test as the proof of a scenario. Each gets a command as its proof, so the change carries deltas for `agent-instructions`, `k8s-bootstrap` and `roadmap-refine/waits`. It fits in one pull request.

## Capabilities

### Modified Capabilities
- `agent-instructions`: the scenarios of the safety rules and of the draft rule read the files with `git grep`.
- `k8s-bootstrap`: the two scenarios of `docs/DEVCONTAINER_USAGE.md` read the file with `git grep`.
- `roadmap-refine/waits`: the scenario of the refine guide reads the file with `git grep`.

## Impact

- An edit of an instruction file, a document, a prompt or a skill needs no edit of a test.
- A wrong edit of a prompt sentence is no longer found by a unit test. The contract tests that compare a prompt with the source code stay, and the recorded evaluation cases of the roadmap jobs stay.
- No source code changes.

## Feasibility

Confirmed in the worktree of the change:
- `uv run devops ci test tests` passes after the removal.
- `uv run devops ci --check --only lint,format,typecheck,test-tree,docs,openspec` passes.
- Each `git grep` command of the new scenarios gives the result that its scenario states on the current tree.
- `tests/gate/tree_checks/config_reads.toml` keeps its sum of 127: no removed test was in its counts.

## Existing Tool Considered

`devops docs check` resolves the commands and the links that documents name, Vale checks the style, and `devops roadmap eval` replays recorded cases of the jobs. No code is built.
