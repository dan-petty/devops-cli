Generate an `AGENTS.md` file providing structured guidance and engineering principles for AI coding assistants:
- **Project Scope & Runtime**: Python 3.14+, virtual environment (`uv`), and core tooling.
- **Progressive Verification**: Isolated iterative checks (`uv run pytest`, `ruff check`, `mypy`) vs full CI gate (`devops ci`).
- **Clean Architecture & Design**: High cohesion, low coupling, strict typing, and defensive error handling.
- **Zero-Trust Security**: OS keyring credentials, SSRF mitigation, and bounded subprocess execution.
- **Target-Agnostic Review**: Evaluate target projects by their declared conventions and universal principles.
- **Git Hygiene**: Topic branches (`release/v*` targeting), Conventional Commits, and remote CI checks monitoring.
