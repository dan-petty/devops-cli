"""`devops review intake`: the findings of a session on merged code go to roadmap intake (#2420).

A finding qualifies when admission gave it a fingerprint v2 and no verdict invalidated or
mitigated it. The command refuses a session that is not on merged code, leaves out a finding that
an issue already carries, and hands each other one to intake as one candidate that carries the
finding's marker. Git runs for real in temporary repositories; GitHub, the roadmap store and the
model are faked at their edges.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import pytest

from devops_cli.ai.review_schema import (
    CitedCode,
    ReviewCheckout,
    ReviewSessionPayload,
    SavedFinding,
    VerificationCriterion,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.security import SecurityError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.lang import MESSAGES
from devops_cli.review.checkout import why_not_on_merged_code
from devops_cli.review.filed_findings import finding_marker
from devops_cli.review.handoff import (
    finding_candidate,
    intake_hint,
    prepare_hand_off,
    qualifying_findings,
    run_hand_off,
)
from devops_cli.review.session import ReviewSessionStore
from devops_cli.roadmap.intake import Filer, Outcome
from devops_cli.roadmap.intake_model import GatewayIntakeModel
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.builders import make_finding
from tests.support.fakes.github import API, github_json, quota_headers
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake

_REPO = "octo/repo"
_SESSION = "20261028-120000"
_A, _B, _C, _D, _E = (letter * 64 for letter in "abcde")
_PROPOSAL: dict[str, Any] = {
    "type": "type/bug",
    "type_reason": "the code is wrong.",
    "priority": "P2-Medium",
    "priority_reason": "it is not urgent.",
    "value": "Medium",
    "value_reason": "it removes a defect.",
    "effort": "Low",
    "effort_reason": "one line.",
}


def _head(repo: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _repository(root: Path, git: Callable[..., None]) -> Path:
    """A checkout with one commit on `main`, which `origin/main` also names."""
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    return root


def _finding(fingerprint: str, *, status: str = "VERIFIED", line: int = 1) -> SavedFinding:
    """A ruff finding as admission saves it: its fingerprint v2 and its tool as producer."""
    return make_finding(
        saved=True,
        severity="MEDIUM",
        location=f"src/app.py:{line}",
        title=f"[ruff] S{line}: finding {fingerprint[0]}",
        description=f"Rule S{line} matched.",
        fix="Change the call.",
        status=status,
        fingerprint=fingerprint,
        producer="ruff",
    )


def _payload(
    findings: list[SavedFinding],
    *,
    subject_type: str = "path",
    checkout: ReviewCheckout | None = None,
) -> ReviewSessionPayload:
    return ReviewSessionPayload(
        subject={"type": subject_type, "ref": "src"}, checkout=checkout, findings=findings
    )


def _write_session(store: type[ReviewSessionStore], payload: ReviewSessionPayload) -> Path:
    """Publish the session `_SESSION` with `payload` as its findings.json."""
    directory = store.root() / _SESSION
    directory.mkdir(parents=True)
    (directory / "findings.json").write_text(payload.model_dump_json(), encoding="utf-8")
    return directory


def _search_path() -> str:
    query = f'"devops-review-finding" in:body is:issue repo:{_REPO}'
    return f"/search/issues?{urlencode({'q': query, 'per_page': 100, 'page': 1})}"


def _route_search(api: GitHubApiFake, *carried: str) -> None:
    """Answer the issue search with one open issue for each fingerprint in `carried`."""
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    items = [
        {"number": n, "state": "open", "state_reason": None, "body": finding_marker(fp)}
        for n, fp in enumerate(carried, start=1)
    ]
    payload = {"total_count": len(items), "incomplete_results": False, "items": items}
    api.route(
        "GET",
        _search_path(),
        github_json(payload, headers=quota_headers(29, resource="search", limit=30)),
    )


def _roadmap() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore()
    store.seed_file(
        ".github/labels.yml", (REPO_ROOT / ".github/labels.yml").read_text(encoding="utf-8")
    )
    return store


def _model(model_fake: ModelFake) -> GatewayIntakeModel:
    """Intake's model over the model fake: its chat client and its embedder."""
    model_fake.answer(json.dumps(_PROPOSAL))
    return GatewayIntakeModel(AIConfig(), embedder=model_fake)


