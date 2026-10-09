"""Tests for `devops review score`: saved review sessions scored offline against a label file (#1138).

The committed label file holds the loop study's clusters of S11 and S12–S21, one per findings.json
row. The recorded slices are trimmed copies of S11, S12, S13 and S18, and their expected figures
are the ones the loop evaluation published (its section 2 table, with the S20-style HIGH count
read from the rows), not numbers this scorer produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import git as gitlib
import pytest
from typer.testing import CliRunner

from devops_cli.ai.run_store import (
    Mechanism,
    RunRecord,
    check_regression,
    compare_runs,
    load_runs,
    new_run,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.main import app
from devops_cli.review.score import (
    LabelFile,
    ScoreReport,
    SessionScore,
    load_label_file,
    materialise_golden,
    score_sessions,
)
from devops_cli.security.normalization import NormalizedFinding
from devops_cli.security.sarif import write_sarif

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

FIXTURES = Path(__file__).parent / "fixtures" / "review_labels"
LABELS = FIXTURES / "labels.json"
S11, S12, S13, S18 = (
    FIXTURES / "sessions" / name
    for name in ("20261003-060647", "20261003-065531", "20261003-073236", "20261003-102523")
)
LOOP_ROWS = {
    "20261003-065531": 47,
    "20261003-073236": 46,
    "20261003-080659": 55,
    "20261003-084218": 43,
    "20261003-091619": 49,
    "20261003-095001": 42,
    "20261003-102523": 28,
    "20261003-105505": 37,
    "20261003-112847": 45,
    "20261003-115921": 49,
}
NEW_INPUT = "feedfacefeedface"


def _fraction(ratio: Any) -> tuple[int, int]:
    return ratio.numerator, ratio.denominator


def _write_session(
    root: Path,
    name: str,
    rows: list[dict[str, Any]],
    pages: dict[str, list[str]],
    *,
    digest: str = NEW_INPUT,
    sarif: list[NormalizedFinding] | None = None,
) -> Path:
    """A saved session: findings.json rows, files/ pages holding their findings' locations."""
    session = root / name
    (session / "files").mkdir(parents=True)
    findings = [{"status": "UNVERIFIED", "severity": "MEDIUM", **row} for row in rows]
    subject = {"type": "path", "ref": "example", "input": digest}
    (session / "findings.json").write_text(json.dumps({"subject": subject, "findings": findings}))
    for index, (page, locations) in enumerate(pages.items()):
        record = {"file_path": page, "findings": [{"location": loc} for loc in locations]}
        (session / "files" / f"page{index}.json").write_text(json.dumps(record))
    if sarif is not None:
        write_sarif(sarif, session / "findings.sarif")
    return session


def _label(key: str, label: str = "false", **identity: Any) -> dict[str, Any]:
    return {
        "identity": {"key": key, "producer": "persona", "origin": identity.get("path"), **identity},
        "label": label,
        "defect_id": key,
        "note": "test label",
        "labeller": "a person",
        "date": "2026-10-09",
    }


def _write_labels(
    root: Path, labels: list[dict[str, Any]], recall_set: Path | None = None, **inputs: Any
) -> Path:
    """A label file of one tuning input for the new sessions' digest."""
    labelled_input = {"name": "new", "split": "tuning", "digests": [NEW_INPUT], **inputs}
    label_file: dict[str, Any] = {"inputs": [labelled_input], "labels": labels}
    if recall_set is not None:
        label_file["recall_set"] = str(recall_set)
    path = root / "labels.json"
    path.write_text(json.dumps(label_file))
    return path


RECALL_SET = FIXTURES.parent / "review_recall" / "recall_set.json"


# --- (a) the label file covers every S11 and loop row -----------------------------------------


def test_the_label_file_maps_every_s11_and_loop_row_to_a_label() -> None:
    """Every findings.json row of S11 and the loop has a cluster, and every cluster a label."""
    label_file: LabelFile = load_label_file(LABELS)
    row_counts = {sid: len(rows) for i in label_file.inputs for sid, rows in i.sessions.items()}
    keys = {label.identity.key for label in label_file.labels}
    mapped = {key for i in label_file.inputs for rows in i.sessions.values() for key in rows}

    assert (
        row_counts,
        sum(row_counts.values()),
        mapped - keys,
        {label.label for label in label_file.labels},
        {i.name: i.split for i in label_file.inputs},
    ) == (
        {"20261003-060647": 51, **LOOP_ROWS},
        492,
        set(),
        {"valid-strict", "valid-lenient", "opinion", "false"},
        {"s11": "tuning", "loop": "tuning", "golden": "held-out"},
    )


