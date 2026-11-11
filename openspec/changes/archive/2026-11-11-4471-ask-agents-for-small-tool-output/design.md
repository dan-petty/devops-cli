# Design

## Decisions

- The rule is number 14, after the other rules. Many documents and code comments cite a rule by its number (for example "AGENTS.md rule 5"), so a rule in the middle would make them wrong.
- The rule holds only the policy items that the audit upheld: search first, read only the lines that you need, ask each command for less output, and keep the facts that the reader needs. The detail is the list of example commands in the rule itself, so no other document gets a copy.
- The room for the rule comes from command details that another document already owns. Each removed detail stays in that document or in `devops <command> --help`.
- The stub text names the import line itself (`The line `@AGENTS.md` in this file ...`). Claude Code shows the imported file after CLAUDE.md in the context, so a word such as "above" would not be correct for the reader.

## Rejected alternatives

- Raise `CONST_AGENTS_MD_MAX_CHARS`: the cap is a quality threshold, and only the owner can lower a threshold (AGENTS.md rule 5). The invariant test also holds the cap at 6,500 or less.
- "Do not read a file again" and "at most 10 lines" in the rule: the skeptic checks of the audit refuted both. An agent must read a file again after an edit or a change by another process, and a fixed line count drops facts that the reader needs.
- One stub text for all tools that says "AGENTS.md is in your context": GitHub Copilot reads no import line, so it would not get the rules.
- A section in CONTRIBUTING.md with the full draft policy of the audit: CONTRIBUTING.md is not in the start context of an agent, and the upheld items fit in the rule.