def test_a_session_that_is_not_on_merged_code_says_why(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify each kind of session gives its reason, and a session on merged code gives none."""
    root = _repository(tmp_path / "project", git)
    on_main = _head(root)
    git(root, "commit", "-q", "--allow-empty", "-m", "topic")
    topic = _head(root)
    clean, dirty = (
        ReviewCheckout(head=on_main, clean=True),
        ReviewCheckout(head=on_main, clean=False),
    )
    texts = MESSAGES.review

    unrecorded = ReviewSessionPayload(checkout=clean)

    reasons = [
        why_not_on_merged_code(unrecorded, root),
        why_not_on_merged_code(_payload([], subject_type="pr", checkout=clean), root),
        why_not_on_merged_code(_payload([]), root),
        why_not_on_merged_code(_payload([], checkout=dirty), root),
        why_not_on_merged_code(_payload([], checkout=ReviewCheckout(head=topic, clean=True)), root),
        why_not_on_merged_code(_payload([], checkout=clean), root),
    ]

    assert reasons == [
        texts.merged_reason_no_subject,
        texts.merged_reason_target.format(type="pr"),
        texts.merged_reason_no_checkout,
        texts.merged_reason_dirty,
        texts.merged_reason_not_on_main.format(head=topic),
        None,
    ]


def test_review_path_names_the_hand_off_only_for_a_clean_session_with_qualifying_findings() -> None:
    """Verify the line counts the qualifying findings of a clean session and names the command."""
    head = "1" * 40
    findings = [_finding(_A), _finding(_B, line=2), _finding(_C, status="INVALIDATED", line=3)]
    clean = _payload(findings, checkout=ReviewCheckout(head=head, clean=True))
    dirty = _payload(findings, checkout=ReviewCheckout(head=head, clean=False))
    none_left = _payload(findings[2:], checkout=ReviewCheckout(head=head, clean=True))

    assert [intake_hint(p, _SESSION) for p in (clean, dirty, none_left)] == [
        MESSAGES.review.hand_off_hint.format(count=2, session=_SESSION),
        None,
        None,
    ]


def test_the_hand_off_takes_the_open_tool_findings_of_a_session() -> None:
    """Verify a finding qualifies with a fingerprint v2 and a verdict that keeps it."""
    payload = _payload(
        [
            _finding(_A, status="VERIFIED", line=1),
            _finding(_B, status="UNVERIFIED", line=2),
            _finding(_C, status="INVALIDATED", line=3),
            _finding(_D, status="MITIGATED", line=4),
            _finding("osv:requests:GHSA-1", status="VERIFIED", line=5),
        ]
    )

    assert [f.fingerprint for f in qualifying_findings(payload)] == [_A, _B]


def test_the_candidate_of_a_finding_cites_it_and_carries_its_marker() -> None:
    """Verify the title names the finding and its place, and the body ends with its marker."""
    finding = _finding(_A, line=3).model_copy(
        update={
            "cited_code": CitedCode(
                project="project", file="src/app.py", line=3, excerpt="subprocess.run(cmd)"
            ),
            "verification_criteria": [VerificationCriterion(description="The call is gone.")],
        }
    )

    candidate = finding_candidate(finding, _SESSION)

    body = candidate.body
    cited = ("subprocess.run(cmd)", "The call is gone.", finding.description, finding.fix)
    assert (
        candidate.title,
        candidate.filed_by,
        [part in body for part in (_SESSION, "src/app.py:3", "ruff", "MEDIUM", "VERIFIED")],
        [part in body for part in cited],
        body.splitlines()[-1],
    ) == (
        "fix: [ruff] S3: finding a (src/app.py:3)",
        Filer.AGENT,
        [True] * 5,
        [True] * 4,
        finding_marker(_A),
    )


@pytest.mark.parametrize("confirm", [True, False], ids=["confirm", "plan"])
def test_the_hand_off_sends_intake_only_the_finding_no_issue_carries(
    tmp_path: Path,
    git: Callable[..., None],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    confirm: bool,
) -> None:
    """Verify an open issue keeps finding A out, and B goes to intake: filed with its marker on
    confirm, and only decided on a plan."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=True)
    session = _write_session(
        review_store, _payload([_finding(_A), _finding(_B, line=2)], checkout=checkout)
    )
    _route_search(github_api, _A)
    store = _roadmap()

    plan = prepare_hand_off(session, root, repo=_REPO, dry_run=False)
    report = run_hand_off(plan, repo=_REPO, store=store, model=_model(model_fake), confirm=confirm)

    filed = [issue for issue in store.issues() if issue.title.startswith("fix: ")]
    assert (
        plan.settled,
        [outcome.decision.outcome for outcome in report.outcomes],
        [outcome.decision.subject.title for outcome in report.outcomes],
        report.filed == tuple(issue.number for issue in filed),
        [issue.body.rstrip().splitlines()[-1] for issue in filed],
        "fix: [ruff] S2: finding b (src/app.py:2)" in report.text,
        (MESSAGES.review.hand_off_plan_note in report.render(confirm=confirm)) is not confirm,
        report.skipped,
        model_fake.call_count,
    ) == (
        1,
        [Outcome.PLACE],
        ["fix: [ruff] S2: finding b (src/app.py:2)"],
        True,
        [finding_marker(_B)] if confirm else [],
        True,
        True,
        0,
        1,
    )


def test_a_candidate_that_looks_like_it_holds_a_secret_is_refused_before_any_request(
    tmp_path: Path,
    git: Callable[..., None],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
) -> None:
    """Verify a finding whose text looks like a token stops the hand-off and names the finding."""
    root = _repository(tmp_path / "project", git)
    leaky = _finding(_A, line=7).model_copy(
        update={"description": "It fails with token=ghp_abcdefghijklmnop1234"}
    )
    checkout = ReviewCheckout(head=_head(root), clean=True)
    session = _write_session(review_store, _payload([leaky], checkout=checkout))

    with pytest.raises(SecurityError) as raised:
        prepare_hand_off(session, root, repo=_REPO, dry_run=False)

    assert ("src/app.py:7" in raised.value.message, github_api.requested) == (True, [])


def test_a_session_that_is_not_on_merged_code_is_refused_before_any_request(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `devops review intake` exits 1 for a dirty tree, says so, and sends nothing."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=False)
    _write_session(review_store, _payload([_finding(_A)], checkout=checkout))
    monkeypatch.chdir(root)

    result = cli("review", "intake", _SESSION, "--repo", _REPO)

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        MESSAGES.review.merged_reason_dirty in output,
        github_api.requested,
    ) == (
        1,
        True,
        [],
    )


def test_a_dry_run_of_the_hand_off_makes_no_request(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the dry run lists both candidates, the issue search and intake's model call."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=True)
    _write_session(review_store, _payload([_finding(_A), _finding(_B, line=2)], checkout=checkout))
    monkeypatch.chdir(root)

    result = cli("review", "intake", _SESSION, "--repo", _REPO, "--dry-run")

    output = result.output
    assert (
        result.exit_code,
        "fix: [ruff] S1: finding a (src/app.py:1)" in output,
        "fix: [ruff] S2: finding b (src/app.py:2)" in output,
        f"{API}/search/issues?" in output,
        "model the proposal for new candidate" in output,
        github_api.requested,
        model_fake.call_count,
    ) == (0, True, True, True, True, [], 0)


def test_a_plan_whose_findings_issues_already_carry_hands_off_nothing(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a plan whose qualifying findings are all filed calls no model and exits 0."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=True)
    _write_session(review_store, _payload([_finding(_A), _finding(_B, line=2)], checkout=checkout))
    _route_search(github_api, _A, _B)
    monkeypatch.chdir(root)

    result = cli("review", "intake", _SESSION, "--repo", _REPO, "--plan")

    output = " ".join(result.output.split())
    expected = MESSAGES.review.hand_off_all_filed.format(count=2, session=_SESSION)
    assert (result.exit_code, expected in output, model_fake.call_count) == (0, True, 0)


def test_more_than_one_mode_flag_is_refused(cli: Callable[..., Any]) -> None:
    """Verify `--plan` and `--confirm` together are refused before the session is read."""
    result = cli("review", "intake", "--plan", "--confirm")

    assert (result.exit_code, "--plan" in result.output and "--confirm" in result.output) == (
        1,
        True,
    )


def test_review_path_names_no_hand_off_for_a_session_with_no_qualifying_finding(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a path review that keeps a session with no finding prints no hand-off line."""
    root = _repository(tmp_path / "project", git)
    monkeypatch.chdir(root)

    result = cli("review", "path", str(root / "src"), "--reporting-only")

    assert (result.exit_code, "devops review intake" in result.output) == (0, False)


def test_a_session_with_no_qualifying_finding_hands_off_nothing(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a session whose one finding a verdict invalidated reads no issue and exits 0."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=True)
    _write_session(review_store, _payload([_finding(_A, status="INVALIDATED")], checkout=checkout))
    monkeypatch.chdir(root)

    result = cli("review", "intake", _SESSION, "--repo", _REPO)

    output = " ".join(result.output.split())
    expected = MESSAGES.review.hand_off_none.format(session=_SESSION)
    assert (result.exit_code, expected in output, github_api.requested) == (0, True, [])


@pytest.mark.parametrize("place", ["outside", "no-origin"])
def test_the_hand_off_needs_a_checkout_and_its_repository(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    monkeypatch: pytest.MonkeyPatch,
    place: str,
) -> None:
    """Verify the command exits 1 outside any checkout, and in a checkout with no origin and no
    `--repo`, and says what to do."""
    root = _repository(tmp_path / "project", git)
    checkout = ReviewCheckout(head=_head(root), clean=True)
    _write_session(review_store, _payload([_finding(_A)], checkout=checkout))
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.chdir(outside if place == "outside" else root)

    result = cli("review", "intake", _SESSION)

    texts = MESSAGES.review
    expected = texts.hand_off_no_checkout if place == "outside" else texts.hand_off_no_repo
    assert (result.exit_code, expected in " ".join(result.output.split())) == (1, True)
