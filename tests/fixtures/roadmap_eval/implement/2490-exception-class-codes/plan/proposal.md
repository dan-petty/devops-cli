# Proposal

## Why

Issue #2490, part 2 of #1006. Each exception class stated its error code three ways. A `CONST_ERROR_CODE_*` constant in `config/constants.py` held the code. An `__init__` parameter had the code as its default. Each subclass passed its own code to its base again. Most `__init__` methods of the exception package only repeated their base for that reason.

Measured on origin/main d156ce7e (2026-10-28):

- 116 exception classes: `DevOpsCLIError` and the 115 rows of `docs/ERRORS.md`, in `src/devops_cli/exceptions/` and in the other modules that `CONST_DOMAIN_EXCEPTION_MODULES` names. 102 of them have an `__init__`.
- 46 `CONST_ERROR_CODE_*` constants and 4 `CONST_GITHUB_*_ERROR_CODE` constants in `config/constants.py`. After the change no module in `src` imports one of them.
- 10 `DEFAULT_ERROR_CODE` and `DEFAULT_EXIT_CODE` attributes, a third way to state the same codes.
- 7 classes that no module in `src` raises, catches or names: `ConstellationQuiesceError`, `ConstellationFailoverError`, `ConstellationResumeError`, `GitOpsSyncError`, `InsecureConfigError`, `SecretExposureError` and `InvalidVersionError`. `git grep -w <name> -- src ':!src/devops_cli/exceptions/'` finds none of them. Only a test that builds the class itself names each one.

## What Changes

- `DevOpsCLIError` declares `error_code = "DEVOPS_CLI_ERROR"` and `exit_code = 1` as class attributes. Each subclass declares the one that differs from its base. An instance takes its class's codes.
- `exit_code=` stays on `DevOpsCLIError.__init__` and on the domain bases that took it, as an override for one instance. `SubprocessError`, `ToolExecutionError`, `CosignError`, `CosignVerificationError` and the `err_type` of `core/process.py` use it to give a failed subprocess's own status. `error_code=` goes from every `__init__`: no raise site set it.
- 28 `__init__` methods go: the 17 that passed their own arguments to their base unchanged, with their base's defaults; the 4 ingestion and schema errors' `__init__` methods, whose default message no caller used; and the 7 deleted classes. 74 `__init__` methods stay. Each one adds detail keys, builds the message, or gives an argument a default of its own (a default message or a default GitHub operation).
- The 46 `CONST_ERROR_CODE_*` constants, the 4 `CONST_GITHUB_*_ERROR_CODE` constants and the 10 `DEFAULT_*` attributes go. The tests that read a constant compare with the code's string, because the code is what a caller reads.
- The 7 classes no code uses go, with their re-exports and the tests that only built them.
- The error catalog generator reads each class's `error_code` and `exit_code`, and no longer builds an instance with placeholder arguments. Its note on the exit status said that only three command groups exit with it. Since #2487 every command does, so the note says that.
- `CONTRIBUTING.md` says how an exception class declares its codes, and `docs/SDLC.md` points to it.
- `docs/ERRORS.md` keeps the code, exit status, domain and description of each remaining class. Its 7 rows of the deleted classes go, and its note changes as above.
- No command, option or message changes, so the change has no spec delta (`skip_specs: true`).
- This change fits one pull request. With #2487, it completes #1006.

## Impact

- `src/devops_cli/exceptions/`, `src/devops_cli/config/constants.py`, `src/devops_cli/docs/generator.py`.
- The exception classes in `ai/agents/testing.py`, `ai/rag/embeddings.py`, `review/state.py` and `telemetry/memory_profiler.py`.
- `tests/test_exceptions.py`, `tests/test_docs.py`, and the tests that read a deleted constant or built a deleted class.
- `docs/ERRORS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`.

## Feasibility

- `docs/ERRORS.md` on origin/main is the snapshot of the codes before the change. The generator builds it from each class, and `devops docs check` fails when the committed file differs. The new test `test_each_error_class_declares_the_codes_of_its_catalog_row` reads its rows and compares them with the class attributes. On origin/main it fails, because no class declares its codes. After the change it passes with the same 108 rows and without the 7 deleted classes.
- `test_an_error_built_without_an_override_carries_its_class_codes` builds each class with a placeholder for each required argument and no override. It fails on origin/main and passes after the change, so no `__init__` changes a code.
- `git grep -n -E "(error_code|exit_code)=" -- src ':!src/devops_cli/exceptions/'` lists the raise sites. No raise site passes `error_code=`. Raise sites in six modules pass `exit_code=`. In `tf/cost.py`, `security/sbom.py`, `docker/cosign.py` and `core/process.py` it is a failed subprocess's own status, so the override stays. `ai/rag/indexer.py` and `ai/rag/retriever.py` pass 1, the class's own value.
- `git grep -n "CONST_ERROR_CODE_" -- src` finds nothing after the change.

## Existing Tool Considered

Python class attributes hold the codes, and a subclass inherits them. No library is needed. The change builds no registry and deletes code: 28 `__init__` methods, 7 classes, 50 constants and 10 `DEFAULT_*` attributes, with a net 495 fewer lines in `src`.
