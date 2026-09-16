Perform an in-depth code review on '{target}' using the '{persona}' persona.

### Core Review Mandates:
- **Target Context**: Ground evaluations against the target project's declared conventions (`AGENTS.md`, `CLAUDE.md`, `README.md`) and universal software engineering principles (OWASP Top 10, CIS Benchmarks, SOLID) without imposing external host assumptions.
- **Falsification & Lockfile Verification**: Actively attempt disproof against target runtime idioms and authoritative lockfiles before reporting. Distinguish production code from test fixtures, mocks, or sample configurations.
- **Remediation & Hygiene**: Output structured JSON citing exact canonical locations (`path/to/file.ext:start-end`), minimal drop-in fixes, and isolated verification criteria.
