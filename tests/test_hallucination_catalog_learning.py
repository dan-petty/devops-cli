"""The hallucinations catalog never rewrites its builtin entries (#514) and learns only what a
person judged: one claim about one piece of code, which a later review suppresses (#950)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    _build_builtin_hallucinations,
    get_common_hallucinations_file_path,
    load_common_hallucinations,
    render_negative_exemplars,
    verify_ground_truth_hallucination,
)
from devops_cli.ai.review.judged_claims import JudgedClaim
from devops_cli.ai.review.verification import _apply_single_finding_verification
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


def _finding(title: str, description: str = "d", location: str = "app.py:3") -> Finding:
    return Finding(severity="HIGH", location=location, title=title, description=description)


def _learned(entry_id: str = "JUDGED-000000000001") -> CommonHallucinationEntry:
    """A claim a person judged, as their INVALIDATED verdict records it."""
    return CommonHallucinationEntry(
        id=entry_id,
        name="Directory created world-writable",
        category=HallucinationCategory.GENERAL,
        description="The `append_entry` function creates the directory with mode `0o777`.",
        resolution="The directory holds public assets",
        source="person",
        judged=JudgedClaim(
            project="target",
            file="store.py",
            line=3,
            code_sha256="0" * 64,
            claim=("append_entry",),
        ),
    )


def _write(path: Path, entries: list[CommonHallucinationEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([e.model_dump(mode="json") for e in entries]), encoding="utf-8")


def test_a_model_invalidation_does_not_teach_the_catalog() -> None:
    """Verify an LLM verdict invalidates the finding but records nothing."""
    ledger = get_common_hallucinations_file_path()
    finding = _finding("Directory created world-writable", "mkdir(mode=0o777) in append_entry")

    result = _apply_single_finding_verification(
        finding,
        {
            "verified": False,
            "citation_line": 3,
            "invalidated_criteria_matched": ["Mode is intended"],
        },
        "t",
    )

    assert (result.status, ledger.exists()) == ("INVALIDATED", False)


def test_a_persisted_copy_of_a_builtin_entry_is_ignored() -> None:
    """Verify a learned copy cannot shadow the shipped entry or its later fixes."""
    builtin = _build_builtin_hallucinations()[0]
    polluted = builtin.model_copy(
        update={"pattern_keywords": ["missing", "validation"], "occurrence_count": 225}
    )
    _write(get_common_hallucinations_file_path(), [polluted, _learned()])

    loaded = [e for e in load_common_hallucinations() if e.id in {builtin.id, _learned().id}]

    assert [(e.id, e.source, e == builtin) for e in loaded] == [
        (builtin.id, "builtin", True),
        (_learned().id, "person", False),
    ]


def _entry(
    category: HallucinationCategory, entry_id: str = "HALLUCINATION-TEST"
) -> CommonHallucinationEntry:
    return CommonHallucinationEntry(
        id=entry_id, name="n", category=category, description="d", resolution="r"
    )


@pytest.mark.parametrize(
    ("category", "source", "location", "title", "description", "expected"),
    [
        pytest.param(
            HallucinationCategory.SYNTAX_GRAMMAR,
            "x = 1\n",
            "a.py:1",
            "Syntax error: invalid Python 2 syntax",
            "except A, B:",
            True,
            id="syntax-claim",
        ),
        pytest.param(
            HallucinationCategory.SYNTAX_GRAMMAR,
            "x = eval(input())\n",
            "a.py:1",
            "getattr RCE via resource name",
            "Arbitrary code runs.",
            False,
            id="not-a-syntax-claim",
        ),
        pytest.param(
            HallucinationCategory.BOUNDARY_ERRORS,
            "data = Path(p).read_text()\n",
            "a.py:1",
            "CWE-400 unbounded read_text of a user-uploaded file",
            "handle_upload reads it whole.",
            False,
            id="untrusted-input",
        ),
        pytest.param(
            HallucinationCategory.MUTABLE_DEFAULTS,
            "from pydantic import Field\nx: list = Field(default_factory=list)\n\n\n\n\ndef merge(items=[]):\n    return items\n",
            "a.py:7",
            "Mutable default argument in merge",
            "items=[] is shared.",
            False,
            id="default-factory-elsewhere",
        ),
    ],
)
def test_ground_truth_checks_the_claim(
    tmp_path: Path,
    category: HallucinationCategory,
    source: str,
    location: str,
    title: str,
    description: str,
    expected: bool,
) -> None:
    """Verify a catalog match invalidates only when the file refutes that specific claim."""
    target = tmp_path / "a.py"
    target.write_text(source, encoding="utf-8")

    result = verify_ground_truth_hallucination(
        _finding(title, description, location), _entry(category), target
    )

    assert result is expected


def test_learned_entries_can_be_listed_and_removed() -> None:
    """Verify a learned entry shows in the catalog listing and can be removed; builtins cannot."""
    _write(get_common_hallucinations_file_path(), [_learned(), _learned("JUDGED-000000000002")])
    builtin_id = _build_builtin_hallucinations()[0].id

    listed = cli.invoke(app, ["review", "hallucinations", "list", "--learned", "--json"])
    refused = cli.invoke(app, ["review", "hallucinations", "remove", builtin_id])
    removed = cli.invoke(app, ["review", "hallucinations", "remove", "JUDGED-000000000001"])
    left = [e.id for e in load_common_hallucinations(include_builtin=False)]

    assert (
        sorted(e["id"] for e in json.loads(listed.output)),
        refused.exit_code,
        removed.exit_code,
        left,
    ) == (
        ["JUDGED-000000000001", "JUDGED-000000000002"],
        1,
        0,
        ["JUDGED-000000000002"],
    )


@pytest.mark.parametrize(
    ("source", "location", "title", "description"),
    [
        pytest.param(
            "def handle_upload(path):\n    return Path(path).read_text()\n",
            "upload.py:2",
            "CWE-400: unbounded read_text() of user-uploaded file",
            "handle_upload reads an attacker-supplied file with no size cap, exhausting memory.",
            id="cwe400-upload",
        ),
        pytest.param(
            "def build(items):\n    for item in items:\n        system_prompt = item\n    return system_prompt\n",
            "prompt.py:4",
            "`system_prompt` may be unbound (UnboundLocalError) when the list is empty",
            "If items is empty the loop never assigns system_prompt.",
            id="unbound-local",
        ),
        pytest.param(
            "def retry():\n    return timeout * 2\n",
            "retry.py:2",
            "NameError: undefined variable `timeout` in retry handler",
            "timeout is referenced before any assignment in retry.",
            id="real-nameerror",
        ),
        pytest.param(
            "def load(name):\n    return getattr(module, name)()\n",
            "loader.py:2",
            "getattr on a user-controlled resource name enables code execution",
            "The resource name comes from the request and selects any attribute to call.",
            id="getattr-resource",
        ),
    ],
)
def test_real_defects_pass_the_builtin_catalog(
    tmp_path: Path, source: str, location: str, title: str, description: str
) -> None:
    """Verify the shipped catalog invalidates none of these real defects."""
    from devops_cli.ai.review.verification import _check_catalog_hallucination

    target = tmp_path / location.split(":")[0]
    target.write_text(source, encoding="utf-8")
    finding = _finding(title, description, location)

    assert _check_catalog_hallucination(finding, target).status == "UNVERIFIED"


# =============================================================================
# The catalog learns only from a person's verdicts, one claim at a time (#950)
# =============================================================================

# An entry in the shape the deterministic checks taught the learned catalog (#950): its signature
# pairs two common words. Enabled, entries like it would have invalidated 240 of review session
# 20261001-224227's 903 candidates, 19 VERIFIED HIGH findings among them.
_MACHINE_LEARNED_ENTRY: dict[str, Any] = {
    "id": "HALLUCINATION-AUTO-0000E8C8",
    "name": "Auto-learned: Exception Handling Vulnerability in URL Parsing",
    "category": "general",
    "description": "The URL parser catches two exception types as one tuple.",
    "signature_patterns": ["(?=.*\\bexception\\b)(?=.*\\bhandling\\b)"],
    "pattern_keywords": ["exception", "handling", "parsing"],
    "file_patterns": ["*.py"],
    "resolution": "Syntax validation passed cleanly via language parser (valid Python 3.14+ syntax)",
    "source": "auto_learned",
}

_LOADER = """import json


