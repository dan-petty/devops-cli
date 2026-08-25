"""Unit tests for standardized exception taxonomy."""

from __future__ import annotations

from devops_cli.exceptions import (
    ContextBudgetExceededError,
    DevOpsCLIError,
    KeyringUnavailableError,
    ModelUnavailableError,
    PersonaExecutionError,
    SecretExposureError,
    SSRFBlockedError,
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
