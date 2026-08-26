"""Unit tests for Dive container layer efficiency analyzer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from devops_cli.security.dive import run_dive_analysis


def test_dive_fallback_analysis() -> None:
    with patch("shutil.which", return_value=None):
        result = run_dive_analysis("test-image:latest")
        assert result.image_name == "test-image:latest"
        assert result.efficiency_score > 0.9
        assert len(result.layers) == 2


def test_dive_mocked_binary_execution() -> None:
    fake_output = json.dumps(
        {
            "layer": [
                {
                    "digest": "sha256:1234",
                    "sizeBytes": 50000000,
                    "wastedBytes": 1000000,
                    "command": "RUN apt-get update",
                }
            ],
            "image": {
                "efficiencyScore": 0.95,
                "wastedBytes": 1000000,
                "sizeBytes": 50000000,
            },
        }
    )

    mock_proc = MagicMock()
    mock_proc.stdout = fake_output

    with patch("shutil.which", return_value="/usr/local/bin/dive"):
        with patch("subprocess.run", return_value=mock_proc):
            result = run_dive_analysis("my-app:v1")
            assert result.image_name == "my-app:v1"
            assert result.efficiency_score == 0.95
            assert result.wasted_bytes == 1000000
            assert len(result.layers) == 1
            assert result.layers[0].digest == "sha256:1234"


def test_dive_empty_output_and_exception() -> None:
    """Test empty stdout and exception handling in Dive analyzer."""
    mock_empty = MagicMock(stdout="")
    with patch("shutil.which", return_value="/usr/local/bin/dive"):
        with patch("subprocess.run", return_value=mock_empty):
            res_empty = run_dive_analysis("empty-img:v1")
            assert res_empty.image_name == "empty-img:v1"
            assert res_empty.efficiency_score == 1.0

        with patch("subprocess.run", side_effect=RuntimeError("Dive failure")):
            res_err = run_dive_analysis("err-img:v1")
            assert res_err.image_name == "err-img:v1"
