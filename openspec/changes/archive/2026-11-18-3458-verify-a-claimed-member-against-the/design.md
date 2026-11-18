# Design

## Decisions

- **Judge a member claim in `class_claim_problems` beside the class claim.**: That rule already takes the class source at the staged commit and judges a decision, a rejected alternative and a feasibility line, so one reader serves the class and its members.
- **Give the members of a class body with a new `parse_class_members` over the standard library `ast`.**: A member is a field, a method or a nested class, and a text search for the member name matches a comment, a string or a local variable.
- **Judge the module-quote rule in the `citation` gate, over the decision, the rejected alternative and the feasibility lines.**: That gate is the one that holds a reader of a file at the staged commit, and it already scans the same evidence fields.
- **Judge no module whose text the reader does not give.**: The gate judges a text it can read, and a module that the commit does not hold gives none.
- **State the same rule in the verification prompt.**: The model review reads a plan that the machine check accepted, so the prompt names such a line as a `false_premise` finding.
- **Measure the verification prompt change with `uv run devops roadmap eval verify --model <baseline-model> --source .` before and after the change.**: The rule at `docs/ROADMAP_WORKFLOW.md:443` states the score of the model before and after a change to the verification prompt, and the golden set scores the first review of a plan, so the live run of the reviewer is the measure that moves.

## Rejected alternatives

- **Reuse `parse_class_fields` and refuse a member that the returned field map lacks.**: `src/devops_cli/roadmap/stage/stage_models.py:100:def _class_field_lines(node: ast.ClassDef) -> dict[str, int]:` takes annotated and assigned names only, so a claim about a method would be refused and `tests/roadmap/stage/test_roadmap_stage_class_claim.py:70:def test_a_decision_that_quotes_the_class_passes() -> None:` would fail.
- **Walk the module with a second `ast` reader of the whole module.**: `src/devops_cli/roadmap/stage/stage_models.py:185:def class_sources(source: Path, sha: str, names: Sequence[str] | set[str]) -> dict[str, str]:` already gives the source of each class that a claim names, so a second reader repeats that read of the staged commit.
- **Compare the quote with the working tree instead of the staged commit.**: `src/devops_cli/roadmap/stage/stage_change.py:1627:def _plan_citation_problems(` takes a reader of the staged file, and the plan is judged at that commit.
- **Trust the quoted statement alone and skip the class-body read.**: A quote of another class of the module would pass, and the member of the claim would stay unchecked.
- **Put the member rule in `model_problems`, which judges a `Class.attribute` of a known model.**: That rule reads a fixed field map of a model class and scans task text, and it reads no arbitrary class of `src/` at the staged commit.
- **Measure the verification prompt change with the stage replay `uv run devops roadmap eval stage --replay`.**: The replay reads the recorded plans through the gates and calls no model, so it cannot move the score of the reviewer that the verification prompt changes; `docs/ROADMAP_WORKFLOW.md:443:A pull request that changes the verification prompt` names the score of the model instead.
