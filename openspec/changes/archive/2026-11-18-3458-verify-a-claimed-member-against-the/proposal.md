# Proposal

## Why

Issue #3458: the plan of #3417 said that a parsed group carries its kind, and `TaskGroup` in `src/devops_cli/roadmap/step_files.py` holds `number`, `title`, `tasks`, `text` and `line` and no `kind`, so the stage plan check accepted a claim about a member of a type and the plan passed.

## What Changes

- `src/devops_cli/roadmap/stage/stage_change.py` refuses a `Class.member` claim whose member the class body at the staged commit does not define.
- `src/devops_cli/roadmap/stage/stage_models.py` gains `parse_class_members`, which gives the fields, the methods and the nested classes of a class body.
- `src/devops_cli/roadmap/stage/stage_change.py` refuses a claim line that names a module under `src/` and holds no statement of that module, in the citation gate.
- `src/devops_cli/lang/en/messages.py` gains the member-claim message and the module-quote message.
- `src/devops_cli/ai/tasks/roadmap_stage_verify.md` names a line that quotes no statement of its module as a `false_premise` finding.
- Group 3 runs `uv run devops roadmap eval verify --model <baseline-model> --source .` on the base commit and on the change and states the score before and after, because a change to the verification prompt moves that score.
- `tests/roadmap/stage/test_roadmap_stage_class_claim.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` pin the rules.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/claims`: A member claim names a member that the class body defines, The member-claim problem names the class, the member and the plan section
- `roadmap-stage/trace-gate`: A line that names a module quotes a statement of that module
- `roadmap-stage/verification`: The verification prompt names a line that quotes no statement of its module

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_class_claim.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probe line "The path `src/devops_cli/roadmap/step_files.py` is a file of the staging commit." confirms the module of the issue, and `read_file` of `src/devops_cli/roadmap/step_files.py` returned `class TaskGroup:`, whose body holds `number`, `title`, `tasks`, `text` and `line` and no `kind` member, so the claim of #3417 that a parsed group carries its kind is false; `src/devops_cli/roadmap/step_files.py:59:class TaskGroup:` cites the definition.
- The probe line "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." shows that the issue cites a path that the commit does not hold, and the candidate `src/devops_cli/roadmap/stage/stage_change.py` holds `def class_claim_problems(`, so the plan uses the paths that the commit holds.
- The class-claim rule is in the code: `src/devops_cli/roadmap/stage/stage_change.py:2556:def class_claim_problems(` takes the class sources at the staged commit, and `tests/roadmap/stage/test_roadmap_stage_class_claim.py` holds its cases, so the member rule extends a rule that the code holds and waits on no other item.
- The field reader takes annotated and assigned names only: `src/devops_cli/roadmap/stage/stage_models.py:100:def _class_field_lines(node: ast.ClassDef) -> dict[str, int]:` and `src/devops_cli/roadmap/stage/stage_models.py:114:def parse_class_fields(source_code: str) -> dict[str, dict[str, int]]:` would refuse a member claim about a method, so the plan adds `parse_class_members` for the fields, the methods and the nested classes of a class body.
- The citation gate already holds the reader of a staged file: `src/devops_cli/roadmap/stage/stage_change.py:1627:def _plan_citation_problems(` takes a reader of the staged file, and `src/devops_cli/roadmap/stage/stage_change.py:213:_CITATION_MIN_CHARS: Final[int] = 3` is the least length of a quote that the module rule keeps.
- A prompt change lists and verifies the prompt-rule test, which a constant names: `src/devops_cli/roadmap/stage/stage_change.py:226:PROMPT_RULE_TEST: Final[str] = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"`.
- The stage job gives the reader the staged text, and `src/devops_cli/roadmap/stage/stage_models.py:185:def class_sources(source: Path, sha: str, names: Sequence[str] | set[str]) -> dict[str, str]:` runs `git grep` and `git show`, so the precondition of that call is a checkout of the repository at the staged commit; it calls no client of a service and reaches no network.
- The review finding is answered: `docs/ROADMAP_WORKFLOW.md:443:A pull request that changes the verification prompt` states the score of the model before and after the change, so group 3 runs `uv run devops roadmap eval verify --model <baseline-model> --source .` on the base commit and on the change with the same model and states the score of each run.
- The live run `uv run devops roadmap eval verify --model <baseline-model> --source .` needs a client of the model gateway and a network to it, and its failure class is `provider` with the action `retry`; the replay `uv run devops roadmap eval stage --replay` calls no model and needs no network.
- The commands of the plan introduce no program of its own: `uv`, `devops` and `pytest` come from the runner image, and the pod sets `allowPrivilegeEscalation` to false, drops all capabilities and mounts the root filesystem read-only.
- The first checks of the implementation are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py` for the member rule and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` for the module rule, and `uv run devops roadmap eval stage --replay` gives the score before and after the change.
- The issue also cites the verification module of the stage job, which moved in the same commit bff2f14f; the run did not read it (not checked), and the plan changes the prompt file `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and no code of that module.
- The context lists no overlap, no metric sender and no issue dependency, so the plan waits on no other item and `dependencies` is empty.

## Existing Tool Considered

The alternatives check of 2026-11-07 found no open, maintained tool: griffe parses a working tree into the members of a class, and it finds no plan line, compares no quote with a staged module and reports no false-premise finding. The change extends the class-claim rule that the project keeps, so it builds its own code at a cost of about 2,000 tokens to build and test and about 30 minutes elapsed.

## Dependencies

None.
