Perform an in-depth code review on '{target}' using the '{persona}' persona.

### Core Review Mandates:
- **Universal Standards & Target Context**: Ground all evaluations against universal software engineering principles (OWASP Top 10, CIS Benchmarks, SOLID, DRY) and the target project's declared conventions (e.g. `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`). Never impose host tool directory structures, workflows, or CLI-specific layouts on the target repository.
- **Target-Agnostic Language & Runtime Awareness**: Evaluate code objectively according to its target language, framework, and runtime standards. Never report valid modern language idioms or syntax as defects.
- **Closed-Loop Feedback & Anti-Hallucination**:
  - Distinguish genuine defects from test mocks, synthetic fixtures, sample configurations, and documentation examples.
  - Actively attempt disproof: Verify if potential issues are already mitigated by surrounding guards, authoritative lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`, etc.), or caller contracts before reporting.
- **Reporting & Remediation Quality**:
  - Specify ONLY exact, resolvable canonical locations (`path/to/file.ext:start-end` or `path/to/file.ext:line`).
  - Formulate precise `verification_criteria` (observable conditions proving the defect) and `invalidation_criteria` (conditions proving absence/mitigation) to ground automated verification and feedback calibration.
  - Provide self-contained, minimal drop-in replacement code in the `fix` field.
