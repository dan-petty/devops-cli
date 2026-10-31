"""Unit tests for binary verification utilities (TDD Specification)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from devops_cli.core.binaries import check_binary, require_binary
from devops_cli.exceptions.base import DevOpsCLIError


def test_require_binary_found() -> None:
    """When tool exists on PATH, returns resolved Path object."""
    with patch("shutil.which", return_value="/usr/local/bin/kubectl"):
        res = require_binary("kubectl")
        assert isinstance(res, Path)
        assert res == Path("/usr/local/bin/kubectl")


def test_require_binary_missing_raises_dependency_error() -> None:
    """When tool does not exist, raises DevOpsCLIError with install hint."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(DevOpsCLIError) as exc_info:
            require_binary("missing-tool", install_hint="Install with brew install missing-tool")
        msg = str(exc_info.value)
        assert "missing-tool" in msg
        assert "brew install missing-tool" in msg


def test_check_binary_returns_boolean() -> None:
    """check_binary returns True if found, False otherwise."""
    with patch("shutil.which", return_value="/bin/sh"):
        assert check_binary("sh") is True

    with patch("shutil.which", return_value=None):
        assert check_binary("imaginary_binary") is False
