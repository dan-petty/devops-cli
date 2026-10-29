# Design

## Decision

Delete the guards file and every path that copies or routes to it. Keep the general conventions reader (`nearest_conventions`), because the corpus and the pull request checkout still copy `AGENTS.md`. #2594 decides that reader.

## Rejected alternatives

- **Pass the guards to the group analysis stage.** The stage explains admitted tool findings, and its G10 check refuses any finding id outside the admitted set. The guards say what a review must not report, and in this design the model reports nothing new (ADR 0005).
- **Keep the file as a guide for a person.** Each bullet is written for a model reviewer, for example "Analysis stages MUST NOT declare a variable ... undefined". A person who reviews a pull request does not use it, so it stays a rule with no reader.
- **Move the guards to a Copilot code review instructions file.** GitHub documents `.github/instructions/*.instructions.md` with `excludeAgent: "cloud-agent"` for this. Copilot reviews run only when a person asks, and the file would change what those reviews report, which no item asks for. A person can add it later in one file.