def test_a_row_map_naming_no_label_is_refused(tmp_path: Path) -> None:
    labels = _write_labels(tmp_path, [_label("C1", path="a.py")], sessions={"s": ["C1", "C2"]})

    with pytest.raises(ValidationError, match="C2"):
        load_label_file(labels)


def test_a_session_whose_rows_differ_from_its_row_map_is_refused(tmp_path: Path) -> None:
    session = _write_session(tmp_path, "s", [{"location": "a.py:1"}], {"a.py": []})
    labels = _write_labels(tmp_path, [_label("C1", path="a.py")], sessions={"s": ["C1", "C1"]})

    with pytest.raises(ValidationError, match="2 rows"):
        score_sessions([session], labels)


# --- (b) recorded slices reproduce the published baselines -------------------------------------


def _alone(*sessions: Path) -> list[SessionScore]:
    """Each session scored on its own, so no input has two sessions and no κ is computed: only
    the stability test pays statsmodels' import, and every other test stays under a second."""
    return [score_sessions([session], LABELS).sessions[0] for session in sessions]


def test_the_recorded_slices_reproduce_the_published_precision() -> None:
    """S11 prints 12/51, 11/51 and 4/30; each loop slice prints its section 2 row."""
    assert [
        (
            s.rows,
            _fraction(s.lenient),
            _fraction(s.strict),
            _fraction(s.distinct),
            _fraction(s.high),
            _fraction(s.verified),
            _fraction(s.verified_strict),
        )
        for s in _alone(S11, S12, S13, S18)
    ] == [
        (51, (12, 51), (11, 51), (4, 30), (1, 3), (1, 7), (0, 7)),
        (47, (9, 47), (6, 47), (4, 28), (0, 5), (3, 10), (0, 10)),
        (46, (1, 46), (0, 46), (1, 31), (1, 7), (0, 9), (0, 9)),
        (28, (4, 28), (0, 28), (4, 15), (4, 7), (1, 5), (0, 5)),
    ]


def test_the_loop_slices_pin_their_stability_and_pooled_precision() -> None:
    """Jaccard of the three loop slices' row clusters, and Fleiss κ over the 19 they all report.

    Both were computed from clusters.json when the labels were transcribed, as the task file
    records; every identity the three report carries one status in all three, so κ is 1. This is
    the one test that computes κ, so it alone pays statsmodels' import.
    """
    report: ScoreReport = score_sessions([S11, S12, S13, S18], LABELS)
    s11, loop = report.groups
    metrics = report.run_metrics()

    assert (
        (s11.input, s11.sessions, s11.jaccard.value, s11.kappa.value, _fraction(s11.lenient)),
        (loop.input, loop.split, loop.sessions, _fraction(loop.lenient), _fraction(loop.strict)),
        (round(loop.jaccard.value or 0, 4), loop.jaccard.n),
        (loop.kappa.value, loop.kappa.n),
        (metrics["stability_jaccard"], metrics["stability_kappa"], metrics["not_computable"]),
    ) == (
        ("s11", 1, None, None, (12, 51)),
        ("loop", "tuning", 3, (14, 121), (6, 121)),
        (0.3672, 3),
        (1.0, 19),
        (0.3672, 1.0, {}),
    )


def test_precision_splits_by_producer() -> None:
    by_producer = score_sessions([S11], LABELS).sessions[0].by_producer

    assert {
        name: (s.rows, _fraction(s.lenient), _fraction(s.distinct))
        for name, s in by_producer.items()
    } == {
        "kube-linter": (25, (9, 25), (1, 4)),
        "persona": (17, (1, 17), (1, 17)),
        "semgrep": (9, (2, 9), (2, 9)),
    }


# --- (c) unlabelled rows -------------------------------------------------------------------------


