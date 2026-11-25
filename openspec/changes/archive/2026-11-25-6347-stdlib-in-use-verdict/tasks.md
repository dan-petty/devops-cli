## 1. Specification & Design

- [x] 1.1 Write OpenSpec proposal, design, tasks, and `roadmap-alternatives` spec delta for `#6347`

## 2. Tests First (RED)

- [x] 2.1 Add RED tests in `tests/roadmap/test_roadmap_alternatives_project_facts.py` and `tests/roadmap/test_roadmap_alternatives.py` covering SBOM PURL signal, deployed suffix signal, third-party tool, empty inventory, non-Python stdlib, and zero `deps.dev` HTTP lookups
- [x] 2.2 Run targeted `pytest` on `origin/main` code and verify the new tests fail

## 3. Implementation & Documentation (GREEN)

- [x] 3.1 Add `_STDLIB_LANGUAGES`, `suffixes` collection from deployed files, and `_stdlib_in_use` check in `src/devops_cli/roadmap/inventory.py`
- [x] 3.2 Update `docs/roadmap/alternatives.md` (`### The tools in use`) to document standard library language matching
- [x] 3.3 Run `ruff format`, `ruff check`, `mypy src/`, and targeted `pytest` suites to verify GREEN

## 4. Verification & Archive

- [x] 4.1 Archive the OpenSpec change with `devops openspec archive`
- [x] 4.2 Run `devops ci --check --no-cache --skip test,outdated` and `devops ci fail-to-pass --base origin/main`
