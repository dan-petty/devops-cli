# Design

## Decisions

- **Keep a sentence when every task needs it or when it is a safety rule.** The safety rules stay inline: never commit or push to `main`, never `--no-verify`, never lower a security or quality threshold, keep private data out, use `devops gh` and `devops pr`, and only a person merges and changes secrets, settings and hardware.
- **Keep the whole private-data rule in rule 10.** The implement step of the Service reads `AGENTS.md` word for word (`rules_sections` in `src/devops_cli/roadmap/step_rules.py`), and it gets `SECURITY.md` only for a group under `src/devops_cli/security/**`. A group under `k8s/**` or `tf/**` writes the image registries and the host paths. So rule 10 keeps the private registry, the device path and the placeholders `example.com`, RFC 5737 and `<storage-node>`. `SECURITY.md` rule 8 keeps the full list.
- **Keep rules 1 to 12, their numbers and their titles.** The rule-title test needs the 12 titles of the template. About 17 places cite rule 5 by number for the 5-minute bound, so the bound stays in rule 5.
- **Keep the model-call limit in rule 7.** "Only when no file or deterministic check can answer" applies to every `devops ai` call, generative or not. Rule 7 links the `ask-jev` skill, which owns the choice between a decision model and a generative model. The old rule 13 leaves the list, and the old rule 14 becomes rule 13.
- **Keep the superseded-item case in rule 2.** The premise check of every task finds an item that newer issues or code already replace. Rule 2 says to close it as not planned, and `docs/SDLC.md` Phase 1 gives the same cases with the command.
- **Move a sentence only to a home that holds it.** Most homes already held the sentence. Two homes get a short addition: `SECURITY.md` rule 8 (`example.com` for a domain) and the naming table of `CONTRIBUTING.md` (the form `<path>.bak-<YYYYMMDD-HHMMSS>` of a backup copy).
- **Drop the description line.** It is not a rule, and `README.md` holds it.
- **Shorter link text in the table.** A row that `step_rules.py` reads keeps its "When you" cell and its link target; only the visible text changes.
- **Cap 4,500.** It is 6.6 percent above the new size of 4,220 characters, within the 10 percent that the issue allows, and above the 4,206 characters that the template renders for devops-cli.

## Rejected alternatives

- **Move the 5-minute P0 bound out of rule 5:** it saves 66 characters and changes about 17 citations of rule 5.
- **Drop the link to `README.md`, `docs/CLI_REFERENCE.md`, `docs/ROADMAP_WORKFLOW.md` or the knowledge base:** each holds documents that are then more than two links from `AGENTS.md`.
- **Put the placeholders in the prompt of the implement step:** the prompt holds only the rules of the runner and leaves the rules of the project to `AGENTS.md` (#3097, `DROPPED_RULES` in `tests/roadmap/implement/test_roadmap_implement_prompt.py`).
- **Route `SECURITY.md` to the groups under `k8s/**` and `tf/**`:** the route gives the whole section "Zero-Trust Security & Egress Safety Principles", about 24,700 characters, to each step.
- **A separate table row for the `ask-jev` skill:** the link in rule 7 gives the same route for 32 fewer characters.
- **A cap under 4,206:** the template would need a trim too, for no gain in this repository.
