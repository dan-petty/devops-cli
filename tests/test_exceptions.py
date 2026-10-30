"""Unit tests for standardized exception taxonomy."""

from __future__ import annotations

import ast
import inspect
import re
import textwrap

from devops_cli.docs.generator import DocGenerator
from devops_cli.exceptions import (
    BranchAlreadyExistsError,
    ChecksumMismatchError,
    ConfigurationError,
    DevOpsCLIError,
    GitOperationError,
    InvalidBranchNameError,
    InvalidURLError,
    KeyringUnavailableError,
    SSRFBlockedError,
    ToolDownloadError,
    ToolExecutionError,
    ValidationError,
)
from tests.support.paths import REPO_ROOT


def test_base_devops_cli_error() -> None:
    """An error takes its class's codes, and `exit_code=` overrides the exit status of one instance."""

    class CustomError(DevOpsCLIError):
        error_code = "CUSTOM_CODE"
        exit_code = 5

    err = CustomError("Generic error message", details={"k": "v"})
    overridden = CustomError("Subprocess failed", exit_code=7)

    assert (str(err), err.to_dict(), overridden.exit_code, CustomError.exit_code) == (
        "Generic error message",
        {
            "error_code": "CUSTOM_CODE",
            "message": "Generic error message",
            "exit_code": 5,
            "details": {"k": "v"},
        },
        7,
        5,
    )


def test_ssrf_blocked_error() -> None:
    err = SSRFBlockedError("http://192.168.1.1:8000/api")
    assert err.exit_code == 2
    assert err.error_code == "SSRF_BLOCKED"
    assert "<masked>" in str(err)
    assert "192.168.1.1" not in str(err)
    assert err.details["target_url"] == "http://192.168.1.1:8000/api"


def test_ssrf_blocked_error_credentials_and_length_bounded() -> None:
    """Verify SSRFBlockedError masks embedded credentials and bounds details length <= 256."""
    long_path = "a" * 500
    err = SSRFBlockedError(f"http://user:supersecret@10.0.0.1:8080/{long_path}")
    assert "supersecret" not in err.details["target_url"]
    assert "user:***@" in err.details["target_url"]
    assert len(err.details["target_url"]) <= 256


def test_keyring_unavailable_error() -> None:
    err = KeyringUnavailableError()
    assert err.exit_code == 3
    assert err.error_code == "KEYRING_UNAVAILABLE"
    assert "Keyring" in str(err)


def test_validation_exceptions() -> None:
    val_err = ValidationError("Invalid value", field="endpoint")
    assert isinstance(val_err, DevOpsCLIError)
    assert isinstance(val_err, ValueError)
    assert val_err.error_code == "VALIDATION_ERROR"
    assert val_err.exit_code == 1
    assert val_err.details["field"] == "endpoint"

    url_err = InvalidURLError("ftp://example.com", "Unsupported scheme")
    assert isinstance(url_err, ValidationError)
    assert url_err.error_code == "INVALID_URL"
    assert str(url_err) == "Invalid URL for server example.com: Unsupported scheme"
    assert url_err.details["url"] == "example.com"


def test_git_exceptions() -> None:
    git_err = GitOperationError("Git failed", operation="checkout")
    assert isinstance(git_err, DevOpsCLIError)
    assert isinstance(git_err, ValueError)
    assert git_err.error_code == "GIT_OPERATION_ERROR"
    assert git_err.details["operation"] == "checkout"

    branch_name_err = InvalidBranchNameError("-invalid-branch")
    assert isinstance(branch_name_err, GitOperationError)
    assert branch_name_err.error_code == "INVALID_BRANCH_NAME"

    exists_err = BranchAlreadyExistsError("main")
    assert isinstance(exists_err, GitOperationError)
    assert exists_err.error_code == "BRANCH_ALREADY_EXISTS"


def test_tool_exceptions() -> None:
    tool_err = ToolExecutionError("Tool error", tool_name="trivy")
    assert isinstance(tool_err, DevOpsCLIError)
    assert isinstance(tool_err, ValueError)
    assert tool_err.error_code == "TOOL_EXECUTION_ERROR"

    dl_err = ToolDownloadError("https://example.com/bin", "HTTP 404")
    assert isinstance(dl_err, ToolExecutionError)
    assert dl_err.error_code == "TOOL_DOWNLOAD_ERROR"

    csum_err = ChecksumMismatchError(
        "trivy.tar.gz", "actualsha256sumhere", expected_checksum="expectedsha256"
    )
    assert isinstance(csum_err, ToolExecutionError)
    assert csum_err.error_code == "CHECKSUM_MISMATCH"
    assert csum_err.details["expected_checksum"] == "expectedsha256"


