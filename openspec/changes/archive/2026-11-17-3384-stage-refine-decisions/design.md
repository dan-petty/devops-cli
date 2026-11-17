# Design

## Decisions

- **Parser lives in `stage_criteria.py`.** `stage_criteria.py` already cuts the refine block using `_without_refine_block`. Putting `refine_decisions` next to `acceptance_criteria` keeps refine parsing logic in one place and avoids circular imports with `stage_change.py`.
- **Refuse empty decisions and rejected alternatives independently.** When the refine block holds `Chosen` decisions and `proposal.decisions` is empty, record a refusal problem. When the refine block holds `Rejected` alternatives and `proposal.rejected` is empty, record a refusal problem.
- **Checked in `ProposalGate.CRITERIA`.** `check_proposal` evaluates issue body constraints under `ProposalGate.CRITERIA`.

## Rejected alternatives

- **Place parser in `stage_change.py`.** `stage_criteria.py` already defines refine block markers and cuts refine blocks. Placing the parser in `stage_criteria.py` keeps parsing together.
- **Fail only when both decisions and rejected are empty.** If a refine block has both chosen decisions and rejected alternatives, a plan that only copies one while omitting the other drops half of the refined design.
