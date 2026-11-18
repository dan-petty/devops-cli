# Proposal

## Why

The stage job commits the text of an earlier model reply into the Feasibility section of a proposal, as #4111 reports: the section holds a self-correction instead of a system fact. This change adds a deterministic gate that refuses such a line before the job commits the plan, and it names the line and the phrase.

## What Changes

- Add `src/devops_cli/roadmap/stage/stage_meta_text.py` with the bounded list of repair phrases and the check of the Feasibility lines, which skips fenced code blocks and block quotations.
- Add the message `stage_problem_meta_text` to `src/devops_cli/lang/en/messages.py`; it names the line number and the phrase of each refused line.
- Register the gate `meta-text` in `src/devops_cli/roadmap/stage/stage_change.py` and in `STAGE_EVAL_GATE_PATHS`, so the stage job and `devops roadmap plan-recheck` report it.
- Test the rule in `tests/roadmap/stage/test_roadmap_stage_meta_text.py`, and add the plan's own acceptance test to `tests/roadmap/stage/test_roadmap_stage_gates.py`.
- Document the gate and its phrases in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-recheck.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: The plan refuses repair text in the Feasibility lines

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_meta_text.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-recheck.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_meta_text.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`

## Feasibility

- The path `CONTEXT.md` is a file of the staging commit.
- The path `docs/adr/0005-review-findings-come-from-tools-not-models.md` is a file of the staging commit.
- The path `proposal.md` is no file at the root of the staging commit, and that shows nothing about the premise: the stage job writes the proposal into a change folder.
- `file_symbols` of `src/devops_cli/roadmap/stage/stage_change.py` listed `def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]:` and `def check_gates(`, so one function collects the problems of a reply and one place takes the new rule.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` lines 3299 to 3312 showed the proposal writer, whose Feasibility section is written from the `feasibility` list of the reply, with `f"## Feasibility` as the start of that section.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` lines 2913 to 2993 showed `ProposalGate.CONTENT: content_problems(proposal, probes),`, so a new gate is one member of the enum and one line of `check_gates`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_gates.py` lines 1 to 80 showed the plan's own acceptance test, which builds a plan and asserts that the problems of the reply are no problem, and it imports the gate enum from that module.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 4980 to 5120 showed `stage_problem_no_quote: str = (`, so a new problem text follows the same form in that catalog.
- The defect is the line that the issue quotes, `The earlier reply was wrong`, which names an earlier reply where the section must hold a system fact.
- The issue can be built as written: the gate has a place in `check_gates`, and the writer of the proposal file gives the Feasibility section from the reply.
- No function that the plan calls needs a checkout, a client of a service or a network: `meta_text_problems` reads the lines of the reply, and `content_problems` and `check_gates` read the reply and the tree that their caller passes.
- The plan introduces no command of the stage job and no verify program: `uv run devops ci test` and `uv run devops roadmap eval stage --replay` run `uv`, `pytest` and `devops`, which are in the runner image, and no pod setting changes.
- The checks that the implementation runs first are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_meta_text.py`, which fails on the base, and then `uv run devops roadmap eval stage --replay` with the score before and after the change.

## Existing Tool Considered

Vale (MIT, maintained) lints Markdown prose with custom regular-expression rules and reports each hit with its file and line. It holds no rule for a reference to an earlier reply, it has no way to limit a rule to the body of one section or to skip block quotations, and the stage runner image holds no `vale`, which is NOT_IN_RUNNER. This change builds a small check with Python's `re` module instead. The written cost is 10000 tokens and 2 hours to build and test, 1000 tokens each year to keep, and 500 tokens for each defect to fix. It deletes no internal code.

## Dependencies

None.
