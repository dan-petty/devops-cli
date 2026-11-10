# Design

## Decisions

- One rule in `AGENTS.md` carries the choice, and the skill carries the detail. `AGENTS.md` stays inside its 6,500-character cap.
- The skill uses a table, so an agent compares the two model kinds in one read. It names the settings `ai.model`, `ai.tasks.<task>.model` and `ai.decision_model`.
- The skill states that a rule goes before a decision model and that a Jev answer is evidence. This follows ADR 0019 and ADR 0020.
- The configuration files explain the distinction in comments. They add no key, because this release does not read `ai.decision_model`.
- The three skill copies get the same text. A test already compares them.

## Rejected alternatives

- A new document for the guidance: rejected. An agent must read one more file, and `AGENTS.md` already routes the task to the skill.
- A change to the `pydantic_ai` bridge or the settings: rejected. ADR 0020 gives that work to a separate item, and this item changes no behavior.
- A chat model in `ai.decision_model`: rejected. A chat model writes text, and the settings refuse it.
