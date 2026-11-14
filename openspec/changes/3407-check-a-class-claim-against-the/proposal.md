# Proposal

## Why

A stage plan can build on a false claim about an internal class and pass every check. The plan of #3350 said in its design that `StagedTree` holds the file text of the staged commit, and the class keeps the tracked paths only, so an implementation step would have failed on text that does not exist. `check_proposal` tests the paths, the spec delta, the criteria, the form and the content of a plan, and no rule compares a claim about a class with the staged source (#3407).

## What Changes

- The `paths` gate of `check_proposal` refuses a decision, a rejected alternative or a feasibility line that names an internal class under `src/` in a code span and gives no other code span that holds text of that class at the staged commit.
- `class_sources` in `src/devops_cli/roadmap/stage/stage_models.py` greps `^class <name>` at the staged commit, reads each module with `git show` and `ast`, and returns the source of the class, so a class that declares no base is read.
- The stage job computes the class sources from the names that the plan claims and passes them to `check_gates` as an optional mapping, and the replay reads them from the facts of its case.
- The problem is the `RoadmapMessages` entry `stage_problem_class_claim` in `src/devops_cli/lang/en/messages.py`, and it names the class and the plan section.
- A golden case records a plan whose decision claims that `StagedTree` holds file text, with two null commits and a note that the case reads no commit, and one `false_premise` defect at the `paths` gate.
- `docs/roadmap/plan-recheck.md` and `docs/ROADMAP_WORKFLOW.md` state the class-claim rule of the `paths` gate.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/claims`: A class claim quotes the class source at the staged commit, The class claim reads the class at the staged commit, The class-claim problem names the class and the plan section, The replay judges a false class claim

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- Documents: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_class_claim.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/case.json`, `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/facts.json`, `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/issue.txt`, `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/plan.json`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`

## Feasibility

- The issue cites paths that commit bff2f14f moved. The probe says: The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The test path of the issue moved as well. The probe says: The path `tests/roadmap/test_roadmap_stage_plan.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_plan.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The premise holds at the moved path. `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed `src/devops_cli/roadmap/stage/stage_paths.py:117:class StagedTree:` and `src/devops_cli/roadmap/stage/stage_paths.py:143:listing = git(source, "ls-files", "-z", operation=operation)`, so the tree reader keeps the tracked paths and reads no file text. The claim of #3350 is false at the staged commit.
- The probe shows that the class has no field `read`: `StagedTree` defines no field `read` in `src/devops_cli/roadmap/stage/stage_paths.py`. The class source that the rule reads holds `listing = git(source, "ls-files", "-z", operation=operation)`, and `read` is a classmethod at `src/devops_cli/roadmap/stage/stage_paths.py:140:def read(cls, source: Path, *, operation: str) -> Self:`.
- The finding of this review is a real defect, and group 3 corrects it. The `roadmap-stage-eval-commits` row refuses a null commit with no note: `tests/gate/roadmap_stage_eval_commits.py:31:_READS_NO_COMMIT: Final[str] = "reads no commit"` and `tests/gate/roadmap_stage_eval_commits.py:48:if not any(_READS_NO_COMMIT in note for note in case.notes):`. The staged case that the new one copies carries the note: `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/case.json:20:The change was never merged as this plan, so pull, merge_commit and base_commit hold the issue number and two placeholders: the case reads no commit, and the facts hold the files of its tree.` Group 3 now writes that note in `case.json` and asserts it in `test_the_case_of_a_false_class_claim_is_recorded`.
- The blocker of an earlier review is corrected. The old helper greps a definition line with a base: `src/devops_cli/roadmap/stage/stage_models.py:131:args = ["grep", "-n", f"^class {name}(", sha, "--", "src/"]`, and `src/devops_cli/roadmap/stage/stage_paths.py:117:class StagedTree:` declares no base, so that helper would return no source for it. The new reader greps `^class <name>` with no `(`, confirms the definition with `ast`, and group 1's test `test_class_sources_reads_a_class_with_no_base` calls it on the class of the issue and asserts that the source holds `ls-files`.
- A further finding of an earlier review is corrected. Group 3 changes the case files and the counts, and group 4 raises the judged baseline in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, the module whose fixture replays the whole set, so that module is the `verify` of group 4 and the replay of the new case runs under its own group.
- An earlier review's finding is corrected. Group 4 names the test function that it updates: `test_the_counts_of_each_type_are_the_baseline_that_a_change_of_a_gate_beats` asserts `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:281:assert report.judged() == JUDGED_BASELINE`, so that function carries the raised baseline.
- An earlier review's finding is corrected. Group 1 changes `src/devops_cli/roadmap/stage/stage_change.py` and now lists the existing test module of the stage job's writes, `tests/roadmap/stage/test_roadmap_stage_apply.py`, in `reads` and names it in a code span of the implementation, so the implement job may run that test.
- The rule joins the `paths` gate: `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` 2407 2640 showed `src/devops_cli/roadmap/stage/stage_change.py:2534:*model_problems(proposal, models),`, so that gate already judges a claim about the staged source.
- The comparison folds whitespace with the helper that the citation rule uses: `src/devops_cli/roadmap/stage/stage_change.py:def _squash`.
- The job reads the staged text with the reader it already passes: `src/devops_cli/roadmap/stage/stage.py:2245:read_text=partial(_read_staged_file, self._source, self._sha),`.
- The job computes the model record and gives it to the gate: `src/devops_cli/roadmap/stage/stage.py:2134:models = model_fields(self._source, self._sha, referenced)`. The new line computes the class sources from the names that `claimed_classes` returns, beside that line.
- The replay reaches the rule through the paths gate: `src/devops_cli/roadmap/stage/stage_eval_gates.py:222:models=plan.models,` passes the record to `check_proposal`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:430:found = problems.get(defect.gate, [])` shows that a recorded defect is judged by the gate it names.
- The facts of a case hold such a record: `src/devops_cli/roadmap/stage/stage_eval_cases.py:179:models: Mapping[str, tuple[str, tuple[str, ...]]] = Field(default_factory=dict)`, so a `classes` mapping joins it.
- The case may record the type `false_premise` with the gate `paths` and a message: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:306:by_finding = defect.gate in {g.name for g in GATES} and defect.message`, so the defect of the new case needs no new type and no row of a score moves.
- The constants are staged as the plan reads them: `src/devops_cli/roadmap/stage/stage_change.py:208:_CITATION_MIN_CHARS: Final[int] = 3`, the bound of a quote, and `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:56:JUDGED_BASELINE: Final[tuple[int, int]] = (82, 319)`, which the new case raises by one caught defect and one defect.
- The golden set holds 59 cases and 53 reviewed pulls: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:71:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 59, 6)` and `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:72:assert len(EVALUATED_PULLS) == 53`, so the new case raises both by one.
- The two halves of the split are even: `read_file` of `tests/fixtures/roadmap_eval/stage/split.json` showed 29 names in half A and 30 in half B, and `tests/fixtures/roadmap_eval/stage/split.json:38:"good-3410-the-stage-gate-proves-a-negative"` is the last name of half A, so the new name joins half A.
- A reader that runs `git` at a commit is tested on the checkout: `tests/roadmap/stage/test_roadmap_stage_models.py:33:result = model_fields(REPO_ROOT, "HEAD", ["StageFilter"])`, so the test of `class_sources` reads the class at `HEAD` and reaches no network.
- Precondition of `class_sources`: a checkout of the repository at the staged commit, because it runs `git grep` and `git show` there. It calls no client of a service and reaches no network.
- Precondition of `check_proposal` and `class_claim_problems`: none. They read the mapping that the caller hands them, so they need no checkout, no client and no network.
- The plan introduces no new command and no new verify program. `uv run devops ci test`, `uv run devops roadmap eval stage --replay` and `uv run devops ci docs` run `devops` from the runner image, which holds `git` and `pytest`; no excluded tool is needed, and a red group carries the failure class `test`.
- The plan adds a rule of the plan check, so group 1 gives `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own reply object and asserts that `content_problems` returns no problem for it.
- First checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py`, then `uv run devops roadmap eval stage --replay`, then `uv run devops ci docs`.

## Existing Tool Considered

No open, maintained tool or library compares a plan claim about an internal class with the source of a commit. The change extends `check_proposal` and reuses the `git show` reader and the standard library `ast`, so it adds no dependency. Cost: about 8,000 output tokens to build and test, about 2,000 tokens for each later fix, and about 1 day elapsed.

## Dependencies

None.
