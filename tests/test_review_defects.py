"""Synthetic defect corpora: injected defects at recorded locations, and review recall against them."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review import runner
from devops_cli.ai.review.defects import (
    CORPUS_CONVENTIONS_FILE,
    CORPUS_FILES_DIR,
    CORPUS_MANIFEST,
    DefectCorpus,
    Injection,
    generate_corpus,
    score_corpus,
    select_templates,
)
from devops_cli.ai.review.profile import ReviewProfile
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})

BOUNDS = """def take(items, n):
    if n > len(items):
        raise ValueError("too many")
    return items[:n]
"""
CONTAINMENT = """def read(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise PermissionError(name)
    return path.read_text()
"""
AWAIT = """async def fetch(client):
    response = await client.get("/")
    return response
"""


def _inject(
    template: str, filename: str, text: str
) -> tuple[str, tuple[int, int], tuple[str, ...]]:
    (chosen,) = select_templates([template])
    find = chosen.finder_for(filename)
    assert find is not None
    lines = text.splitlines(keepends=True)
    site = find(lines)[0]
    mutated = "".join([*lines[: site.start], *site.replacement, *lines[site.end :]])
    return mutated, site.region, site.evidence


@pytest.mark.parametrize(
    ("template", "filename", "text", "expected", "region", "evidence"),
    [
        (
            "drop-bounds-check",
            "app.py",
            BOUNDS,
            "def take(items, n):\n    return items[:n]\n",
            (1, 2),
            (),
        ),
        (
            "drop-path-containment",
            "files.py",
            CONTAINMENT,
            "def read(base, name):\n    path = (base / name).resolve()\n    return path.read_text()\n",
            (1, 3),
            ("is_relative_to",),
        ),
        (
            "drop-await",
            "client.py",
            AWAIT,
            AWAIT.replace("await client", "client"),
            (2, 2),
            ("client.get",),
        ),
        (
            "unpin-image-tag",
            "deploy.yaml",
            "    image: nginx:1.27.1\n",
            "    image: nginx:latest\n",
            (1, 1),
            ("latest",),
        ),
        (
            "unpin-image-tag",
            "Dockerfile",
            "FROM registry.local:5000/base:3.14-slim AS build\n",
            "FROM registry.local:5000/base:latest AS build\n",
            (1, 1),
            ("latest",),
        ),
        (
            "unpin-action-ref",
            "ci.yml",
            "      - uses: actions/checkout@v4\n",
            "      - uses: actions/checkout@main\n",
            (1, 1),
            ("checkout",),
        ),
        (
            "disable-tls-verify",
            "site.yaml",
            "    validate_certs: true\n",
            "    validate_certs: false\n",
            (1, 1),
            ("validate_certs",),
        ),
        (
            "disable-tls-verify",
            "http.py",
            "requests.get(url, verify=True)\n",
            "requests.get(url, verify=False)\n",
            (1, 1),
            ("verify",),
        ),
        (
            "log-secrets",
            "users.yaml",
            "  no_log: true\n",
            "  no_log: false\n",
            (1, 1),
            ("no_log",),
        ),
        (
            "widen-file-mode",
            "keys.yaml",
            '    mode: "0600"\n',
            '    mode: "0666"\n',
            (1, 1),
            ("0666", "666"),
        ),
        (
            "widen-file-mode",
            "keys.py",
            "os.chmod(path, 0o700)\n",
            "os.chmod(path, 0o777)\n",
            (1, 1),
            ("0o777", "777"),
        ),
        (
            "weaken-pod-security",
            "pod.yaml",
            "  runAsNonRoot: true\n",
            "  runAsNonRoot: false\n",
            (1, 1),
            ("runAsNonRoot",),
        ),
    ],
)
def test_each_template_injects_its_defect_and_records_where_it_counts(
    template: str,
    filename: str,
    text: str,
    expected: str,
    region: tuple[int, int],
    evidence: tuple[str, ...],
) -> None:
    """Verify each template's mutation, where a report counts, what it would name, and parsing."""
    mutated, recorded, named = _inject(template, filename, text)
    if filename.endswith(".py"):
        ast.parse(mutated)

    assert (mutated, recorded, named) == (expected, region, evidence)


@pytest.mark.parametrize(
    ("template", "filename", "text"),
    [
        (
            "drop-bounds-check",
            "only.py",
            "def check(n):\n    if n > 3:\n        raise ValueError(n)\n",
        ),
        ("drop-bounds-check", "branch.py", "if n > 3:\n    raise ValueError(n)\nelse:\n    pass\n"),
        ("drop-await", "sync.py", "def run(x):\n    return x\n"),
        ("unpin-image-tag", "latest.yaml", "image: nginx:latest\n"),
        ("unpin-image-tag", "templated.yaml", 'image: "{{ app_image }}"\n'),
        ("unpin-image-tag", "untagged.yaml", "image: nginx\n"),
        ("widen-file-mode", "open.yaml", "mode: '0644'\n"),
    ],
)
def test_templates_skip_places_without_the_defect_to_inject(
    template: str, filename: str, text: str
) -> None:
    """Verify no site where removal breaks the code, or where the protection is already absent."""
    (chosen,) = select_templates([template])

    find = chosen.finder_for(filename)

    assert find is not None and find(text.splitlines(keepends=True)) == []


def test_unknown_templates_are_rejected_by_name() -> None:
    """Verify an unknown template name is an error listing the known ones."""
    with pytest.raises(ValueError, match="no-such-template"):
        select_templates(["no-such-template"])


def _source_tree(root: Path) -> Path:
    source = root / "src"
    (source / "roles").mkdir(parents=True)
    (source / "site.yaml").write_text(
        "- hosts: all\n  tasks:\n    - uri:\n        url: https://example.com\n"
        "        validate_certs: true\n",
        encoding="utf-8",
    )
    (source / "roles" / "client.py").write_text(AWAIT, encoding="utf-8")
    (source / "README.txt").write_text("nothing to inject\n", encoding="utf-8")
    return source


def _sources(source: Path) -> list[tuple[Path, str]]:
    return [(p, p.relative_to(source).as_posix()) for p in sorted(source.rglob("*")) if p.is_file()]


def test_generation_is_seeded_and_keeps_the_answers_outside_the_reviewed_tree(
    tmp_path: Path,
) -> None:
    """Verify a seed reproduces the corpus, and only mutated files sit under the reviewed tree."""
    source = _source_tree(tmp_path)
    first = generate_corpus(_sources(source), tmp_path / "a", sources=[str(source)], seed=7)
    second = generate_corpus(_sources(source), tmp_path / "b", sources=[str(source)], seed=7)
    files = tmp_path / "a" / CORPUS_FILES_DIR
    mutated = {
        i.file: (files / i.file).read_text(encoding="utf-8").splitlines()[i.line - 1]
        for i in first.injections
    }

    assert (
        [(i.file, i.template) for i in first.injections],
        first.injections == second.injections,
        sorted(p.relative_to(files).as_posix() for p in files.rglob("*") if p.is_file()),
        {i.file: i.mutated for i in first.injections} == mutated,
        (tmp_path / "a" / CORPUS_MANIFEST).exists(),
        (tmp_path / "a" / CORPUS_CONVENTIONS_FILE).exists()
        and (tmp_path / "a" / ".devops" / "review.md").exists(),
    ) == (
        [("roles/client.py", "drop-await"), ("site.yaml", "disable-tls-verify")],
        True,
        ["roles/client.py", "site.yaml"],
        True,
        True,
        True,
    )


def _injection(
    file: str, line: int, region: tuple[int, int], template: str, evidence: list[str]
) -> Injection:
    return Injection(
        id=f"{file}:{line}:{template}",
        template=template,
        file=file,
        line=line,
        region_start=region[0],
        region_end=region[1],
        original="",
        mutated="",
        description="",
        severity="HIGH",
        evidence=evidence,
    )


def _finding(
    location: str, *, status: str = "VERIFIED", reportable: bool = True, text: str = "d"
) -> SavedFinding:
    return SavedFinding(
        location=location, title="t", description=text, status=status, reportable=reportable
    )


def test_score_matches_by_line_or_evidence_and_separates_what_verification_kept() -> None:
    """Verify matching by region or named evidence, the file boundary, and what was dropped."""
    corpus = DefectCorpus(
        sources=["src"],
        seed=1,
        created_at="2026-09-24T00:00:00+00:00",
        injections=[
            _injection("site.yaml", 5, (5, 5), "disable-tls-verify", ["validate_certs"]),
            _injection("roles/db.yaml", 10, (10, 10), "log-secrets", ["no_log"]),
            _injection("app.py", 20, (18, 22), "drop-bounds-check", ["batch_size"]),
            _injection("keys.py", 40, (40, 40), "widen-file-mode", ["0o777", "777"]),
        ],
    )
    at_line = _finding(".data/reviews/corpora/src-1/files/site.yaml:4-6")
    by_name = _finding("app.py:50", text="A zero batch_size loops forever.")
    by_mode = _finding("keys.py:3", text="The directory is created world-writable (777).")
    other = _finding("other.yaml:3")
    wrong_file = _finding("xsite.yaml:5", text="validate_certs is off.")
    dropped = _finding("roles/db.yaml:11", status="INVALIDATED", reportable=False)
    reported = [at_line, by_name, by_mode, other, wrong_file]

    score = score_corpus(corpus, [*reported, dropped], reported, session_id="s1")

    assert (
        (score.found, score.found_by_line, score.reported, score.dropped, score.in_file),
        (score.unmatched_findings, score.recall_found, score.recall_reported),
        [(o.matched_by, o.statuses, o.titles) for o in score.outcomes],
    ) == (
        (4, 2, 3, 1, 4),
        (2, 1.0, 0.75),
        [
            (["line"], ["VERIFIED"], ["t"]),
            (["line"], ["INVALIDATED"], ["t"]),
            (["content"], ["VERIFIED"], ["t"]),
            (["content"], ["VERIFIED"], ["t"]),
        ],
    )


def _session(reviews: Path, name: str, target: Path, findings: list[SavedFinding]) -> None:
    session = reviews / name
    session.mkdir(parents=True)
    (session / "findings.json").write_text(
        ReviewSessionPayload(findings=findings).model_dump_json(), encoding="utf-8"
    )
    ReviewProfile(session_id=name, target=str(target.resolve())).write(session)


def test_corpus_commands_generate_then_score_the_latest_review_of_that_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify generate writes a corpus, and score reads the latest session that reviewed it."""
    reviews = tmp_path / "reviews"
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)
    source = _source_tree(tmp_path)

    generated = cli.invoke(app, ["review", "corpus", "generate", str(source), "--seed", "7"])
    corpus_dir = reviews / "corpora" / "src-7"
    corpus = DefectCorpus.load(corpus_dir)
    hit = next(i for i in corpus.injections if i.file == "src/site.yaml")
    _session(
        reviews,
        "20260924-100000",
        corpus_dir / CORPUS_FILES_DIR,
        [_finding(f"src/site.yaml:{hit.line}")],
    )
    _session(reviews, "20260924-110000", source, [])

    scored = cli.invoke(app, ["review", "corpus", "score", str(corpus_dir), "--json"])
    score = json.loads(scored.stdout)
    again = cli.invoke(app, ["review", "corpus", "generate", str(source), "--seed", "7"])

    assert (
        generated.exit_code,
        (scored.exit_code, score["session_id"], score["reported"], score["injections"]),
        again.exit_code,
    ) == (0, (0, "20260924-100000", 1, 2), 1)


def test_a_corpus_score_is_kept_with_each_injections_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a score is kept in the run store, its subject the corpus's injections, so scores
    of the same corpus under different setups can be compared (#554)."""
    from devops_cli.ai.run_store import Mechanism, load_runs

    reviews = tmp_path / "reviews"
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)
    source = _source_tree(tmp_path)
    corpus_dir = tmp_path / "corpus"
    generate_corpus(_sources(source), corpus_dir, sources=[str(source)], seed=1)
    _session(reviews, "20260924-100000", corpus_dir / CORPUS_FILES_DIR, [])

    first = cli.invoke(app, ["review", "corpus", "score", str(corpus_dir)])
    second = cli.invoke(app, ["review", "corpus", "score", str(corpus_dir)])
    runs = load_runs(Mechanism.CORPUS_SCORE)

    assert (
        (first.exit_code, second.exit_code),
        len({r.subject_key for r in runs}),
        [len(r.results["outcomes"]) for r in runs],
    ) == ((0, 0), 1, [2, 2])


def test_score_without_a_review_of_the_corpus_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify scoring refuses a session that did not review the corpus, rather than guessing."""
    reviews = tmp_path / "reviews"
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)
    source = _source_tree(tmp_path)
    corpus_dir = tmp_path / "corpus"
    generate_corpus(_sources(source), corpus_dir, sources=[str(source)], seed=1)
    _session(reviews, "20260924-110000", source, [])

    result = cli.invoke(app, ["review", "corpus", "score", str(corpus_dir)])

    assert result.exit_code == 1