def test_an_unlabelled_row_is_listed_and_every_label_ratio_reads_not_computable(
    tmp_path: Path,
) -> None:
    session = _write_session(
        tmp_path,
        "s",
        [{"location": "src/a.py:3"}, {"location": "src/a.py:40"}],
        {"src/a.py": ["src/a.py:3", "src/a.py:40"]},
    )
    labels = _write_labels(tmp_path, [_label("P1", path="src/a.py", start_line=4, end_line=4)])

    report = score_sessions([session], labels)
    scored = report.sessions[0]

    assert (
        [(u.session, u.row, u.location, u.producer) for u in report.unlabelled],
        [r.value for r in (scored.lenient, scored.strict, scored.distinct, scored.known_defects)],
        str(scored.lenient),
        scored.recall_set.reason,
        report.run_metrics()["not_computable"],
    ) == (
        [("s", 2, "src/a.py:40", "persona")],
        [None, None, None, None],
        "not computable (1 of 2 rows unlabelled)",
        None,
        {
            "precision_lenient": "1 of 1 sessions not computable",
            "precision_strict": "1 of 1 sessions not computable",
            "recall": "1 of 1 sessions not computable",
            "stability_jaccard": "no input has two sessions",
            "stability_kappa": "no input has two sessions",
        },
    )


def test_a_score_whose_new_rows_are_unlabelled_fails_the_run_check(tmp_path: Path) -> None:
    """A pipeline change that adds a false finding no label covers cannot pass on precision."""
    pages = {"src/a.py": ["src/a.py:3", "src/a.py:40"]}
    before = _write_session(tmp_path, "before", [{"location": "src/a.py:3"}], pages)
    after = _write_session(
        tmp_path, "after", [{"location": "src/a.py:3"}, {"location": "src/a.py:40"}], pages
    )
    labels = _write_labels(tmp_path, [_label("A", "valid-strict", path="src/a.py", start_line=3)])

    def run(session: Path) -> RunRecord:
        metrics = score_sessions([session], labels).run_metrics()
        return new_run(Mechanism.REVIEW_SCORE, setup={}, subject={}, results=metrics)

    report = check_regression(compare_runs(run(before), run(after)))

    assert (report.passed, [(v.metric, v.reason) for v in report.verdicts]) == (
        False,
        [
            (
                "precision_lenient",
                "Precision lenient not computable (1 of 1 sessions not computable)",
            ),
            (
                "precision_strict",
                "Precision strict not computable (1 of 1 sessions not computable)",
            ),
        ],
    )


# --- (d) location and fixture rules ---------------------------------------------------------------


def test_a_row_outside_the_reviewed_tree_counts_as_false_without_a_label(tmp_path: Path) -> None:
    """A label for app/shell.py would match, but app/shell.py is no page of the session."""
    session = _write_session(
        tmp_path,
        "s",
        [{"location": "app/shell.py:4"}],
        {"src/a.py": [], "tests/golden/review_findings.json": ["app/shell.py:4"]},
    )
    labels = _write_labels(
        tmp_path,
        [_label("C5", "valid-strict", path="app/shell.py", start_line=4, end_line=4)],
    )

    scored = score_sessions([session], labels)

    assert (_fraction(scored.sessions[0].lenient), scored.unlabelled) == ((0, 1), [])


def test_the_s11_shell_row_is_outside_its_reviewed_tree() -> None:
    pages = {json.loads(p.read_text())["file_path"] for p in (S11 / "files").glob("*.json")}

    assert ("app/shell.py" in pages, "tests/golden/review_findings.json" in pages) == (False, True)


def test_a_hit_echoed_from_a_fixture_page_is_not_recall(tmp_path: Path) -> None:
    """The persona copied the recall set's record onto pricing.py; that is not finding it."""
    row = {"location": "src/devops_cli/ai/spend/pricing.py:53"}
    pricing = "src/devops_cli/ai/spend/pricing.py"
    echo = _write_session(
        tmp_path,
        "echo",
        [row],
        {pricing: [], "tests/fixtures/review_recall/recall_set.json": [row["location"]]},
    )
    own = _write_session(tmp_path, "own", [row], {pricing: [row["location"]]})
    labels = _write_labels(tmp_path, [], recall_set=RECALL_SET)

    report = score_sessions([echo, own], labels)

    assert [_fraction(s.recall_set) for s in report.sessions] == [(0, 6), (1, 6)]


