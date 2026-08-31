## Paginated Code Review Protocol
Analyze the code segment using systematic chain-of-thought evaluation:
1. **Context & Invariants**: Inspect chunk boundaries, imported symbols, and type contracts against visible code and target project conventions.
2. **Evidence Grounding**: Trace control and data flow to prove defects exist in visible lines before reporting.
3. **Falsification Testing**: Verify if potential issues are already mitigated by surrounding handlers, lockfiles, or callers.
4. **Actionable Remediation**: Provide minimal, self-contained drop-in replacement code for every verified finding using canonical location formatting (`filename.ext:start-end`).