def load_config(path):
    try:
        return json.loads(path.read_text())
    except:
        return {}
"""

_DOC_RUNNER = """import textwrap


def run_snippet(source, namespace):
    code = compile(textwrap.dedent(source), "doc", "exec")
    exec(code, {"__name__": "count"})
    return namespace
"""

_SEMGREP_EXEC_TITLE = (
    "[python.lang.security.audit.exec-detected.exec-detected] Detected the use of exec(). "
    "exec() can be dangerous if used to evaluate dynamic"
)


def _source_tree(root: Path, files: dict[str, str]) -> Path:
    """A checkout holding `files`, which the review and the verdict both read."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _judge(
    reviews: Path,
    write_review_session: Callable[..., Path],
    findings: list[SavedFinding],
    session: str = "20261002-205520",
    reason: str = "The test runs a snippet it wrote itself",
) -> list[int]:
    """A person's INVALIDATED verdict on each finding of a new session, which records the code
    each finding cites in the working directory's checkout as a review saves it; the exit codes."""
    from devops_cli.ai.review.verification import record_cited_code
    from devops_cli.commands.review import app as review_app

    record_cited_code(findings, Path.cwd())
    write_review_session(
        reviews / session, generated_at="2026-10-02T21:00:00+00:00", findings=findings
    )
    return [
        cli.invoke(
            review_app,
            ["verify", session, "--index", str(n), "--status", "INVALIDATED", "--reason", reason],
        ).exit_code
        for n in range(1, len(findings) + 1)
    ]