def test_echoed_known_defects_are_not_recall_in_the_slices() -> None:
    """S18 reports pricing and investigator only through recall-set echoes, so it found one."""
    assert [_fraction(s.known_defects) for s in _alone(S11, S12, S13, S18)] == [
        (4, 9),
        (4, 9),
        (1, 9),
        (1, 9),
    ]


# --- (e) n beside every ratio ---------------------------------------------------------------------


def _ratios(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "value" in node else []
        return own + [r for child in node.values() for r in _ratios(child)]
    if isinstance(node, list):
        return [r for child in node for r in _ratios(child)]
    return []


def test_every_ratio_carries_its_n_in_the_table_and_the_json() -> None:
    table = cli.invoke(app, ["review", "score", str(S11), str(S12), "--labels", str(LABELS)])
    as_json = cli.invoke(
        app, ["review", "score", str(S11), str(S12), "--labels", str(LABELS), "--json"]
    )
    ratios = _ratios(json.loads(as_json.stdout))

    assert (
        table.exit_code,
        as_json.exit_code,
        all({"numerator", "denominator"} <= r.keys() or "n" in r for r in ratios),
        len(ratios) > 20,
        all(text in table.stdout for text in ("12/51 (23.5%)", "11/51 (21.6%)", "4/30")),
    ) == (0, 0, True, True, True)


# --- (f) new-session identity -------------------------------------------------------------------


def test_new_sessions_match_labels_by_fingerprint_loop_key_and_persona_window(
    tmp_path: Path,
) -> None:
    """Identity comes from findings.sarif, never from a title; persona rows need one label."""
    worktree = "/home/example/worktrees/review-1-commit"
    sarif = [
        NormalizedFinding(
            tool="bandit",
            rule_id="B103",
            severity="LOW",
            message="chmod",
            path="tests/test_tls.py",
            line=243,
            partial_fingerprints={"fingerprint_v2": "fp-b103"},
        ),
        NormalizedFinding(
            tool="kube-linter",
            rule_id="no-read-only-root-fs",
            severity="LOW",
            message="rootfs",
            path="k8s/app.yaml",
            symbol="DaemonSet/app",
        ),
    ]
    rows = [
        {
            "location": f"{worktree}/tests/test_tls.py:243",
            "cited_code": {
                "project": "example",
                "file": "tests/test_tls.py",
                "line": 243,
                "excerpt": "",
            },
        },
        {"location": "k8s/app.yaml:DaemonSet/app"},
        {"location": "src/a.py:12"},
        {"location": "src/a.py:30"},
    ]
    session = _write_session(
        tmp_path,
        "s",
        rows,
        {
            "tests/test_tls.py": [],
            "k8s/app.yaml": [],
            "src/a.py": ["src/a.py:12", "src/a.py:30"],
        },
        sarif=sarif,
    )
    labels = _write_labels(
        tmp_path,
        [
            {
                **_label("B", path="tests/test_tls.py"),
                "identity": {
                    "key": "B",
                    "producer": "bandit",
                    "rule": "B103",
                    "path": "tests/test_tls.py",
                    "start_line": 1,
                    "origin": "tests/test_tls.py",
                    "fingerprint_v2": "fp-b103",
                },
            },
            {
                **_label("K", "valid-strict"),
                "identity": {
                    "key": "K",
                    "producer": "kube-linter",
                    "rule": "no-read-only-root-fs",
                    "path": "k8s/app.yaml",
                    "object": "DaemonSet/app",
                    "origin": "k8s/app.yaml",
                },
            },
            _label("P", "opinion", path="src/a.py", start_line=8, end_line=9),
            _label("Q1", path="src/a.py", start_line=27, end_line=27),
            _label("Q2", path="src/a.py", start_line=34, end_line=35),
        ],
    )

    report = score_sessions([session], labels)

    assert (
        [(u.row, u.location) for u in report.unlabelled],
        {name: s.rows for name, s in report.sessions[0].by_producer.items()},
        _fraction(report.sessions[0].by_producer["kube-linter"].strict),
    ) == (
        [(4, "src/a.py:30")],
        {"bandit": 1, "kube-linter": 1, "persona": 2},
        (1, 1),
    )


def test_stored_scanner_paths_are_made_relative_to_the_input_root() -> None:
    """S11 stored its Semgrep rows with the checkout's absolute paths; read as they are, the two
    valid ollama-profiles.yaml rows would fall outside the reviewed tree and count as false."""
    rows = json.loads((S11 / "findings.json").read_text())["findings"]
    semgrep = score_sessions([S11], LABELS).sessions[0].by_producer["semgrep"]

    assert (
        [rows[i]["location"] for i in (8, 36)],
        _fraction(semgrep.strict),
    ) == (
        [
            "/workspaces/devops-cli/k8s/llm/profiles/ollama-profiles.yaml:53",
            "/workspaces/devops-cli/k8s/llm/profiles/ollama-profiles.yaml:36",
        ],
        (2, 9),
    )


def _kube_linter(check: str, fingerprint: str | None = None) -> NormalizedFinding:
    return NormalizedFinding(
        tool="kube-linter",
        rule_id=check,
        severity="LOW",
        message=check,
        path="k8s/app.yaml",
        symbol="Deployment/app",
        partial_fingerprints={"fingerprint_v2": fingerprint} if fingerprint else {},
    )


def test_two_tool_findings_at_one_place_leave_its_rows_unlabelled(tmp_path: Path) -> None:
    """Two kube-linter checks on one object: no row says which it is, so neither label is used;
    the same result written twice, as sessions write Bandit's B108, is still one finding."""
    rows = [{"location": "k8s/app.yaml:Deployment/app"}] * 2
    pages = {"k8s/app.yaml": []}
    labels = _write_labels(
        tmp_path,
        [
            {
                **_label(check, value),
                "identity": {
                    "key": check,
                    "producer": "kube-linter",
                    "rule": check,
                    "path": "k8s/app.yaml",
                    "object": "Deployment/app",
                    "origin": "k8s/app.yaml",
                },
            }
            for check, value in (
                ("no-read-only-root-fs", "valid-strict"),
                ("run-as-non-root", "false"),
            )
        ],
    )
    two = _write_session(
        tmp_path,
        "two",
        rows,
        pages,
        sarif=[
            _kube_linter("no-read-only-root-fs", "fp-1"),
            _kube_linter("run-as-non-root", "fp-2"),
        ],
    )
    twice = _write_session(
        tmp_path,
        "twice",
        rows,
        pages,
        sarif=[_kube_linter("no-read-only-root-fs", "fp-1")] * 2,
    )

    report = score_sessions([two, twice], labels)

    assert (
        [(u.session, u.row, u.producer, u.identity) for u in report.unlabelled],
        [str(s.lenient) for s in report.sessions],
    ) == (
        [("two", 1, "kube-linter", None), ("two", 2, "kube-linter", None)],
        ["not computable (2 of 2 rows unlabelled)", "2/2 (100.0%)"],
    )


@pytest.mark.parametrize(
    ("findings_json", "match"),
    [(None, "No such file"), ("{", "Invalid JSON"), ('{"findings": "none"}', "valid array")],
)
def test_a_session_without_a_readable_findings_json_is_refused(
    tmp_path: Path, findings_json: str | None, match: str
) -> None:
    """A mistyped SESSION is refused, not scored as a session that reported nothing."""
    session = tmp_path / "session"
    session.mkdir()
    if findings_json is not None:
        (session / "findings.json").write_text(findings_json)
    labels = _write_labels(tmp_path, [])

    with pytest.raises(ValidationError, match=f"(?s)Cannot read review session .*{match}"):
        score_sessions([session], labels)


def test_sessions_without_an_input_digest_are_compared_with_no_other(tmp_path: Path) -> None:
    pages = {"src/a.py": ["src/a.py:3"]}
    rows = [{"location": "src/a.py:3"}]
    first = _write_session(tmp_path, "first", rows, pages, digest="")
    second = _write_session(tmp_path, "second", rows, pages, digest="")
    labels = _write_labels(tmp_path, [_label("A", path="src/a.py", start_line=3)])

    groups = score_sessions([first, second], labels).groups

    assert [(g.input, g.sessions, g.jaccard.reason, g.kappa.reason) for g in groups] == [
        ("first", 1, "the session records no input digest", "the session records no input digest"),
        ("second", 1, "the session records no input digest", "the session records no input digest"),
    ]


# --- (g) stability --------------------------------------------------------------------------------


def test_kappa_is_not_computable_for_one_status_or_one_session(tmp_path: Path) -> None:
    rows = [{"location": "src/a.py:3"}, {"location": "src/a.py:20"}]
    pages = {"src/a.py": ["src/a.py:3", "src/a.py:20"]}
    first = _write_session(tmp_path, "first", rows, pages)
    second = _write_session(tmp_path, "second", rows[:1], pages)
    labels = _write_labels(
        tmp_path,
        [
            _label("A", path="src/a.py", start_line=3, end_line=3),
            _label("B", path="src/a.py", start_line=20, end_line=20),
        ],
    )

    pair = score_sessions([first, second], labels).groups[0]
    alone = score_sessions([first], labels).groups[0]

    assert (
        (pair.jaccard.value, pair.jaccard.n, pair.kappa.value, pair.kappa.reason),
        (alone.jaccard.reason, alone.kappa.reason),
    ) == (
        (0.5, 1, None, "every rating is UNVERIFIED"),
        ("one session", "one session"),
    )


def test_stability_needs_an_identity_on_every_row_and_one_every_session_reported(
    tmp_path: Path,
) -> None:
    pages = {"src/a.py": ["src/a.py:3", "src/a.py:20", "src/a.py:90"]}
    first = _write_session(tmp_path, "first", [{"location": "src/a.py:3"}], pages)
    second = _write_session(tmp_path, "second", [{"location": "src/a.py:20"}], pages)
    third = _write_session(tmp_path, "third", [{"location": "src/a.py:90"}], pages)
    labels = _write_labels(
        tmp_path,
        [
            _label("A", path="src/a.py", start_line=3, end_line=3),
            _label("B", path="src/a.py", start_line=20, end_line=20),
        ],
    )

    disjoint = score_sessions([first, second], labels).groups[0]
    unidentified = score_sessions([first, third], labels).groups[0]

    assert (
        (disjoint.jaccard.value, disjoint.kappa.reason),
        (unidentified.jaccard.reason, unidentified.kappa.reason),
    ) == (
        (0.0, "no identity every session reported"),
        ("1 rows have no identity", "1 rows have no identity"),
    )


# --- (h) golden materialisation -------------------------------------------------------------------


def test_the_golden_set_materialises_as_one_fixed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pinned id is the commit `git commit` makes of these files with that author and date."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"files": {"app/db.py": "query = f'{x}'\n", "a.py": "x = 1\n"}}))
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "name": "golden",
                        "split": "held-out",
                        "source": "golden.json",
                        "accepted_loss": [{"defect_id": "logic", "reason": "no rule"}],
                    }
                ],
                "labels": [],
            }
        )
    )

    first = materialise_golden(labels, tmp_path / "one")
    second = materialise_golden(labels, tmp_path / "two")
    commits = list(gitlib.Repo(tmp_path / "one").iter_commits())

    assert (
        first.commit,
        second.commit,
        len(commits),
        (tmp_path / "one" / "app" / "db.py").read_text(),
        [(loss.defect_id, loss.reason) for loss in first.accepted_loss],
    ) == (
        "63b6e3c00959a24f7f5badfa9508a96cca4504ae",
        first.commit,
        1,
        "query = f'{x}'\n",
        [("logic", "no rule")],
    )


