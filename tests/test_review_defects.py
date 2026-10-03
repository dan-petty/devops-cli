"""Synthetic defect corpora: injected defects at recorded locations, and review recall against them."""

from __future__ import annotations

import ast
import contextlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai import run_store
from devops_cli.ai.review import runner
from devops_cli.ai.review.defects import (
    CORPUS_FILES_DIR,
    CORPUS_MANIFEST,
    CorpusScore,
    DefectCorpus,
    Injection,
    generate_corpus,
    score_corpus,
    score_corpus_runs,
    select_templates,
)
from devops_cli.ai.review.profile import ReviewProfile
from devops_cli.ai.review.review_environment import (
    nearest_conventions,
    nearest_review_conventions,
)
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.ai.run_store import Mechanism, load_runs
from devops_cli.commands import review as review_commands
from devops_cli.exceptions.validation import ValidationError
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
        sorted(p.name for p in (tmp_path / "a").iterdir()),
    ) == (
        [("roles/client.py", "drop-await"), ("site.yaml", "disable-tls-verify")],
        True,
        ["roles/client.py", "site.yaml"],
        True,
        [CORPUS_FILES_DIR, CORPUS_MANIFEST],
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


def _arm_run(corpus: DefectCorpus, session_id: str, found: str, reported: str) -> CorpusScore:
    """A session whose review found the injections in the named files, and kept those reported."""
    candidates = [_finding(f"{name}.py:1") for name in found]
    kept = [finding for name, finding in zip(found, candidates, strict=True) if name in reported]
    return score_corpus(corpus, candidates, kept, session_id=session_id)


def test_an_arm_counts_the_runs_that_found_and_reported_each_injection() -> None:
    """Verify pass@k and pass^k over 3 runs, and each figure's mean beside its range (#413)."""
    corpus = DefectCorpus(
        sources=["src"],
        seed=1,
        created_at="2026-10-02T00:00:00+00:00",
        injections=[_injection(f"{name}.py", 1, (1, 1), "drop-await", []) for name in "abcd"],
    )
    runs = [
        _arm_run(corpus, "s1", found="abc", reported="a"),
        _arm_run(corpus, "s2", found="ab", reported="a"),
        _arm_run(corpus, "s3", found="a", reported=""),
    ]

    arm = score_corpus_runs(runs, [None, None, None])
    spread = arm.spread or {}

    assert (
        [(t.found_in, t.reported_in) for t in arm.tallies],
        (arm.found.pass_at_k, arm.found.pass_hat_k, arm.found.in_none),
        (arm.reported.pass_at_k, arm.reported.pass_hat_k, arm.reported.in_none),
        (arm.recall_found, spread["recall_found"]),
        (arm.recall_reported, spread["recall_reported"]),
        (arm.runs, [row.session_id for row in arm.sessions], arm.scores == runs),
    ) == (
        [(3, 2), (2, 0), (1, 0), (0, 0)],
        (0.75, 0.25, 1),
        (0.25, 0.0, 3),
        (0.5, (0.25, 0.75)),
        (0.167, (0.0, 0.25)),
        (3, ["s1", "s2", "s3"], True),
    )


def _matching_fixture() -> tuple[DefectCorpus, list[SavedFinding], list[SavedFinding]]:
    """The corpus and findings of the single-session matching test: candidates, then reported."""
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
    reported = [
        _finding(".data/reviews/corpora/src-1/files/site.yaml:4-6"),
        _finding("app.py:50", text="A zero batch_size loops forever."),
        _finding("keys.py:3", text="The directory is created world-writable (777)."),
        _finding("other.yaml:3"),
        _finding("xsite.yaml:5", text="validate_certs is off."),
    ]
    dropped = _finding("roles/db.yaml:11", status="INVALIDATED", reportable=False)
    return corpus, [*reported, dropped], reported


def test_an_arm_of_one_run_reproduces_that_sessions_totals() -> None:
    """Verify one session scored as an arm keeps its score, its recall as pass@1 and pass^1, its
    finding counts, and claims no spread (#413)."""
    corpus, candidates, reported = _matching_fixture()
    score = score_corpus(corpus, candidates, reported, session_id="s1")

    arm = score_corpus_runs([score], [None])

    assert (
        arm.scores[0] == score,
        (arm.found.pass_at_k, arm.found.pass_hat_k, score.recall_found),
        (arm.reported.pass_at_k, arm.reported.pass_hat_k),
        (score.candidate_findings, score.invalidated_findings, score.reported_findings),
        (arm.candidate_findings, arm.invalidated_findings, arm.reported_findings),
        arm.spread,
    ) == (True, (1.0, 1.0, 1.0), (0.75, 0.75), (6, 1, 5), (6, 1, 5), None)


def test_an_arm_refuses_sessions_that_ran_different_prompts() -> None:
    """Verify sessions with different prompt digests, or none, are not scored as an arm (#413)."""
    corpus, candidates, reported = _matching_fixture()
    scores = [score_corpus(corpus, candidates, reported, session_id=s) for s in ("s1", "s2")]
    profiles = [ReviewProfile(session_id=s, target="t", prompt_digest=s * 4) for s in ("s1", "s2")]

    with pytest.raises(ValidationError, match="s1 s1s1s1s1, s2 s2s2s2s2"):
        score_corpus_runs(scores, profiles)
    with pytest.raises(ValidationError, match="got 0 score"):
        score_corpus_runs([], [])


def _session(
    reviews: Path, name: str, target: Path, findings: list[SavedFinding], **profile: Any
) -> None:
    session = reviews / name
    session.mkdir(parents=True)
    (session / "findings.json").write_text(
        ReviewSessionPayload(findings=findings).model_dump_json(), encoding="utf-8"
    )
    ReviewProfile(session_id=name, target=str(target.resolve()), **profile).write(session)


def _repository_with_conventions(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    (root / ".devops").mkdir()
    (root / "AGENTS.md").write_text("Repository conventions.\n", encoding="utf-8")
    (root / ".devops" / "review.md").write_text("Repository review rules.\n", encoding="utf-8")
    return root


def test_a_corpus_inside_a_repository_reads_none_of_its_conventions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the conventions lookup stops at the corpus root its manifest marks (#946).

    A corpus is written under the reviews directory of the checkout that made it, and its
    review climbed to that checkout's `AGENTS.md` and `.devops/review.md`, so every arm of a
    benchmark was scored under conventions it did not choose. A source with none gives a
    corpus with none; one with its own gives the corpus a copy.
    """
    repo = _repository_with_conventions(tmp_path / "repo")
    reviews = repo / ".data" / "reviews"
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)
    source = _source_tree(tmp_path)

    generated = cli.invoke(review_commands.corpus_app, ["generate", str(source), "--seed", "7"])
    files = reviews / "corpora" / "src-7" / CORPUS_FILES_DIR
    copied = generate_corpus(
        _sources(source),
        repo / "copied",
        sources=[str(source)],
        seed=7,
        conventions="Source conventions.\n",
        review_conventions="Source review rules.\n",
    )

    assert (
        generated.exit_code,
        (nearest_conventions(files / "src"), nearest_review_conventions(files / "src")),
        (nearest_conventions(reviews), nearest_review_conventions(reviews)),
        bool(copied.injections),
        (
            nearest_conventions(repo / "copied" / CORPUS_FILES_DIR),
            nearest_review_conventions(repo / "copied" / CORPUS_FILES_DIR),
        ),
    ) == (
        0,
        ("", ""),
        ("Repository conventions.\n", "Repository review rules."),
        True,
        ("Source conventions.\n", "Source review rules."),
    )


def test_a_manifest_that_is_not_a_corpus_stops_no_conventions_lookup(tmp_path: Path) -> None:
    """Verify only a corpus's manifest ends the walk: a web app's `manifest.json` is not one."""
    repo = _repository_with_conventions(tmp_path / "repo")
    (repo / "public").mkdir()
    (repo / "public" / CORPUS_MANIFEST).write_text('{"name": "app"}', encoding="utf-8")

    assert nearest_review_conventions(repo / "public") == "Repository review rules."


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_manifest_that_is_no_regular_file_is_never_opened(tmp_path: Path) -> None:
    """Verify the walk does not open a FIFO named `manifest.json` (#946).

    Opening one waits for a writer, so the conventions lookup hung, and a link to `/dev/zero`
    read until memory ran out. A regression is given a writer after a second, so it fails
    instead of hanging the suite.
    """
    repo = _repository_with_conventions(tmp_path / "repo")
    (repo / "src").mkdir()
    fifo = repo / "src" / CORPUS_MANIFEST
    os.mkfifo(fifo)
    opened = threading.Event()

    def give_it_a_writer() -> None:
        with contextlib.suppress(OSError):  # ENXIO: nothing is waiting to read it
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            opened.set()

    watchdog = threading.Timer(1.0, give_it_a_writer)
    watchdog.start()
    try:
        conventions = nearest_conventions(repo / "src")
    finally:
        watchdog.cancel()

    assert (conventions, opened.is_set()) == ("Repository conventions.\n", False)


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
        (
            scored.exit_code,
            score["scores"][0]["session_id"],
            score["scores"][0]["reported"],
            score["scores"][0]["injections"],
        ),
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
        [len(r.results["scores"][0]["outcomes"]) for r in runs],
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


# The corpus group's own app parses `devops review corpus score` as the full CLI does; the tests
# above drive it through `devops`, and these through it, which builds two commands, not all.
def _reviewed_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A corpus and the reviews directory its sessions are written to."""
    reviews = tmp_path / "reviews"
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: reviews)
    # A kept run is stamped with the checkout's commit, which runs git three times; not tested here.
    monkeypatch.setattr(run_store, "source_commit", lambda: None)
    source = _source_tree(tmp_path)
    corpus_dir = tmp_path / "corpus"
    generate_corpus(_sources(source), corpus_dir, sources=[str(source)], seed=1)
    _session(reviews, "20260924-090000", source, [], prompt_digest="d1")
    return corpus_dir, reviews


def _profiled(tokens: int, digest: str = "d1") -> dict[str, Any]:
    """Profile fields of a session: its tokens, one parsed and one unparsed persona reply."""
    return {
        "prompt_digest": digest,
        "prompt_tokens": tokens,
        "completion_tokens": tokens // 10,
        "persona_outcomes": {"findings": 1, "unparsed": 1},
        "persona_replies": [
            {"persona": "devsecops", "outcome": "findings"},
            {"persona": "qa", "outcome": "unparsed"},
        ],
    }


@pytest.fixture
def three_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A corpus with three reviews written newest first, and one review of another target."""
    corpus_dir, reviews = _reviewed_corpus(tmp_path, monkeypatch)
    for name, tokens in (
        ("20260924-120000", 300),
        ("20260924-100000", 100),
        ("20260924-110000", 200),
    ):
        _session(reviews, name, corpus_dir / CORPUS_FILES_DIR, [], **_profiled(tokens))
    return corpus_dir


def test_corpus_score_scores_the_latest_runs_oldest_first_as_one_arm(three_runs: Path) -> None:
    """Verify --runs takes the corpus's reviews oldest first, each with its tokens and unparsed
    replies, and records the personas that replied in its setup (#413)."""
    result = cli.invoke(
        review_commands.corpus_app, ["score", str(three_runs), "--runs", "3", "--json"]
    )
    arm = json.loads(result.stdout)
    (record,) = load_runs(Mechanism.CORPUS_SCORE)

    assert (
        (result.exit_code, arm["runs"], arm["prompt_digest"]),
        [
            (r["session_id"], r["prompt_tokens"], r["completion_tokens"], r["unparsed_replies"])
            for r in arm["sessions"]
        ],
        (record.setup["personas"], record.setup["runs"], record.setup["prompt_digest"]),
    ) == (
        (0, 3, "d1"),
        [
            ("20260924-100000", 100, 10, 1),
            ("20260924-110000", 200, 20, 1),
            ("20260924-120000", 300, 30, 1),
        ],
        (["devsecops", "qa"], 3, "d1"),
    )


def test_corpus_score_scores_exactly_the_named_sessions(three_runs: Path) -> None:
    """Verify a repeated --session scores those sessions and no others (#413)."""
    args = ["-s", "20260924-120000", "-s", "20260924-100000", "--json"]

    result = cli.invoke(review_commands.corpus_app, ["score", str(three_runs), *args])

    assert (result.exit_code, [r["session_id"] for r in json.loads(result.stdout)["sessions"]]) == (
        0,
        ["20260924-100000", "20260924-120000"],
    )


def test_corpus_score_refuses_more_runs_than_exist_and_says_how_many_do(three_runs: Path) -> None:
    """Verify --runs beyond the reviews of the corpus exits 1, names how many exist and records
    no run (#413)."""
    result = cli.invoke(review_commands.corpus_app, ["score", str(three_runs), "--runs", "4"])

    assert (
        result.exit_code,
        "Only 3 review(s)" in result.output,
        load_runs(Mechanism.CORPUS_SCORE),
    ) == (1, True, [])


def test_corpus_score_refuses_session_beside_runs(three_runs: Path) -> None:
    """Verify naming sessions and asking for the latest runs at once exits 1 (#413)."""
    args = ["-s", "20260924-100000", "--runs", "2"]

    result = cli.invoke(review_commands.corpus_app, ["score", str(three_runs), *args])

    assert (result.exit_code, load_runs(Mechanism.CORPUS_SCORE)) == (1, [])


def test_corpus_score_refuses_runs_of_different_prompts_and_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify two runs with different prompt digests are refused, each digest named (#413)."""
    corpus_dir, reviews = _reviewed_corpus(tmp_path, monkeypatch)
    files = corpus_dir / CORPUS_FILES_DIR
    _session(reviews, "20260924-100000", files, [], **_profiled(100, "a1b2c3d4e5f60718"))
    _session(reviews, "20260924-110000", files, [], **_profiled(100, "8f7e6d5c4b3a2910"))

    result = cli.invoke(review_commands.corpus_app, ["score", str(corpus_dir), "--runs", "2"])

    assert (
        result.exit_code,
        "a1b2c3d4e5f60718" in result.output and "8f7e6d5c4b3a2910" in result.output,
        load_runs(Mechanism.CORPUS_SCORE),
    ) == (1, True, [])


def test_corpus_score_warns_when_a_gateway_group_serves_several_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the report says a run is not model-pinned, and still records it (#413)."""
    corpus_dir, reviews = _reviewed_corpus(tmp_path, monkeypatch)
    _session(reviews, "20260924-100000", corpus_dir / CORPUS_FILES_DIR, [], **_profiled(100))
    pool = [
        {"backend": "backend-a", "model": "ollama_chat/qwen3-coder:30b", "weight": 1},
        {"backend": "backend-b", "model": "ollama_chat/gpt-oss:20b", "weight": 1},
    ]
    monkeypatch.setattr(
        review_commands, "review_setup", lambda **extra: {"pools": {"devops-review": pool}} | extra
    )

    result = cli.invoke(review_commands.corpus_app, ["score", str(corpus_dir)])

    assert (
        result.exit_code,
        "not model-pinned: devops-review serves 2 models" in result.output,
        "found in 0/1" in result.output and "Synthetic recall measures regression" in result.output,
        len(load_runs(Mechanism.CORPUS_SCORE)),
    ) == (0, True, True, 1)
