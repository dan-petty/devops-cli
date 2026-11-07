"""The evidence that makes a candidate critical: who may cite it, and how intake checks it against
the text (#1335).
"""

from __future__ import annotations

from devops_cli.roadmap.intake.intake import (
    NewCandidate,
    intake_candidate,
)
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
)
from tests.support.roadmap_intake import REGRESSION, REPO, FakeModel, Roadmap


def test_a_collaborators_bug_citing_an_existing_regression_commit_is_a_p0_in_the_backlog(
    roadmap: Roadmap,
) -> None:
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"))
    real = roadmap.issue("fix: crash on start", "Introduced by abc1234.")
    cited = REGRESSION | {"evidence": {"kind": "regression_commit", "value": "def5678"}}
    missing = roadmap.issue("fix: crash on stop", "Introduced by def5678.")
    roadmap.run(
        FakeModel(proposals={"fix: crash on start": REGRESSION, "fix: crash on stop": cited})
    )
    (refused,) = roadmap.comments(missing)
    assert (
        roadmap.fields(real)[1::3],
        roadmap.fields(missing)[1::3],
        "def5678" in refused and "no such commit" in refused,
        "A person can set P0" in refused,
    ) == (("P0-Critical", None), ("P1-High", None), True, True)


def test_a_valid_citation_needs_a_trusted_author_and_must_be_in_the_candidates_text(
    roadmap: Roadmap,
) -> None:
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"))
    outsider = roadmap.issue("fix: outsider", "Introduced by abc1234.", author="NONE")
    invented = roadmap.issue("fix: invented", "It broke last week.")
    roadmap.run(FakeModel(proposals={"fix: outsider": REGRESSION, "fix: invented": REGRESSION}))
    comments = [roadmap.comments(outsider)[0], roadmap.comments(invented)[0]]
    assert (
        roadmap.fields(outsider)[1::3],
        roadmap.fields(invented)[1::3],
        ["A person can set P0" in comment for comment in comments],
        "no write access" in comments[0],
        "does not appear in the candidate's text" in comments[1],
    ) == (("P1-High", None), ("P1-High", None), [True, True], True, True)


def test_a_p0_feature_with_verified_evidence_lands_in_the_backlog_at_p0(roadmap: Roadmap) -> None:
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    number = roadmap.issue("feat: retry flaky uploads", "Run 4242 failed on upload.")
    proposal = {"evidence": {"kind": "failed_run", "value": "4242"}}
    roadmap.run(FakeModel(proposals={"feat: retry flaky uploads": proposal}))
    assert roadmap.fields(number)[1::3] == ("P0-Critical", None)


def test_evidence_the_entry_points_caller_attaches_is_trusted_and_the_source_is_kept(
    roadmap: Roadmap,
) -> None:
    """An agent's text earns no P0, but evidence its caller attached does, once GitHub confirms
    it; the source link ends the filed body."""
    commit = Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234")
    roadmap.store.seed_evidence(commit)
    model = FakeModel(proposals={"fix: attached": REGRESSION, "fix: claimed": REGRESSION})
    attached = intake_candidate(
        roadmap.store,
        NewCandidate(
            title="fix: attached",
            body="Crash on start.",
            source="https://example.test/review/1",
            evidence=(commit,),
        ),
        repo=REPO,
        model=model,
        confirm=True,
    )
    claimed = intake_candidate(
        roadmap.store,
        NewCandidate(title="fix: claimed", body="Introduced by abc1234."),
        repo=REPO,
        model=model,
        confirm=True,
    )
    body = next(i.body for i in roadmap.store.issues() if i.number == attached.number)
    assert (
        roadmap.fields(attached.number or 0)[1::3],
        roadmap.fields(claimed.number or 0)[1::3],
        body.endswith("Source: https://example.test/review/1"),
    ) == (("P0-Critical", None), ("P1-High", None), True)


def test_evidence_counts_as_a_whole_token_anywhere_in_the_text(roadmap: Roadmap) -> None:
    """A run id cut from a date is no citation; a commit cited past the embedded text, or in a
    link, is."""
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="20"))
    roadmap.store.seed_evidence(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"))
    inside = roadmap.issue("fix: date", "Seen on 2026-10-04.")
    late = roadmap.issue("fix: late", "context " * 800 + "Introduced by abc1234.")
    linked = roadmap.issue("fix: linked", "See https://github.com/o/r/commit/abc1234.")
    run = {"type": "type/bug", "evidence": {"kind": "failed_run", "value": "20"}}
    roadmap.run(
        FakeModel(proposals={"fix: date": run, "fix: late": REGRESSION, "fix: linked": REGRESSION})
    )
    assert (
        roadmap.fields(inside)[1],
        roadmap.fields(late)[1],
        roadmap.fields(linked)[1],
    ) == ("P2-Medium", "P0-Critical", "P0-Critical")