def test_materialising_into_a_directory_that_holds_files_or_a_file_is_refused(
    tmp_path: Path,
) -> None:
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "file").write_text("x")
    (tmp_path / "plain").write_text("x")

    with pytest.raises(ValidationError, match="not empty"):
        materialise_golden(LABELS, tmp_path / "taken")
    with pytest.raises(ValidationError, match="not a directory"):
        materialise_golden(LABELS, tmp_path / "plain")


def test_the_committed_golden_input_lists_its_accepted_recall_loss() -> None:
    golden = next(i for i in load_label_file(LABELS).inputs if i.name == "golden")
    loss = {entry.defect_id for entry in golden.accepted_loss}

    assert (
        {"missing-containment", "missing-depth-limit"} <= loss,
        loss & set(golden.known_defects),
        len(loss) + len(golden.known_defects),
    ) == (True, set(), 24)


def test_a_session_whose_digest_is_not_its_mapped_input_is_refused(tmp_path: Path) -> None:
    session = _write_session(tmp_path, "s", [{"location": "a.py:1"}], {"a.py": []}, digest="other")
    labels = _write_labels(tmp_path, [_label("C1", path="a.py")], sessions={"s": ["C1"]})

    with pytest.raises(ValidationError, match="reviewed input other"):
        score_sessions([session], labels)


