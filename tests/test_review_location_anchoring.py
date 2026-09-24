"""Findings located by a bare file or function name are tied to the file under review (#535).

In the first sample validation (#505), 36 of 208 candidate findings named no directory:
`flag_groups.go:111-116`, `Dockerfile:7`, `getBodySize:18-24`. The review knows the file of the
page each finding came from, but kept the model's text, so the finding was tied to no file.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from devops_cli.ai.review import pipeline
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding, anchor_location

BODY_TS = "17\t\n18\texport const getBodySize = (body?: BodyInit): number => {\n"
NVM_SH = '1368\tnvm_alias_path() {\n1369\t  nvm_echo "$(nvm_version_dir old)/alias"\n'


@pytest.mark.parametrize(
    ("location", "fpath", "page", "expected"),
    [
        ("flag_groups.go:111-116", "cobra/flag_groups.go", "", "cobra/flag_groups.go:111-116"),
        ("Dockerfile:7", "nginx/debian/Dockerfile", "", "nginx/debian/Dockerfile:7"),
        ("dockerfile:7", "nginx/debian/Dockerfile", "", "nginx/debian/Dockerfile:7"),
        ("read.rs", "serde-json/src/read.rs", "", "serde-json/src/read.rs"),
        ("getBodySize:18-24", "ky/utils/body.ts", BODY_TS, "ky/utils/body.ts:18-24"),
        ("nvm_alias_path() { 1368-1374", "nvm/nvm.sh", NVM_SH, "nvm/nvm.sh:1368-1374"),
        ("", "pkg/app.py", "", "pkg/app.py"),
    ],
)
def test_a_bare_location_is_tied_to_the_file_under_review(
    location: str, fpath: str, page: str, expected: str
) -> None:
    """Verify a bare file name, a symbol the page defines, or nothing, becomes the file's path."""
    assert anchor_location(location, fpath, page) == expected


@pytest.mark.parametrize(
    ("location", "fpath", "page"),
    [
        # Already a path.
        ("src/app.py:3", "pkg/app.py", ""),
        # Another file: its name is not this file's, whatever the page mentions.
        ("config.yaml:3", "pkg/app.py", '1\tCONFIG = "config.yaml"\n'),
        # A symbol this page never names.
        ("renderTemplate:40", "ky/utils/body.ts", BODY_TS),
    ],
)
def test_a_location_naming_nothing_on_the_page_is_left_alone(
    location: str, fpath: str, page: str
) -> None:
    """Verify only what the page can vouch for is rewritten."""
    assert anchor_location(location, fpath, page) == location


class _Step:
    agent_name = "DevSecOps"
    backend_info = ""
    thoughts = None

    def __init__(self, content: str) -> None:
        self.content = content
        self.parsed_data = None


class _Pipeline:
    """A persona pipeline answering every page with the same reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply

    def run(self, prompt: str, **_: object) -> SimpleNamespace:
        return SimpleNamespace(steps=[_Step(self.reply)])


def test_the_page_review_anchors_its_findings_and_counts_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a review ties bare locations to its file and records the ones it cannot."""
    source = tmp_path / "pkg" / "flag_groups.go"
    source.parent.mkdir()
    source.write_text("package cobra\n\nfunc validateFlagGroups() error {\n\treturn nil\n}\n")
    fpath = str(source)
    reply = (
        '{"findings": ['
        '{"location": "flag_groups.go:3-5", "severity": "HIGH", "title": "Group check skipped",'
        ' "description": "validateFlagGroups returns nil.", "fix": "Check the groups."},'
        '{"location": "other.go:9", "severity": "LOW", "title": "Unused import",'
        ' "description": "fmt is unused.", "fix": "Remove it."}]}'
    )
    orchestrator = ReviewPipelineOrchestrator(session_id="s535", target_dir=tmp_path)
    monkeypatch.setattr(pipeline, "print_info", lambda *a, **k: None)
    payload = FileReviewPayload(file_path=fpath)

    orchestrator._review_single_file_payload(
        1,
        1,
        payload,
        {},
        ["devsecops"],
        "test",
        pipeline=_Pipeline(reply),  # type: ignore[arg-type]
        persona_lookup={"DevSecOps": ("devsecops", "DevSecOps")},
    )

    assert sorted(f.location for f in payload.findings) == sorted([f"{fpath}:3-5", "other.go:9"])
    assert (
        payload.ai_scratchpad["anchored_locations"],
        payload.ai_scratchpad["unanchored_locations"],
    ) == (["flag_groups.go:3-5"], ["other.go:9"])
    assert all(isinstance(f, SavedFinding) for f in payload.findings)
