Generate an `AGENTS.md` file providing structured guidance and engineering principles for AI coding assistants:
- **Project Scope & Runtime**: Python 3.14+, virtual environment (`uv`), and core tooling.
- **Progressive Verification**: Isolated iterative checks (`uv run pytest`, `ruff check`, `mypy`) vs full CI gate (`devops ci`).
- **Clean Architecture & Design**: High cohesion, low coupling, strict typing, and defensive error handling.
- **Knowledge Base Consultation**: Mandatory consultation of project knowledge base guides (`src/devops_cli/ai/knowledge_base/` or `docs/`) before feature design or refactoring.
- **Zero-Trust Security**: OS keyring credentials, SSRF mitigation, bounded subprocess execution, and strict prohibition on leaking data from hidden, private, or `.gitignored` files into documents or code.
- **Target-Agnostic Review**: Evaluate target projects by their declared conventions and universal principles.
- **Git Hygiene**: Topic branches (`release/v*` targeting), Conventional Commits, and remote CI checks monitoring.
