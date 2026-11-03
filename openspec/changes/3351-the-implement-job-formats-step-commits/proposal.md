# Proposal

## Why

The implement job created an intermediate commit titled `Correct the Valkey paragraph in SECURITY.md (#2670)` for a `docs` item, with no Conventional Commit prefix, while CONTRIBUTING.md requires that format on every commit of a topic branch (#3351). The history disagreed with the pull request title and the archive commit, and no check caught it.

## What Changes

- A helper in `src/devops_cli/roadmap/` builds a step commit title from the item title, the step title and the issue number.
- The helper reads the type and scope with the `commit_type` and `commit_scope` functions that `src/devops_cli/roadmap/commit_title.py` already holds, and falls back to `chore` when the item title has no valid type.
- The helper adds the issue reference `(#N)` exactly once, also when the step title already ends with it.
- The step that commits a task group builds its commit title with the helper.
- The archive commit keeps the title `docs(openspec): archive the change (#N)`.
- An offline unit test pins the exact title for a docs item, a step title that already holds the reference, and an item title with no prefix.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: A step commit title carries the type and scope of the item, A step commit title holds the issue reference once, The archive commit keeps its docs type

## Impact

- Code: `src/devops_cli/roadmap/step_commit.py`, `src/devops_cli/roadmap/implement_step.py`
- Tests: `tests/roadmap/test_step_commit_title.py`, `tests/roadmap/test_roadmap_implement_step_commit.py`

## Feasibility

- `probes` reports `The path `CONTRIBUTING.md` is a file of the staging commit.`, and CONTRIBUTING.md section 4 says `Commits on a topic branch also follow the Conventional Commits format.` That is the rule the issue says the job breaks.
- `probes` reports `The path `CONTEXT.md` is a file of the staging commit.`, and CONTEXT.md defines Implementing as `one step for each task group that has an unticked task, the documentation, the archive, the push, the body that closes the issue` - the step commit and the archive commit are the two titles the issue names.
- `probes` reports `The path `docs/TESTING.md` is a file of the staging commit.`, and docs/TESTING.md asks a pure function over open-ended input to be tested with examples, which is the offline unit test the issue requires.
- `probes` reports the identifier `chore` at `tests/roadmap/test_roadmap_implement_planned.py:97` and `tests/roadmap/test_roadmap_stage_selection.py:91`, and the identifier `docs` only under `src/devops_cli/ai/`. So no helper that formats a step commit title exists yet, and the work is to create one.
- First checks against the real system: `uv run devops ci test tests/roadmap/` runs the roadmap tests that hold the implement job, and `uv run devops ci` runs the full gate with lint, types and coverage.

## Existing Tool Considered

commitizen validates and formats Conventional Commit messages, and its `cz commit` builds a title from a type, a scope and a subject. It does not derive a step title from the title of a roadmap item, and the repository already holds the parser that the `Semantic PR title` check, `devops pr create` and the roadmap jobs use. So the change reuses `commit_type` and `commit_scope` and adds one small helper. Building and keeping that helper costs about 1,500 tokens to build, 500 tokens to review and 30 minutes of elapsed time, against a new dependency, its configuration and its release cadence for a pure string rule.
