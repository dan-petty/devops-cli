# Design

## Rule phrasing in Rule 2

Rule 2 defines premise checks and actions when a premise fails. Adding:
"Close issues as rejected if their functionality has been superseded by newer issues or code changes."
explicitly instructs agents when to close superseded issues instead of continuing obsolete work or returning them to `New`.

## Budget preservation in AGENTS.md

`AGENTS.md` enforces a strict character ceiling (`CONST_AGENTS_MD_MAX_CHARS = 6500`).
The new sentence adds 93 characters. Trimming 107 characters across introductory and secondary phrases keeps the total at 6,480 characters, maintaining compliance.

## Template synchronization

`src/devops_cli/templates/AGENTS.md.j2` generates `AGENTS.md`. Both files include the updated Rule 2 sentence so `devops ai agents` generates matching text.

## Rejected Alternatives

- **Add a separate rule number.** Numbered rules are heavily referenced and constrained by character budgets.
- **Raise CONST_AGENTS_MD_MAX_CHARS.** Only the repository owner can raise safety and quality thresholds.
