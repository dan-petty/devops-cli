"""Unit tests for standardized exception taxonomy."""

from __future__ import annotations

from devops_cli.exceptions import (
    BranchAlreadyExistsError,
    ChecksumMismatchError,
    ConfigurationError,
    ContextBudgetExceededError,
    DevOpsCLIError,
    GitOperationError,
    InvalidBranchNameError,
    InvalidURLError,
    InvalidVersionError,
    KeyringUnavailableError,
    ModelUnavailableError,
    PersonaExecutionError,
    SecretExposureError,
    SSRFBlockedError,
    ToolDownloadError,
    ToolExecutionError,
    ValidationError,
)


def test_base_devops_cli_error() -> None:
    err = DevOpsCLIError(
        "Generic error message",
        exit_code=5,
        error_code="CUSTOM_CODE",
        details={"k": "v"},
    )
    assert str(err) == "Generic error message"
    assert err.exit_code == 5
    assert err.error_code == "CUSTOM_CODE"
    assert err.to_dict() == {
        "error_code": "CUSTOM_CODE",
        "message": "Generic error message",
        "exit_code": 5,
        "details": {"k": "v"},
    }


def test_ssrf_blocked_error() -> None:
    err = SSRFBlockedError("http://192.168.1.1:8000/api")
    assert err.exit_code == 2
    assert err.error_code == "SSRF_BLOCKED"
    assert "192.168.1.1" in str(err)
    assert err.details["target_url"] == "http://192.168.1.1:8000/api"


def test_keyring_unavailable_error() -> None:
    err = KeyringUnavailableError()
    assert err.exit_code == 3
    assert err.error_code == "KEYRING_UNAVAILABLE"
    assert "Keyring" in str(err)


def test_secret_exposure_error() -> None:
    err = SecretExposureError("aws_key", "src/main.py:12")
    assert err.exit_code == 4
    assert err.error_code == "SECRET_EXPOSURE_DETECTED"
    assert "aws_key" in str(err)
    assert "src/main.py:12" in str(err)


def test_context_budget_exceeded_error() -> None:
    err = ContextBudgetExceededError(token_count=12000, budget=8000, model="gpt-4o")
    assert err.exit_code == 11
    assert err.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert "12000" in str(err)
    assert "8000" in str(err)
    assert err.details["token_count"] == 12000


def test_model_unavailable_error() -> None:
    err = ModelUnavailableError("claude-3-5-sonnet", "anthropic")
    assert err.exit_code == 12
    assert err.error_code == "MODEL_UNAVAILABLE"
    assert "claude-3-5-sonnet" in str(err)


def test_persona_execution_error() -> None:
    err = PersonaExecutionError("devsecops", "auth.py", "Timeout during inference")
    assert err.exit_code == 13
    assert err.error_code == "PERSONA_EXECUTION_ERROR"
    assert "devsecops" in str(err)
    assert "auth.py" in str(err)


def test_validation_exceptions() -> None:
    val_err = ValidationError("Invalid value", field="endpoint")
    assert isinstance(val_err, DevOpsCLIError)
    assert isinstance(val_err, ValueError)
    assert val_err.error_code == "VALIDATION_ERROR"
    assert val_err.exit_code == 1
    assert val_err.details["field"] == "endpoint"

    url_err = InvalidURLError("ftp://insecure.local", "Unsupported scheme")
    assert isinstance(url_err, ValidationError)
    assert url_err.error_code == "INVALID_URL"
    assert "ftp://insecure.local" in str(url_err)

    ver_err = InvalidVersionError("bad-version", tool_name="terraform")
    assert isinstance(ver_err, ValidationError)
    assert ver_err.error_code == "INVALID_VERSION"
    assert "bad-version" in str(ver_err)
    assert ver_err.details["tool_name"] == "terraform"


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
