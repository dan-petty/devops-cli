## Problem or Motivation

Part 2 of #1006. The exception package (`src/devops_cli/exceptions/`, 96 classes, checked at origin/main 08d70ca6, 2026-10-28) states each error code three ways, and most of its code only repeats the base class:

- 32 classes have an `__init__` whose only statement is `super().__init__(...)`.
- 46 `CONST_ERROR_CODE_*` constants in `src/devops_cli/config/constants.py`. Their only importers are the exception modules and `ai/rag/embeddings.py`.
- Some classes are never raised in `src`. The change lists them with the search that shows no `raise` and no `except`.

## Proposed Solution & Architectural Design

- `DevOpsCLIError` reads `error_code` and `exit_code` from class attributes. Each class declares its own. Domain bases add only their structured-detail keys.
- The `__init__` methods that only forward to the base are deleted.
- Classes that no code raises, catches or re-exports are deleted.
- The `CONST_ERROR_CODE_*` constants become class data, and `config/constants.py` keeps none of them.
- `tests/test_exceptions.py` checks a table built from the class hierarchy: one error code maps to one exit status.
- `docs/ERRORS.md` is regenerated and lists the same codes and exit statuses as before.
- The documents that name `CONST_ERROR_CODE_*` say that an exception class declares its `error_code` and `exit_code`.

## Target Subsystem

`src/devops_cli/exceptions/`, `src/devops_cli/config/constants.py`, `docs/ERRORS.md`.

## Existing Tool Considered

Python class attributes hold the codes. No library is needed, and the change deletes code.

## Acceptance criteria

- Each error code and exit status in `docs/ERRORS.md` is the same before and after the change.
- `config/constants.py` holds no `CONST_ERROR_CODE_*`.
- No exception class has an `__init__` that only calls `super().__init__`.
- The tests run offline.

## Related

Parent: #1006. Sibling: one exit seam for every command.


Source: https://github.com/dan-petty/devops-cli/issues/1006

<!-- devops-roadmap-record {"Effort": "Medium", "Priority": "P2-Medium", "Status": "New", "Value": "Medium"} -->