def test_config_exceptions() -> None:
    cfg_err = ConfigurationError(
        "Config key missing", key="telemetry.endpoint", details={"extra": "val"}
    )
    assert isinstance(cfg_err, DevOpsCLIError)
    assert isinstance(cfg_err, ValueError)
    assert cfg_err.error_code == "CONFIGURATION_ERROR"
    assert cfg_err.details["key"] == "telemetry.endpoint"
    assert cfg_err.details["extra"] == "val"


def test_one_error_code_maps_to_one_exit_status() -> None:
    """A caller branching on `error_code` cannot act on a code with two exit statuses.

    `EmbeddingsError` reused `LLM_INFERENCE_ERROR` while exiting 1 rather than 10, so the
    generated catalog listed the same code against both.
    """
    statuses: dict[str, set[int]] = {}
    for cls in _error_classes():
        statuses.setdefault(cls.error_code, set()).add(cls.exit_code)

    assert {code: sorted(v) for code, v in statuses.items() if len(v) > 1} == {}


def _error_classes() -> list[type[DevOpsCLIError]]:
    """Every `DevOpsCLIError` subclass of devops-cli's modules that the error catalog imports.

    A test may define a subclass of its own; it is not one of devops-cli's errors.
    """
    DocGenerator._import_all_exception_modules()
    found: list[type[DevOpsCLIError]] = []
    pending: list[type[DevOpsCLIError]] = [DevOpsCLIError]
    while pending:
        for sub in pending.pop().__subclasses__():
            pending.append(sub)
            if sub.__module__.startswith("devops_cli."):
                found.append(sub)
    return found


def _declared_codes(cls: type[DevOpsCLIError]) -> tuple[object, object]:
    return getattr(cls, "error_code", None), getattr(cls, "exit_code", None)


def _built(cls: type[DevOpsCLIError]) -> DevOpsCLIError:
    """An instance of `cls` with a placeholder for each required argument and no override."""
    params = inspect.signature(cls).parameters.values()
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    args = [
        "error" for p in params if p.default is inspect.Parameter.empty and p.kind in positional
    ]
    kwargs = {
        p.name: "error"
        for p in params
        if p.default is inspect.Parameter.empty and p.kind is inspect.Parameter.KEYWORD_ONLY
    }
    return cls(*args, **kwargs)


def test_each_error_class_declares_the_codes_of_its_catalog_row() -> None:
    """The class data of each error is the error code and exit status of its row in docs/ERRORS.md (#2490)."""
    catalog = REPO_ROOT / "docs" / "ERRORS.md"
    rows = {
        match[1]: (match[2], int(match[3]))
        for line in catalog.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"\| `(\w+)` \| `(\w+)` \| `(\d+)` \|", line))
    }

    assert {cls.__name__: _declared_codes(cls) for cls in _error_classes()} == rows


def test_an_error_built_without_an_override_carries_its_class_codes() -> None:
    """No `__init__` changes the error code or exit status that its class declares (#2490)."""
    differ = {
        cls.__name__
        for cls in _error_classes()
        if ((error := _built(cls)).error_code, error.exit_code) != _declared_codes(cls)
    }

    assert differ == set()


def test_no_error_class_has_an_init_that_only_forwards_to_its_base() -> None:
    """An `__init__` that passes its own arguments to its base unchanged, with its base's defaults, repeats the base (#2490).

    An `__init__` that builds a message or details, or that gives an argument a default of its
    own (a default message, a default GitHub operation), carries data and stays.
    """

    def only_forwards(cls: type[DevOpsCLIError]) -> bool:
        init = vars(cls)["__init__"]
        function = ast.parse(textwrap.dedent(inspect.getsource(init))).body[0]
        assert isinstance(function, ast.FunctionDef)
        body = [
            statement
            for statement in function.body
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        ]
        if len(body) != 1 or not isinstance(body[0], ast.Expr):
            return False
        call = body[0].value
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "__init__"
            and isinstance(call.func.value, ast.Call)
            and getattr(call.func.value.func, "id", None) == "super"
        ):
            return False
        own = list(inspect.signature(init).parameters.values())[1:]
        names = {param.name for param in own}
        passes_through = all(
            isinstance(arg, ast.Name) and arg.id in names for arg in call.args
        ) and all(
            isinstance(keyword.value, ast.Name)
            and keyword.value.id == (keyword.arg or keyword.value.id)
            for keyword in call.keywords
        )
        base = inspect.signature(super(cls, cls).__init__).parameters
        same_defaults = all(
            param.kind is inspect.Parameter.VAR_KEYWORD
            or (param.name in base and base[param.name].default == param.default)
            for param in own
        )
        return passes_through and same_defaults

    forwarding = {
        cls.__name__ for cls in _error_classes() if "__init__" in vars(cls) and only_forwards(cls)
    }

    assert forwarding == set()
