# Design

## Decisions

- **Record the choice in an architecture decision record, MADR 4 form.**: The choice is difficult to reverse: it fixes which tool owns each repository setting, and where the one baseline of the settings lives.
- **Amend ADR 0026, do not supersede it.**: OpenTofu keeps the organization checks of ADR 0026 decision 5 and the transfer check of its decision 6, so most of ADR 0026 stays in force. ADR 0026 has one amendment, so a second one is allowed.
- **The chosen option names OpenTofu.**: The alternatives check reads a tool that only a rejected option names as a refused tool. OpenTofu stays in force for the organization, so the chosen option names it.
- **D2 to D4 are decision text of the same record.**: Each one is a rule of the command that the owner gave on 2026-11-22 (#6773), and each one is short.
- **Row ACC-3 of the production readiness guideline changes in the same change.**: D1 makes the row wrong (AGENTS.md rule 8).

## Rejected alternatives

- **One record for each decision D1 to D4**: D2 to D4 are rules of one command, and four records cost more of the token budget of the alternatives check.
- **Supersede ADR 0026**: the organization checks and the transfer check stay in force, so a new record must then write them again.
- **Copy the row table of the design into the record**: the README puts row tables in the OpenSpec change of the command (#6773), and the record keeps under 1,000 words.
