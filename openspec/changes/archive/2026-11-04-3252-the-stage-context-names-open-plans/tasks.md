# Tasks

## 1. List the other files that hold a cited metric name

Reads: `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/roadmap/stage_overlap.py` (new), `tests/roadmap/test_roadmap_stage_overlap.py` (new).

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_overlap.py`, a test gives `metric_senders` a fake grep answer that holds `devops_cli_github_requests_total` in two files and asserts that both files are listed under the name, and a second test asserts that a name that `INSTRUMENTS` does not hold lists nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_overlap.py` fails on the base
- [x] 1.2 Write `src/devops_cli/roadmap/stage_overlap.py` with `metric_senders(names, grep)` that keeps the names that `INSTRUMENTS` holds, runs `git grep -w` at the staged commit through a `grep` callable that the tests replace, and returns the files of each name in sorted order. It returns an empty mapping when no name survives
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_overlap.py` passes

## 2. List the open pull requests that overlap the paths of a reply

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_github.py`, `src/devops_cli/github/session.py`. Changes: `src/devops_cli/roadmap/stage_overlap.py`, `tests/roadmap/test_roadmap_stage_overlap.py`.

- [x] 2.1 A test gives `overlaps` a fake list that holds pull request 3173 on `docs/TELEMETRY.md` and an issue body that cites that path, and asserts one entry with the number, title, state and shared path. A second test asserts that a plan pull request carries the plan mark. A third test gives 150 fake pull requests and asserts that the fake client records two GraphQL requests and no other request
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_overlap.py` fails on the base
- [x] 2.2 Add `OpenPull` and `Overlap` dataclasses and `open_pulls(client)` to `src/devops_cli/roadmap/stage_overlap.py`. It reads `number`, `title`, `state` and `files` of the open pull requests in one GraphQL request for each 100 through the session client, marks a title whose type is `docs(openspec)` as a plan, and returns the entries. Add `overlaps(pulls, paths)` that compares paths with the files of each pull and returns one entry for each pull with its sorted shared paths. The client is a parameter, so the tests give a fake
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_overlap.py` passes

## 3. Put the overlaps and the senders into the stage context

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_overlap.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 3.1 A test builds the request of one item with a fake client and a fake tree and asserts that the request holds an `overlaps` list with the number of the overlapping pull request and a `metric_senders` mapping for the cited name
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 3.2 In `_Planner._request` of `src/devops_cli/roadmap/stage.py`, read the open pull requests once for the item with `open_pulls`, add the `overlaps` entry for each pull whose files meet the paths that the item body cites, and add `metric_senders` for the names that `INSTRUMENTS` holds. A read that fails adds no key and never stops the item. Pass the overlap list to `_settle` so that `check_proposal` sees it: give `check_proposal` its `overlaps` argument in this group, so the request and the gate meet before group 4 adds the rule
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. Refuse an empty Dependencies field on an overlap

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_stage_form.py`, a test gives `check_proposal` a reply whose `dependencies` field is empty and an overlap list that names pull request 3173 on `docs/TELEMETRY.md`, and asserts that one problem names both. A second test gives a reply that names the overlap and asserts that no problem mentions it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [x] 4.2 Add a `dependencies` field to `StageProposal` in `src/devops_cli/roadmap/stage_change.py`, render it as the `## Dependencies` section of the proposal, update `test_roadmap_stage_plan.py` snapshot assertions, and give `check_proposal` an `overlaps` argument. When the overlaps are non-empty and `dependencies` is empty, add one problem that names the pull request number and the shared path. When `dependencies` names an overlap, add no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 5. State the Dependencies rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_stage_prompt_rules.py`, a test reads the stage prompt and asserts that it names the `dependencies` field, the empty list and the overlap entry
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 5.2 Add the `dependencies` key under reply keys and the Dependencies rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: write each overlap and each shared metric sender into the `dependencies` field, and leave it empty only when the context lists no overlap
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes
- [x] 5.3 Update `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 6. Report the request count of the overlap read

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`.

- [x] 6.1 In `tests/roadmap/test_roadmap_stage_apply.py`, a test stages an item whose body cites a path and asserts that the comment of the staged item states the number of GraphQL requests
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [x] 6.2 In `src/devops_cli/roadmap/stage.py`, carry the request count of `open_pulls` into `StagedChange` and add the note of `stage_comment_overlaps` to the comment. Update `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/stage.md` to state that the job reads the open pull requests in one GraphQL request for each 100, that the comment reports the count, and that the gate refuses an empty `dependencies` field when the context lists an overlap
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` and `uv run devops ci docs` pass

## Criteria

- Group 2: A test with a fake list of pull requests shows that an overlapping path appears in the context with the number.
- Group 1: A test shows that a cited metric name lists its other senders.
- Group 4: `check_proposal` refuses "Dependencies: None" when the context lists an overlap, and names it.
- Group 6: The extra GitHub reads fit the request budget (ADR 0016), and the number of requests is stated.

## Workflow follow-up

- State the replay evaluation score of the same model before and after the prompt and gate changes per `docs/ROADMAP_WORKFLOW.md:233`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