def _reviewed(finding: Finding, root: Path) -> Finding:
    """The verdict a later review's deterministic checks give `finding`."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    return _deterministic_pre_verification(finding, repo_root=root)


def test_a_bare_except_stays_unverified_beside_the_learned_exception_handling_entry(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    """Verify a copy of a ledger holding the `exception`+`handling` entry no longer reaches a
    real HIGH finding about a bare `except`, even once `general` ground truth is enabled (#779,
    #770 may not enable it before this purge lands)."""
    from unittest.mock import patch

    from devops_cli.ai.review import common_hallucinations

    tree = _source_tree(tmp_path / "repo", {"cfg.py": _LOADER})
    get_common_hallucinations_file_path().write_text(
        json.dumps([_MACHINE_LEARNED_ENTRY]), encoding="utf-8"
    )
    finding = Finding(
        severity="HIGH",
        location="cfg.py:7",
        title="Broad exception handling: bare `except` in `load_config` hides every failure",
        description="A corrupt file reads as an empty configuration and nothing reports it.",
    )
    with patch.dict(
        common_hallucinations._GROUND_TRUTH_VERIFIERS,
        {HallucinationCategory.GENERAL: lambda *_: True},
    ):
        result = _reviewed(finding, tree)

    assert (result.status, result.verified_by) == ("UNVERIFIED", None)


def test_machine_learned_entries_are_purged_on_first_load_with_one_notice(
    isolate_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify the entries the deterministic checks taught leave the ledger on its first load,
    which says so once."""
    ledger = get_common_hallucinations_file_path()
    ledger.write_text(json.dumps([_MACHINE_LEARNED_ENTRY]), encoding="utf-8")

    with caplog.at_level("WARNING"):
        first = load_common_hallucinations(include_builtin=False)
        second = load_common_hallucinations(include_builtin=False)
    notices = [r for r in caplog.records if r.levelname == "WARNING"]

    assert (first, second, json.loads(ledger.read_text(encoding="utf-8")), len(notices)) == (
        [],
        [],
        [],
        1,
    )


@pytest.mark.parametrize(
    ("source", "title", "by"),
    [
        pytest.param(
            "def parse(text):\n    return text.split()\n",
            "SyntaxError: invalid syntax in `parse`",
            "deterministic:syntax_error",
            id="syntax-check",
        ),
        pytest.param(
            "def parse(text):\n    return helper(text)\n\n\ndef helper(text):\n    return text\n",
            "NameError: `helper` is not defined in parse",
            "deterministic:missing_symbol",
            id="missing-symbol-check",
        ),
    ],
)
def test_deterministic_checks_never_teach_the_catalog(
    tmp_path: Path, isolate_data_dir: Path, source: str, title: str, by: str
) -> None:
    """Verify a deterministic invalidation leaves the learned catalog empty: only a person's
    verdict teaches it."""
    tree = _source_tree(tmp_path / "repo", {"parse.py": source})

    result = _reviewed(
        Finding(severity="HIGH", location="parse.py:2", title=title, description="d"), tree
    )

    assert (result.status, result.verified_by, _learned_ids()) == ("INVALIDATED", by, [])


def _learned_ids() -> list[str]:
    return [e.id for e in load_common_hallucinations(include_builtin=False)]


def test_a_persons_verdict_suppresses_the_same_claim_until_its_code_changes(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a later review drops the finding a person invalidated while the line it cites
    reads the same, and raises it again once that line changes."""
    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER})
    monkeypatch.chdir(tree)
    judged = SavedFinding(
        severity="MEDIUM",
        location="runner.py:6",
        title="`exec` runs a compiled snippet",
        description="exec evaluates code built at runtime.",
        persona="devsecops",
    )
    codes = _judge(isolate_data_dir / "reviews", write_review_session, [judged])

    again = _reviewed(Finding(**judged.model_dump(include=set(Finding.model_fields))), tree)
    (tree / "runner.py").write_text(
        _DOC_RUNNER.replace('exec(code, {"__name__": "count"})', "exec(code, namespace)"),
        encoding="utf-8",
    )
    changed = _reviewed(Finding(**judged.model_dump(include=set(Finding.model_fields))), tree)

    assert (codes, again.status, again.verified_by, changed.status) == (
        [0],
        "INVALIDATED",
        "deterministic:person_verdict",
        "UNVERIFIED",
    )


