"""The Vale style of the ASD-STE100 rules (#5157).

Vale checks the hand-written documents with four suggestion rules. The test runs the pinned tool
on fixtures and on `docs/TESTING.md`. It skips when the tool is not installed, as a workstation
without `devops install-tools --tool vale` is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.support.paths import REPO_ROOT
from tests.support.vale import vale


def _sentence(words: int) -> str:
    """A markdown line of `words` words, with no period inside it except the last."""
    parts = [f"word{index}" for index in range(1, words + 1)]
    return " ".join(parts) + ".\n"


def _alerts(path: Path) -> list[dict[str, Any]]:
    result = vale(f"--config={REPO_ROOT / '.vale.ini'}", "--output=JSON", path)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout or "{}").get(str(path), [])


@pytest.mark.live("vale")
def test_a_sentence_of_26_words_is_one_alert(tmp_path: Path) -> None:
    path = tmp_path / "long.md"
    path.write_text(_sentence(26), encoding="utf-8")

    alerts = _alerts(path)

    assert [alert["Check"] for alert in alerts] == ["STE.SentenceLength"]


@pytest.mark.live("vale")
def test_a_sentence_of_25_words_is_no_alert(tmp_path: Path) -> None:
    path = tmp_path / "short.md"
    path.write_text(_sentence(25), encoding="utf-8")

    assert _alerts(path) == []


@pytest.mark.live("vale")
def test_a_contraction_is_one_alert_and_do_not_is_none(tmp_path: Path) -> None:
    contraction = tmp_path / "contraction.md"
    contraction.write_text("Do not wait. It doesn't wait.\n", encoding="utf-8")
    plain = tmp_path / "plain.md"
    plain.write_text("Do not wait for the job.\n", encoding="utf-8")

    assert [alert["Check"] for alert in _alerts(contraction)] == ["STE.Contractions"]
    assert _alerts(plain) == []


@pytest.mark.live("vale")
def test_a_code_span_and_a_code_block_take_no_alert(tmp_path: Path) -> None:
    path = tmp_path / "code.md"
    path.write_text("Run `it doesn't` here.\n\n```sh\nit doesn't run\n```\n", encoding="utf-8")

    assert _alerts(path) == []


@pytest.mark.live("vale")
def test_the_testing_page_passes_with_suggestions() -> None:
    result = vale(f"--config={REPO_ROOT / '.vale.ini'}", "docs/TESTING.md", cwd=REPO_ROOT)

    assert result.returncode == 0
    assert "0 errors" in result.stdout
