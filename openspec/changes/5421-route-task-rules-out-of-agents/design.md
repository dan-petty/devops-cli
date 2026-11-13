# Design

## Decisions

- **Keep a sentence when every task needs it or when it is a safety rule.** The safety rules stay inline: never commit or push to `main`, never `--no-verify`, never lower a security or quality threshold, keep private data out, use `devops gh` and `devops pr`, and only a person merges and changes secrets, settings and hardware.
- **Keep rules 1 to 12, their numbers and their titles.** The rule-title test needs the 12 titles of the template. About 17 places cite rule 5 by number for the 5-minute bound, so the bound stays in rule 5.
- **Move a sentence only to a home that holds it.** Most homes already held the sentence. Two homes get a short addition: `SECURITY.md` rule 8 (`example.com` for a domain) and the `ask-jev` skill (ask only when no file or deterministic check can answer).
- **Rule 13 becomes a table row.** The decision model rule applies only when an agent calls a model. Claude Code loads the skill description in each session, and the row keeps a route for agents that do not load skills.
- **Keep the `.data/agent/` path in rule 12.** Each task writes files, and `SECURITY.md` rule 4 describes only where the tool writes its own data.
- **Shorter link text in the table.** A row that `step_rules.py` reads keeps its "When you" cell and its link target; only the visible text changes.
- **Cap 4,500.** It is 6.7 percent above the new size, within the 10 percent that the issue allows, and above the 4,206 characters that the template renders for devops-cli.

## Rejected alternatives

- **Move the 5-minute P0 bound out of rule 5:** it saves 66 characters and changes about 17 citations of rule 5.
- **Drop the link to `README.md`, `docs/CLI_REFERENCE.md`, `docs/ROADMAP_WORKFLOW.md` or the knowledge base:** each holds documents that are then more than two links from `AGENTS.md`.
- **Keep "Close issues as rejected" in `AGENTS.md`:** it applies only to triage, and it conflicts with the "not planned" reason of `docs/SDLC.md`.
- **A cap under 4,206:** the template would need a trim too, for no gain in this repository.
