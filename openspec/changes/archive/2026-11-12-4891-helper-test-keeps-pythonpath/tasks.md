# Tasks

## 1. The plain-Python helper test passes in the Service image

Kind: fix. Changes: `tests/invariants/test_hermetic_floor.py`.

- [x] 1.1 Reproduce the failure: run the test with the base interpreter of the venv, which has no pytest, and with pytest, devops-cli and the checkout only on `PYTHONPATH`. On `origin/main` the child fails with `ModuleNotFoundError`.
- [x] 1.2 Start the child with `-P -s` in place of `-I`, and say why in the test docstring.
- [x] 1.3 Verify: the reproduction of 1.1 passes, and `uv run pytest tests/invariants/test_hermetic_floor.py` passes.
