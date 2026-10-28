# Tasks

## 1. Each exception class declares its codes

- [x] Add failing tests: each class's `error_code` and `exit_code` attributes equal its row in `docs/ERRORS.md`; an error built with no override carries its class's codes; no `__init__` only forwards to its base
  - Verification: `uv run devops ci test tests/test_exceptions.py`
- [x] Declare `error_code` and `exit_code` as class attributes on `DevOpsCLIError` and each subclass that differs from its base, keep `exit_code=` as an override of one instance, remove `error_code=` from every `__init__`, and delete the `__init__` methods that only forward and the `DEFAULT_*` attributes
  - Verification: `uv run devops ci test tests/test_exceptions.py`
- [x] Delete the 7 classes that no code raises, catches or names, with their re-exports and the tests that only built them
  - Verification: `uv run devops ci test tests/test_exceptions.py tests/test_ai_controller.py tests/test_argo_gitops.py tests/test_zero_plaintext_invariants.py`
- [x] Delete the `CONST_ERROR_CODE_*` and `CONST_GITHUB_*_ERROR_CODE` constants, and compare the tests that read them with the code's string
  - Verification: `uv run devops ci test`
- [x] Read the codes from the class in the error catalog generator, correct its note on the exit status, say in `CONTRIBUTING.md` how a class declares its codes, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2490-exception-class-codes`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