@pytest.mark.parametrize(
    ("label_file", "golden", "match"),
    [
        ("{", None, "Cannot read label file"),
        ('{"inputs": [], "labels": []}', None, "names no golden input source"),
        (
            '{"inputs": [{"name": "g", "split": "held-out", "source": "g.json"}], "labels": []}',
            '{"files": {"../escape.py": "x"}}',
            "lies outside",
        ),
        (
            '{"inputs": [{"name": "g", "split": "held-out", "source": "g.json"}], "labels": []}',
            '{"files": {"a.py": "x", "sub/../.git/hooks/post-checkout": "x"}}',
            "lies in the repository's .git directory",
        ),
        (
            '{"inputs": [{"name": "g", "split": "held-out", "source": "g.json"}], "labels": []}',
            None,
            "Cannot read golden set",
        ),
    ],
)
def test_a_golden_set_that_cannot_be_written_is_refused(
    tmp_path: Path, label_file: str, golden: str | None, match: str
) -> None:
    (tmp_path / "labels.json").write_text(label_file)
    if golden is not None:
        (tmp_path / "g.json").write_text(golden)

    with pytest.raises(ValidationError, match=match):
        materialise_golden(tmp_path / "labels.json", tmp_path / "out")
    assert not (tmp_path / "out" / "a.py").exists()


