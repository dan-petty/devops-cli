# Tasks

## 1. Give whole rows

Kind: behavior. Changes: `src/devops_cli/docs/generator.py`, `tests/docs/test_exceptions.py`, `docs/ERRORS.md`.

- [x] 1.1 Write the tests of `catalog_description`, `catalog_domain` and of the generated rows. They fail on the base
  - Verification: `$ uv run devops ci test tests/docs/test_exceptions.py` fails on the base
- [x] 1.2 Add the two methods, use them in `generate_error_catalog_docs` and generate `docs/ERRORS.md` again
  - Verification: `$ uv run devops ci test tests/docs/test_exceptions.py` passes
