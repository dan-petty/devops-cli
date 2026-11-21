# Tasks

## 1. Add the repair-text check and its message

Kind: behavior. Reads: `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_findings.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/stage/stage_meta_text.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_meta_text.py` (new).
Adds: `META_PHRASES`, `_prose_lines`, `meta_text_problems`

- [x] 1.1 Write `test_a_repair_phrase_in_a_feasibility_line_is_refused` in `tests/roadmap/stage/test_roadmap_stage_meta_text.py` first: `meta_text_problems` returns one problem with the line number and the phrase for a line that holds `The earlier reply was wrong`, and returns no problem for the same words inside a fenced code block or a block quotation
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_meta_text.py` fails on the base
- [x] 1.2 Add `src/devops_cli/roadmap/stage/stage_meta_text.py` with `META_PHRASES`, `_prose_lines` and `meta_text_problems`. `META_PHRASES` holds the bounded phrases `earlier reply`, `previous reply`, `prior reply`, `this reply`, `the reply above`, `earlier answer`, `previous turn`, `I was wrong`, `I was mistaken`, `I apologize`, `let me correct` and `my earlier`. `meta_text_problems` reads the lines in order, skips each line inside a fenced code block (a line that starts with three backticks or three tildes toggles the fence) and each block quotation (a line whose first non-space character is `>`), ignores the text inside an inline code span, and gives one problem for each other line that holds a phrase outside a code span, with the number of the line from 1 and the phrase. Add the message `stage_problem_meta_text` to `src/devops_cli/lang/en/messages.py`; it names the line number and the phrase and asks for the system fact alone
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_meta_text.py` passes

## 2. Register the gate and document it

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_meta_text.py`, `tests/roadmap/stage/test_roadmap_stage_meta_text.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-recheck.md`, `tests/roadmap/stage/test_roadmap_stage_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-recheck.md`.
Adds: `META_TEXT`

- [x] 2.1 Write `test_the_meta_text_rule_accepts_the_plan_of_this_change` in `tests/roadmap/stage/test_roadmap_stage_gates.py` first: it builds the plan's own `StageProposal` with a Feasibility line that quotes `The earlier reply was wrong` and asserts that `content_problems` returns no problem for it, and it asserts that `check_gates` gives one `meta-text` problem for a reply whose Feasibility holds that line; it fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` fails on the base
- [x] 2.2 Add the member `META_TEXT` to the gate enum of `src/devops_cli/roadmap/stage/stage_change.py`, the line `ProposalGate.META_TEXT: meta_text_problems(proposal.feasibility),` to `check_gates` after its content line, the import of `meta_text_problems` from `src/devops_cli/roadmap/stage/stage_meta_text.py`, and that module to `STAGE_EVAL_GATE_PATHS`. Add the gate to the list of stage checks in `docs/ROADMAP_WORKFLOW.md` and to the gates of `docs/roadmap/plan-recheck.md`. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` passes
- [x] 2.3 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-recheck.md` with the new gate and the phrases that it refuses
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