def test_a_recall_set_or_findings_sarif_that_does_not_parse_is_refused(tmp_path: Path) -> None:
    session = _write_session(tmp_path, "s", [{"location": "a.py:1"}], {"a.py": []})
    labels = _write_labels(tmp_path, [], recall_set=tmp_path / "missing.json")
    (tmp_path / "plain").mkdir()
    (session / "findings.sarif").write_text('{"version": "1.0"}')

    with pytest.raises(ValidationError, match="Cannot read recall set"):
        score_sessions([session], labels)
    with pytest.raises(ValidationError, match="is not SARIF"):
        score_sessions([session], _write_labels(tmp_path / "plain", []))


# --- (i) the command records a run ----------------------------------------------------------------


def test_review_score_records_a_run(isolate_data_dir: Path) -> None:
    """S11 and S12 are two inputs of one session each, so the run records why it has no
    stability figure; the stability test pins the figures a run of one input records."""
    result = cli.invoke(
        app, ["review", "score", str(S11), str(S12), "--labels", str(LABELS), "--json"]
    )
    (run,) = load_runs(Mechanism.REVIEW_SCORE)

    assert (
        result.exit_code,
        run.subject["inputs"],
        (run.results["precision_lenient"], run.results["precision_strict"]),
        run.results["not_computable"],
        run.results["median_llm_calls"],
        [group["input"] for group in json.loads(result.stdout)["groups"]],
    ) == (
        0,
        ["197b2f088fcf1557", "3d555ac817ab1d60"],
        (round(21 / 98, 4), round(17 / 98, 4)),
        {
            "stability_jaccard": "no input has two sessions",
            "stability_kappa": "no input has two sessions",
        },
        412.0,
        ["s11", "loop"],
    )


def test_review_score_needs_sessions_or_a_golden_directory() -> None:
    result = cli.invoke(app, ["review", "score", "--labels", str(LABELS)])

    assert (result.exit_code, "SESSION" in result.output) == (1, True)


def test_review_score_materialises_the_golden_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    result = cli.invoke(
        app,
        ["review", "score", "--labels", str(LABELS), "--materialise-golden", str(tmp_path / "g")],
    )

    assert (
        result.exit_code,
        "missing-containment" in result.stdout,
        (tmp_path / "g" / "core" / "paths.py").is_file(),
    ) == (0, True, True)