def test_a_judged_semgrep_exec_finding_suppresses_bandits_b102_at_that_line(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify matching ignores the tool and persona that raised a finding: the `exec` line a
    person judged under Semgrep's title is suppressed when Bandit reports it as B102, as
    review session 20261002-214641 reported it."""
    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER})
    monkeypatch.chdir(tree)
    semgrep = SavedFinding(
        severity="MEDIUM",
        location=f"{tree / 'runner.py'}:6",
        title=_SEMGREP_EXEC_TITLE,
        description="Semgrep AST flaw (python.lang.security.audit.exec-detected.exec-detected)",
        persona="devsecops",
    )
    codes = _judge(isolate_data_dir / "reviews", write_review_session, [semgrep])

    bandit = _reviewed(
        Finding(
            severity="MEDIUM",
            location="runner.py:6",
            title="[B102] Use of exec detected.",
            description="Bandit B102 exec_used",
        ),
        tree,
    )

    assert (codes, bandit.status, bandit.verified_by) == (
        [0],
        "INVALIDATED",
        "deterministic:person_verdict",
    )


def test_a_verdict_naming_no_code_on_its_line_records_no_suppression(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify a suppression needs a code identifier: a finding whose title and description name
    nothing the cited line holds teaches the catalog nothing, and the verdict says so."""
    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER})
    monkeypatch.chdir(tree)
    vague = SavedFinding(
        severity="HIGH",
        location="runner.py:6",
        title="Insecure mocking of process output",
        description="The fake leaves the subprocess unchecked.",
        persona="devsecops",
    )

    with caplog.at_level("WARNING"):
        codes = _judge(isolate_data_dir / "reviews", write_review_session, [vague])

    assert (codes, _learned_ids(), "will not suppress this finding" in caplog.text) == (
        [0],
        [],
        True,
    )


def test_threaded_registrations_keep_every_entry(isolate_data_dir: Path) -> None:
    """Verify registrations from parallel threads, as verification threads made them, all land:
    the ledger's read-modify-write holds a lock."""
    import threading
    import time
    from unittest.mock import patch

    from devops_cli.ai.review.common_hallucinations import register_common_hallucination

    get_common_hallucinations_file_path().write_text("[]", encoding="utf-8")
    entries = [
        CommonHallucinationEntry.model_validate(
            {
                "id": f"JUDGED-{n:012d}",
                "name": f"Claim {n}",
                "category": "general",
                "description": "d",
                "resolution": "r",
                "source": "person",
                "judged": {
                    "project": "target",
                    "file": f"mod{n}.py",
                    "line": 1,
                    "code_sha256": f"{n:064d}",
                    "claim": ["exec"],
                },
            }
        )
        for n in range(8)
    ]
    real_loads = json.loads

    def slow_loads(*args: Any, **kwargs: Any) -> Any:
        # Hold each read open long enough that every thread reads before any writes.
        loaded = real_loads(*args, **kwargs)
        time.sleep(0.02)
        return loaded

    with patch("devops_cli.ai.review.common_hallucinations.json.loads", side_effect=slow_loads):
        threads = [
            threading.Thread(target=register_common_hallucination, args=(e,)) for e in entries
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert sorted(_learned_ids()) == sorted(e.id for e in entries)


def test_a_ledger_that_cannot_be_read_warns(
    isolate_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify a ledger load failure is a warning: a catalog that silently fails to load changes
    review outcomes without changing review output."""
    get_common_hallucinations_file_path().write_text("[{not json", encoding="utf-8")

    with caplog.at_level("WARNING"):
        loaded = load_common_hallucinations(include_builtin=False)

    assert (loaded, [r.levelname for r in caplog.records]) == ([], ["WARNING"])


def test_exemplars_come_from_the_claims_people_judged_most_often(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify the persona is shown the claims a person disproved, the most often judged first,
    as reported against this codebase, and none of the shipped entries while any exist."""
    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER, "cfg.py": _LOADER})
    monkeypatch.chdir(tree)
    recurring = SavedFinding(
        severity="MEDIUM",
        location="runner.py:6",
        title="`exec` runs a compiled snippet",
        description="d",
        persona="devsecops",
    )
    once = SavedFinding(
        severity="HIGH",
        location="cfg.py:7",
        title="Bare `except` hides parse failures",
        description="d",
        persona="devsecops",
    )
    reviews = isolate_data_dir / "reviews"
    codes = [
        *_judge(reviews, write_review_session, [recurring, once], session="20261002-205520"),
        *_judge(reviews, write_review_session, [recurring], session="20261002-214641"),
    ]

    block = render_negative_exemplars(target=tree, limit=1)
    builtin = _build_builtin_hallucinations()[0]

    assert (
        codes,
        "`exec` runs a compiled snippet" in block,
        "Bare `except`" in block,
        "reported against this codebase" in block,
        builtin.description[:40] in block,
    ) == ([0, 0, 0], True, False, True, False)


