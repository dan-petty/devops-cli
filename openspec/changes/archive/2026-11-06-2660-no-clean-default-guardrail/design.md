# Design

## Decisions

- **Put the bullet in `ARCHITECTURE.md` section 7.2, after `Strict Typing`.**: The section lists the rules for Pydantic models, and the guardrail is a model rule. `ARCHITECTURE.md` is a declared hardening surface.
- **State the rule for any result model of a lookup or a check, and give the three models as examples.**: #2636 shows the same defect in more than one model, so a rule tied to one model would not help the next author.
- **Name the two merged tests in the bullet.**: A reader can see which check fails when a clean default returns. The rule then rests on a check, not on prose alone.
- **Write no test for the text of the bullet.**: The two merged tests guard the behavior. A test of the wording would copy the sentence and guard nothing. `devops docs check` already checks the references of the document.
- **Omit spec deltas by setting `skip_specs: true`.**: The change edits one document and alters no behavior that a consumer observes.

## Rejected alternatives

- **Add the sentence to `CONTRIBUTING.md` or `SECURITY.md`.**: The rule is about model design, not about contributor flow or a security control.
- **Close the issue as not planned.**: The audit now counts tests as a guardrail, but no document states the general rule, and a close loses it.
- **Keep the criterion that the audit exits 0 for PR #2647.**: The audit counts the additions of the audited pull request, so no later pull request changes that report. It already reports PR #2647 as hardened through `tests/` and `openspec/specs/`.
