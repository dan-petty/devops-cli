"""Tests for reading referenced classes and model fields in the stage job (#3344)."""

from __future__ import annotations

from unittest.mock import patch

from devops_cli.exceptions.git import GitOperationError
from devops_cli.roadmap.stage.stage_models import model_fields, referenced_classes
from tests.support.paths import REPO_ROOT


def test_referenced_classes_extracts_dotted_reference_class() -> None:
    texts = ["A task reads `PullStatus.labels` and updates status.", "Just plain words."]
    classes = referenced_classes(texts)
    assert "PullStatus" in classes
    assert referenced_classes(["plain word only"]) == set()


def test_model_fields_reads_module_and_fields() -> None:
    # Commit ce4e32741aec507c2a76decdd7fa57bf7e280748 defines PullStatus without labels.
    commit = "ce4e32741aec507c2a76decdd7fa57bf7e280748"
    result = model_fields(REPO_ROOT, commit, ["PullStatus"])
    assert "PullStatus" in result
    path, fields = result["PullStatus"]
    assert path == "src/devops_cli/github/client.py"
    assert "state" in fields
    assert "head_sha" in fields
    assert "labels" not in fields


def test_model_fields_leaves_out_class_without_base_model() -> None:
    # StageFilter does not subclass BaseModel.
    result = model_fields(REPO_ROOT, "HEAD", ["StageFilter"])
    assert "StageFilter" not in result


def test_model_fields_ignores_module_with_syntax_error() -> None:
    def fake_git(_cwd: object, *args: str, **_kwargs: object) -> str:
        if args[0] == "grep":
            return "HEAD:src/devops_cli/bad.py:1:class BadModel(BaseModel):\nHEAD:src/devops_cli/good.py:1:class GoodModel(BaseModel):\n"
        if args[0] == "show":
            ref = args[1]
            if "bad.py" in ref:
                return "class BadModel(BaseModel):\n    def broken(:\n"
            return "class GoodModel(BaseModel):\n    field_a: str\n"
        raise GitOperationError(f"Unexpected git args: {args}")

    with patch("devops_cli.roadmap.stage.stage_models.git", side_effect=fake_git):
        result = model_fields(REPO_ROOT, "HEAD", ["BadModel", "GoodModel"])
        assert "BadModel" not in result
        assert "GoodModel" in result
        path, fields = result["GoodModel"]
        assert path == "src/devops_cli/good.py"
        assert fields == ("field_a",)
