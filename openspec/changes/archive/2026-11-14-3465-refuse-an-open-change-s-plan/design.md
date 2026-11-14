# Design

## Decisions

**The rule reads the path, not the link text.** A path under `openspec/changes/` that is not under `openspec/changes/archive/` and ends in `proposal.md` or `design.md` is the plan of a change that no commit merged. A code span or plain text around it makes no difference, so a model cannot evade the rule with formatting.

**The rule sits in the citation gate.** `_evidence_texts` already gives the evidence fields to the citation rules, and the path of another plan is a citation that the staged source does not support, so `check_proposal` reports it under `ProposalGate.CITATION`.

**An archived change's plan stays allowed.** A merged change's `proposal.md` is a recorded decision, and a later plan may cite it as context; the rule refuses only the plan of a change that no commit merged.

## Rejected alternatives

- **Refuse every citation of `openspec/changes/`.** An archived change is history, and a plan may cite it.
- **A prompt rule only.** The prompt already lets a plan cite any text, and a rule without a check leaves the gap of #3439.
- **A new `DefectType`.** The rule refines the citation gate, and no replay case needs a new type.
