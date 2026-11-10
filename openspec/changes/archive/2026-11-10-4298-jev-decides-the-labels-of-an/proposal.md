# Proposal: #4298

## Why
`devops roadmap intake` asks one LLM call of the `triage` task for each candidate. The call fills the type (when the title gives none), the priority, the Value, the Effort and the duplicate flag. All five are fixed lists or yes/no questions. TypeSafe Jev (`typesafe/jev-1.14`) is a System One decision model for exactly such questions: it answers with a calibrated probability and a confidence, and it costs about 0.042 USD for 1M input tokens. The owner asked on 2026-11-09 to use Jev for issue labeling and categorization. Closes #4298.

## What Changes
- A setting `roadmap.intake.jev`, off by default. When it is on, `build_intake_model()` returns `JevIntakeModel`, which asks Jev for the proposal in one request and returns the same `ModelProposal` that the `triage` model returns. The checks of intake decide which values stand, as before.
- A request carries a choice for the type (only for a candidate whose title gives none), a choice for the priority, a score of three levels for the Value and one for the Effort, and a yes/no question for each nearest item. A nearest item whose probability reaches 0.90 is the possible original. Intake only flags it: the candidate is still placed.
- A Jev error, a timeout or a confidence below 0.60 leaves the whole proposal to the `triage` model (fail open).
- A counter `devops_cli_roadmap_intake_jev_fields_total` with the labels `field` and `outcome` adds 10 series: 5 fields and 2 outcomes.
- `ProposalRequest` gains `needs_type` and `type_notes`. The JSON that the `triage` model reads is unchanged.
- A command `devops roadmap eval jev` runs the duplicate cases and a new set of 25 closed issues with their labels through both models and prints the false duplicates first. It stops before the first call when it needs more calls than `--max-calls`.
- The Jev edge fake `tests/support/fakes/jev.py`, a transport under the real `SystemOneModel`.
- This change adds a command, an option, a message, a setting and a metric that a consumer observes, so it carries a spec delta.

## Capabilities
- `roadmap-intake-jev` (new): Jev decides the proposal fields of intake, with a fallback, and an evaluation that compares it with the `triage` model.

## Impact
- With the setting off, nothing changes.
- The setting stays off until `devops roadmap eval jev` shows that Jev flags no more false duplicates than the `triage` model, and a person reads the agreement of the label fields.
- Jev gets the title, the body and the nearest items of a candidate. These texts already go to the hosted `triage` model (SECURITY.md item 13).
- Jev gives no evidence, so with Jev a candidate can not get the P0 priority from a model proposal. P0 stays with a person and with verified evidence.

## Feasibility
- Cookbooks (https://docs.typesafe.ai/cookbooks): "Classification" uses choice questions, matching and routing use score questions, and field checks use yes/no questions. The page states no limit on options or questions; its examples run 75 options in one choice and 13 questions in one call.
- Library source, `pydantic_ai/models/decision.py` and `system_one.py` of the venv: `ChoiceQuestion(criteria: dict)`, `ScoreQuestion(criteria: list)` and `NoulQuestion` exist, `SystemOneModel` requires `instructions`, posts to `/v1/systemone`, and checks that every answer matches its question. The answers carry `confidence` (choice, score) and `noul` (yes/no).
- The fake is a transport under the real `SystemOneModel`, so the library validates each fake answer.
- Live: `devops roadmap eval jev` sent 41 requests to Jev through the gateway after #4289 merged. A probe of three requests showed that the confidence of a score answer is often below 0.60 on the long text of real issues, so the least confidence is a parameter of the model (`--min-confidence` in the evaluation).

## Existing Tool Considered
`pydantic_ai`'s `DecisionModel` and `SystemOneModel` (already in the project, `devops_cli.ai.jev.create_jev_model`) send the request and validate the answers; no parser or client is written. `pydantic-evals`, already used by `devops roadmap eval intake`, scores the duplicate cases. The label cases are counted with plain code: one equality for each field. Deleted internal code: none; the `declared` property of the intake run becomes a view of `descriptions`.
This change fits one pull request.