def test_only_the_target_projects_judged_claims_are_labelled_as_its_own(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a review of another project is not told that this project's judged claims were
    reported against it: it is shown the shipped entries, under their own heading."""
    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER})
    other = _source_tree(tmp_path / "other", {"app.py": "x = 1\n"})
    monkeypatch.chdir(tree)
    codes = _judge(
        isolate_data_dir / "reviews",
        write_review_session,
        [
            SavedFinding(
                severity="MEDIUM",
                location="runner.py:6",
                title="`exec` runs a compiled snippet",
                description="d",
                persona="devsecops",
            )
        ],
    )

    own = render_negative_exemplars(target=tree)
    elsewhere = render_negative_exemplars(target=other)

    assert (
        codes,
        "reported against this codebase" in own,
        "reported against this codebase" in elsewhere,
        "`exec` runs a compiled snippet" in elsewhere,
        bool(elsewhere),
    ) == ([0], True, False, False, True)


# =============================================================================
# A verdict reaches only the claim it judged (#950 review)
# =============================================================================

# Two handlers whose `except` lines read the same: one logs the type and re-raises, the other
# returns the message.
_HANDLERS = """def fetch_a(url):
    try:
        return get(url)
    except Exception as err:
        log(type(err))
        raise


def fetch_b(url):
    try:
        return get(url)
    except Exception as err:
        return str(err)
"""


def _raised(location: str, title: str, severity: str = "HIGH") -> SavedFinding:
    return SavedFinding(
        severity=severity, location=location, title=title, description="d", persona="devsecops"
    )


def _again(finding: SavedFinding, root: Path) -> Finding:
    """The verdict a later review's deterministic checks give `finding`, raised again."""
    return _reviewed(Finding(**finding.model_dump(include=set(Finding.model_fields))), root)


def test_a_verdict_reaches_only_the_line_it_judged(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a person's verdict on one `except Exception as err:` line leaves the same line in
    another function unjudged: the claim's key holds the line it cites, not only its text."""
    tree = _source_tree(tmp_path / "repo", {"api.py": _HANDLERS})
    monkeypatch.chdir(tree)
    title = "Broad `Exception` handler exposes the error"
    codes = _judge(
        isolate_data_dir / "reviews",
        write_review_session,
        [_raised("api.py:4", title)],
        reason="fetch_a logs only the type and re-raises",
    )

    judged = _again(_raised("api.py:4", title), tree)
    other = _again(_raised("api.py:12", title), tree)

    assert (codes, judged.verified_by, other.status, other.verified_by) == (
        [0],
        "deterministic:person_verdict",
        "UNVERIFIED",
        None,
    )


@pytest.mark.parametrize("status", ["VERIFIED", "MITIGATED"])
def test_a_verdict_changed_from_invalidated_stops_suppressing_the_claim(
    status: str,
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a person who changes an INVALIDATED verdict to VERIFIED or MITIGATED withdraws the
    claim it taught, so a later review leaves the finding UNVERIFIED."""
    from devops_cli.commands.review import app as review_app

    tree = _source_tree(tmp_path / "repo", {"runner.py": _DOC_RUNNER})
    monkeypatch.chdir(tree)
    finding = _raised("runner.py:6", "`exec` runs a compiled snippet", "MEDIUM")
    codes = _judge(isolate_data_dir / "reviews", write_review_session, [finding])
    changed = cli.invoke(
        review_app,
        ["verify", "20261002-205520", "--index", "1", "--status", status, "--reason", "Real"],
    )

    later = _again(finding, tree)

    assert (codes, changed.exit_code, _learned_ids(), later.status, later.verified_by) == (
        [0],
        0,
        [],
        "UNVERIFIED",
        None,
    )


def test_a_verdict_in_one_project_leaves_another_projects_identical_code_unjudged(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify two projects sharing one data directory keep their verdicts apart: a person's
    verdict in project A does not suppress project B's finding on identical code."""
    project_a = _source_tree(tmp_path / "project-a", {"runner.py": _DOC_RUNNER})
    project_b = _source_tree(tmp_path / "project-b", {"runner.py": _DOC_RUNNER})
    finding = _raised("runner.py:6", "`exec` runs a compiled snippet", "MEDIUM")
    monkeypatch.chdir(project_a)
    codes = _judge(
        isolate_data_dir / "reviews",
        write_review_session,
        [finding],
        reason="project A only runs constant snippets",
    )

    monkeypatch.chdir(project_b)
    in_b = _again(finding, project_b)
    in_a = _again(finding, project_a)

    assert (codes, in_a.verified_by, in_b.status, in_b.verified_by) == (
        [0],
        "deterministic:person_verdict",
        "UNVERIFIED",
        None,
    )


@pytest.mark.parametrize(
    ("files", "location", "judged_title", "later_title"),
    [
        pytest.param(
            {"loop.py": "def handle(items):\n    for item in items:\n        send(item)\n"},
            "loop.py:2",
            "Unbounded loop in request handler",
            "Shared list mutated while iterated in a thread",
            id="python-keywords",
        ),
        pytest.param(
            {"guide.md": "# Guide\n\nSee the docs to learn more.\n"},
            "guide.md:3",
            "Broken link to the docs",
            "The docs link to nothing",
            id="markdown-words",
        ),
    ],
)
def test_a_claim_naming_only_keywords_or_plain_words_records_nothing(
    files: dict[str, str],
    location: str,
    judged_title: str,
    later_title: str,
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
) -> None:
    """Verify a claim whose only names are language keywords, or plain words of a file that is
    not code, records no suppression, so an unrelated finding on that line stays unjudged."""
    tree = _source_tree(tmp_path / "repo", files)
    monkeypatch.chdir(tree)
    codes = _judge(
        isolate_data_dir / "reviews", write_review_session, [_raised(location, judged_title)]
    )

    later = _again(_raised(location, later_title), tree)

    assert (codes, _learned_ids(), later.status) == ([0], [], "UNVERIFIED")


def test_a_verdict_on_a_session_that_recorded_no_code_suppresses_nothing(
    tmp_path: Path,
    isolate_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_review_session: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify a verdict on a finding whose session recorded no cited code, as sessions written
    before #950 did, records nothing: the file as it reads at verdict time may hold code the
    person never saw."""
    tree = _source_tree(
        tmp_path / "repo", {"m.py": 'def a(src):\n    exec(compile(src, "t", "exec"))\n'}
    )
    monkeypatch.chdir(tree)
    write_review_session(
        isolate_data_dir / "reviews" / "20261002-214641",
        generated_at="2026-10-02T21:46:41+00:00",
        findings=[_raised("m.py:2", "Use of exec on a test snippet", "MEDIUM")],
    )
    (tree / "m.py").write_text("def b(payload):\n    exec(payload)\n", encoding="utf-8")

    with caplog.at_level("WARNING"):
        verdict = cli.invoke(
            app,
            ["review", "verify", "20261002-214641", "--index", "1", "--status", "INVALIDATED"],
        )
    later = _again(_raised("m.py:2", "Remote code execution through exec", "CRITICAL"), tree)

    assert (
        verdict.exit_code,
        _learned_ids(),
        later.status,
        "will not suppress this finding" in caplog.text,
    ) == (0, [], "UNVERIFIED", True)
