# Design

## Context

`DevOpsCLIError.__init__` took `error_code` and `exit_code` as keyword arguments, and each subclass passed its own code. The codes were instance data that each `__init__` set again.

## Decisions

### The codes are plain class attributes

`DevOpsCLIError` annotates `error_code: str` and `exit_code: int` and gives the root values. A subclass assigns the one that differs from its base. A plain attribute, not `ClassVar`, lets the `exit_code=` override of one instance assign `self.exit_code`, which mypy refuses for a `ClassVar`.

### `exit_code=` stays as an override of one instance

Five raise sites give an error the exit status of the subprocess that failed: `SubprocessError` and `ToolExecutionError` in `tf/cost.py` and `security/sbom.py`, `CosignError` and `CosignVerificationError` in `docker/cosign.py`, and the `err_type` of `core/process.py`. That status is not the class's, so the base keeps `exit_code: int | None = None`, and the domain bases that took `exit_code` keep it. No raise site passed `error_code=`, so it goes.

### What counts as an `__init__` that only forwards

`test_no_error_class_has_an_init_that_only_forwards_to_its_base` flags an `__init__` whose one statement is `super().__init__(...)`, when the call passes the `__init__`'s own parameters unchanged and each parameter has its base's default. Such an `__init__` repeats its base. An `__init__` that builds the message or the details, or that gives an argument a default of its own, carries data and stays: the `GitHub*` errors give `operation` a default, and `KeyringUnavailableError` and the telemetry errors give the message one.

### The snapshot is `docs/ERRORS.md`

The catalog already holds each class's code and exit status, and `devops docs check` keeps it equal to the code. The test compares the class attributes with its rows, so the codes are checked against one table.

### The tests compare with the string of the code

A test that read `CONST_ERROR_CODE_SECURITY` now compares with `"SECURITY_ERROR"`. The string is what a caller of `error_code` reads.

## Rejected alternatives

- **A registry from code to class.** The class attribute is the one place a code is stated, and the catalog generator already walks the subclasses. A registry would be a second place.
- **`ClassVar[str]` and `ClassVar[int]`.** mypy refuses `self.exit_code = exit_code` on a `ClassVar`, and the override needs it.
- **Keep `error_code=` on the base for symmetry.** No raise site uses it. A keyword that a caller can set lets one class carry two codes, which `test_one_error_code_maps_to_one_exit_status` exists to prevent.
- **Delete every `__init__` whose one statement is a `super().__init__` call**, as the issue counts them. That would change the default `operation` in the details of six GitHub errors and drop the default message of the telemetry errors and `KeyringUnavailableError`, which `KeyringUnavailableError()` uses.
- **A JSON fixture of the codes as the snapshot.** It would repeat `docs/ERRORS.md`, which the docs check already holds equal to the code.
- **Keep the 7 unused classes.** No module raises, catches or names them. Their tests only build them.