def test_review_score_reports_what_it_refuses(tmp_path: Path) -> None:
    bad_labels = tmp_path / "labels.json"
    bad_labels.write_text("{")
    golden = str(tmp_path / "g")

    def run(*args: str) -> Any:
        return cli.invoke(app, ["review", "score", *args])

    refused = run(str(S12), "--labels", str(bad_labels))
    both = run(str(S12), "--labels", str(LABELS), "--materialise-golden", golden)
    no_golden = run("--labels", str(bad_labels), "--materialise-golden", golden)

    assert (
        (refused.exit_code, "Cannot read label file" in refused.output),
        (both.exit_code, "takes no SESSION" in both.output),
        (no_golden.exit_code, "Cannot read label file" in no_golden.output),
    ) == ((1, True), (1, True), (1, True))


def test_review_score_writes_the_golden_set_as_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    result = cli.invoke(
        app,
        [
            "review",
            "score",
            "--labels",
            str(LABELS),
            "--materialise-golden",
            str(tmp_path / "g"),
            "--json",
        ],
    )
    written = json.loads(result.stdout)

    assert (result.exit_code, written["files"], len(written["accepted_loss"])) == (0, 28, 12)


def test_the_table_lists_unlabelled_rows_and_the_recall_set(tmp_path: Path) -> None:
    session = _write_session(tmp_path, "s", [{"location": "src/a.py:40"}], {"src/a.py": []})
    labels = _write_labels(tmp_path, [], recall_set=RECALL_SET)

    result = cli.invoke(app, ["review", "score", str(session), "--labels", str(labels)])

    assert (
        result.exit_code,
        "Unlabelled Rows (1)" in result.output,
        "src/a.py:40" in result.output,
        "k8s/otel/networkpolicy.yaml:18-35" in result.output,
        "not computable (1 of 1 rows unlabelled)" in result.output,
    ) == (0, True, True, True, True)


# --- (k) the recall protocol's matching rules -----------------------------------------------------


def test_recall_counts_the_samples_whose_report_cites_each_finding(tmp_path: Path) -> None:
    """A match names the set's file and cites a line inside its range, which spans the construct.

    Sessions S1 to S4 cited the monitoring policy's world-open rule at its port list (46-48) and
    the investigator's `except` at its `try` (280); a false finding three lines from
    `VISION.md:12` is no hit, nor is a location without line numbers, as kube-linter gives.
    """
    entries = json.loads(RECALL_SET.read_text())["findings"]
    pages = {entry["path"]: [] for entry in entries}
    investigator = "src/devops_cli/ai/rag/investigator.py"
    s1 = _write_session(
        tmp_path,
        "s1",
        [
            {"location": "k8s/monitoring/networkpolicy.yaml:19-20"},
            {
                "location": f"/r/t/{investigator}:280",
                "cited_code": {"project": "x", "file": investigator, "line": 280, "excerpt": ""},
            },
            {"location": "src/devops_cli/ai/spend/pricing.py:60"},
        ],
        pages,
    )
    s2 = _write_session(
        tmp_path,
        "s2",
        [
            {"location": "k8s/otel/networkpolicy.yaml:NetworkPolicy/otel"},
            {"location": "k8s/monitoring/networkpolicy.yaml:46-48"},
            {"location": "docs/VISION.md:7-9"},
        ],
        pages,
    )
    labels = _write_labels(tmp_path, [], recall_set=RECALL_SET)

    report = score_sessions([s1, s2], labels)

    assert (
        [(e.location, e.reported_in, e.sessions) for e in report.recall_set],
        [_fraction(s.recall_set) for s in report.sessions],
    ) == (
        [
            ("k8s/monitoring/networkpolicy.yaml:18-47", 2, 2),
            ("k8s/otel/networkpolicy.yaml:18-35", 0, 2),
            ("src/devops_cli/ai/rag/investigator.py:280-295", 1, 2),
            ("docs/VISION.md:12-12", 0, 2),
            ("src/devops_cli/ai/spend/pricing.py:53-56", 0, 2),
            ("src/devops_cli/ai/spend/pricing.py:65-68", 0, 2),
        ],
        [(2, 6), (1, 6)],
    )
