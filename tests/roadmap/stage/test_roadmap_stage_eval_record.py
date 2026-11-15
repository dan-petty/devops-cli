"""`devops roadmap eval stage --record`: the constants that a plan cites go into the facts of its
case, read at the base commit of the case (#3390).

The module under test is imported inside each test, so that the file collects on a tree that holds
no recorder, and each test fails on its own assertion there (#3390).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage_eval_cases import CASES_DIRECTORY, NO_COMMIT, load_cases
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CASE = "3410-a-plan-that-states-a-wrong-constant"
SET = REPO_ROOT / CASES_DIRECTORY
Cli = Callable[..., Any]
Read = Callable[[Path, str, Iterable[str]], dict[str, int]]


@pytest.fixture
def copied(tmp_path: Path) -> Path:
    """A folder that holds a copy of the case of a wrong constant, as the command writes it."""
    shutil.copytree(SET / CASE, tmp_path / CASE)
    return tmp_path


def _reader(answer: dict[str, int], seen: list[tuple[Path, str, set[str]]]) -> Read:
    """A read of the constants at a commit that answers `answer` and records what it was asked."""

    def read(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:
        seen.append((source, sha, set(names)))
        return answer

    return read


def _facts(folder: Path) -> dict[str, Any]:
    facts: dict[str, Any] = json.loads((folder / "facts.json").read_text(encoding="utf-8"))
    return facts


def test_record_constants_writes_the_values_of_the_base_commit(
    copied: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.roadmap.stage import stage_eval_record
    from devops_cli.roadmap.stage.stage_eval_record import record_constants, write_constants

    case = load_cases(copied)[0]
    seen: list[tuple[Path, str, set[str]]] = []
    monkeypatch.setattr(
        stage_eval_record, "staged_constants", _reader({"SUMMARY_MAX_CHARS": 60}, seen)
    )
    before = _facts(copied / CASE)

    constants = record_constants(case, copied)
    write_constants(copied / CASE, constants)

    after = _facts(copied / CASE)
    assert constants == (("SUMMARY_MAX_CHARS", 60),)
    assert after["constants"] == [["SUMMARY_MAX_CHARS", 60]]
    assert {key: value for key, value in after.items() if key != "constants"} == {
        key: value for key, value in before.items() if key != "constants"
    }
    assert list(after) == list(before)
    assert [(sha, "SUMMARY_MAX_CHARS" in names) for _, sha, names in seen] == [
        (case.base_commit, True)
    ]


def test_the_record_option_writes_the_facts_of_the_case_and_names_it(
    copied: Path, cli: Cli, monkeypatch: pytest.MonkeyPatch, model_fake: ModelFake
) -> None:
    from devops_cli.roadmap.stage import stage_eval_record

    monkeypatch.setattr(
        stage_eval_record, "staged_constants", _reader({"SUMMARY_MAX_CHARS": 60}, [])
    )

    result = cli("roadmap", "eval", "stage", "--record", "--cases", str(copied))

    assert result.exit_code == 0, result.output
    assert CASE in result.output
    assert _facts(copied / CASE)["constants"] == [["SUMMARY_MAX_CHARS", 60]]
    assert model_fake.call_count == 0


def test_the_record_option_refuses_a_dry_run(copied: Path, cli: Cli) -> None:
    before = (copied / CASE / "facts.json").read_text(encoding="utf-8")

    result = cli("roadmap", "eval", "stage", "--record", "--dry-run", "--cases", str(copied))

    assert result.exit_code == 1
    assert "--dry-run" in result.output
    assert (copied / CASE / "facts.json").read_text(encoding="utf-8") == before


def test_the_record_option_exits_1_for_a_case_that_holds_no_commit(
    copied: Path, cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.roadmap.stage import stage_eval_record

    path = copied / CASE / "case.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**meta, "base_commit": NO_COMMIT}), encoding="utf-8")
    monkeypatch.setattr(stage_eval_record, "staged_constants", _reader({}, []))

    result = cli("roadmap", "eval", "stage", "--record", "--cases", str(copied))

    assert result.exit_code == 1
    assert CASE in result.output
