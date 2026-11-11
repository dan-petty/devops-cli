"""`devops roadmap intake` through its command line: plan, confirm, the report and the exit status
(#1335).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.rag.embeddings import install_embedder
from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake import (
    render_intake,
)
from devops_cli.roadmap.intake.intake_model import (
    ProposalRequest,
)
from devops_cli.roadmap.intake.intake_requests import Spend, SpendMeter
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import install_roadmap_store
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.roadmap_github_store import RecordedGh, issue_payload, labeled
from tests.support.roadmap_intake import LATER, REPO, FakeModel, Roadmap


def test_an_asked_for_issue_that_is_no_candidate_is_reported_and_left_alone(
    roadmap: Roadmap,
) -> None:
    item = roadmap.finished("already an item")
    candidate = roadmap.issue("feat: asked for")
    roadmap.issue("feat: not asked for")
    plan = roadmap.plan(FakeModel(), issues=[item, candidate])
    report = render_intake(plan, repo=REPO)
    assert (
        [d.subject.number for d in plan.decisions],
        plan.missing,
        f"#{item}: not an open issue with no Priority, so intake leaves it alone" in report,
    ) == ([candidate], (item,), True)


def test_plan_reads_and_asks_the_model_writes_nothing_and_reports_its_spend(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    number = opened.issue("feat: previewed")
    before = opened.store.job_writes()
    preview = run_intake("--plan")
    assert (
        f"#{number} feat: previewed: type/feature, P2-Medium, Value Medium, Effort Low; to the "
        "backlog" in preview,
        "writes: label type/feature; Status New" in preview,
        "Nothing was written" in preview,
        "1 embedding call(s) for 1 text(s), 1 proposal call(s)" in preview,
        "GraphQL points not known" in preview,
        len(fake_model.requests),
        opened.store.job_writes() == before,
    ) == (True, True, True, True, True, 1, True)


def test_intake_plan_reports_a_possible_duplicate_with_the_writes_that_place_it(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """`devops roadmap intake --plan` reports the possible original of a candidate, and the
    writes that place it: it closes nothing (#2218)."""
    parent = opened.issue("feat: parent issue", milestone=LATER)
    split = opened.finished("feat: split issue")
    fake_model.duplicates["feat: parent issue"] = "feat: split issue"
    output = run_intake("--issue", str(parent), "--plan")
    possible = (
        f"- possible duplicate: #{split}. The model names `feat: split issue` as the change that "
        "both ask for. - writes: "
    )
    assert (possible in output, "close" in output) == (True, False)


def test_confirm_reports_what_it_placed_names_what_it_skipped_and_exits_one(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """The person running it sees the placements, then which candidate failed and why (#1443)."""
    placed, refused = opened.issue("feat: placed"), opened.issue("feat: refused")
    opened.store.fail_write(
        write="label_issue",
        item=refused,
        error=GitHubOperationError("HTTP 502: Bad Gateway", operation="roadmap.write"),
    )
    output = run_intake("--confirm", exit_code=1)
    assert (
        "Intake placed 1 item(s)." in output,
        "Intake finished with candidates it could not write: the writes failed for 1 "
        "candidate(s)" in output,
        f"#{refused} (GitHubOperationError: HTTP 502: Bad Gateway)" in output,
        opened.fields(placed),
    ) == (True, True, True, ("New", "P2-Medium", "Medium", "Low", None))


def test_plain_intake_previews_as_plan_does_and_says_what_it_spends(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    opened.issue("feat: previewed")
    before = opened.store.job_writes()
    plain, planned = run_intake(), run_intake("--plan")
    note = " ".join(MESSAGES.roadmap.intake_plain_note.split())
    assert (
        note in plain,
        note in planned,
        plain.partition(note)[2].strip() == planned,
        opened.store.job_writes() == before,
    ) == (True, False, True, True)


@pytest.mark.parametrize(
    "flags", [("--dry-run", "--plan"), ("--dry-run", "--confirm"), ("--plan", "--confirm")]
)
def test_the_mode_flags_exclude_each_other(
    no_requests: None, flags: tuple[str, ...], run_intake: Callable[..., str]
) -> None:
    assert "one of --dry-run, --plan and --confirm" in run_intake(*flags, exit_code=1)


def test_the_spend_meter_counts_every_request_the_ledger_paces_and_each_model_call(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    """Every GitHub request a run makes waits its turn on the identity's ledger: a gh command
    through `run_gh` and a request the GitHub session sends alike (#983). The meter reports the
    requests paced since it started, by the resource they spend, and the embedding and proposal
    calls; a request paced before it started is not the run's."""
    from devops_cli.github import rate_limiter

    limiter = rate_limiter.get_github_rate_limiter()
    for resource in ("search", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 600)
    limiter.acquire(subcommand="core")
    meter = SpendMeter()
    github_api, process_fake = github_api_and_gh
    process_fake.answer("gh", ProcessAnswer(stdout="[]"))
    rate_limiter.run_gh(["api", "repos/example/roadmap/issues/1"])
    rate_limiter.run_gh(["api", "-X", "GET", "search/issues", "-f", "q=x", "-F", "per_page=1"])
    rate_limiter.run_gh(["api", "graphql", "-f", "query=query { viewer { login } }"])
    listing = "/repos/example/roadmap/milestones?state=all&per_page=100"
    github_api.route("GET", listing, github_json([]))
    list(get_github_session().paginate(listing))
    model = meter.model(FakeModel())
    model.embed(["one", "two"])
    model.propose(ProposalRequest(title="t", body="b", shortlist=(), types=("type/bug",)))
    assert meter.spend() == Spend(
        rest=2, search=1, graphql=1, embedding_calls=1, embedded_texts=2, model_calls=1
    )


def test_an_unreachable_gateway_exits_non_zero_names_it_and_writes_nothing(
    opened: Roadmap,
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    run_intake: Callable[..., str],
) -> None:
    class Unreachable:
        def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
            raise ConnectionError("connection refused")

    gateway = "http://example.com:4000/v1"
    config(ai={"gateway_url": gateway, "gateway_enabled": True})
    install_embedder(Unreachable())
    opened.issue("feat: waits")
    before = opened.store.job_writes()
    output = run_intake("--confirm", exit_code=1)
    assert (f"gateway {gateway}" in output, opened.store.job_writes() == before) == (True, True)


def test_title_and_body_file_go_together(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    assert "--body-file" in run_intake("--title", "lonely", exit_code=1)


def test_intake_title_confirm_exits_non_zero_when_candidate_is_skipped(
    opened: Roadmap, fake_model: FakeModel, tmp_path: Path, run_intake: Callable[..., str]
) -> None:
    """devops roadmap intake --title ... --body-file ... --confirm exits non-zero when the candidate
    is skipped (#1677)."""
    body_file = tmp_path / "body.md"
    body_file.write_text("candidate body", encoding="utf-8")
    fake_model.proposals["A failing candidate"] = {"type": "type/perf"}
    output = run_intake(
        "--title",
        "A failing candidate",
        "--body-file",
        str(body_file),
        "--confirm",
        exit_code=1,
    )
    assert "skipped, nothing written" in output


def test_intake_confirm_over_existing_issues_exits_zero_when_skipped(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """A run over existing candidates keeps exit 0 and lists its skips (#1677)."""
    issue = opened.issue("An existing issue")
    fake_model.proposals["An existing issue"] = {"type": "type/perf"}
    output = run_intake("--confirm", exit_code=0)
    assert f"#{issue} An existing issue: skipped, nothing written" in output


def test_a_run_reads_the_changes_since_the_last_run_and_full_reads_the_whole_listing(
    github_api: GitHubApiFake, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """The first run reads the whole listing and keeps a snapshot; `--full` reads the whole
    listing again; a later run reads only the issues changed since the snapshot (#4448)."""
    install_roadmap_store(
        lambda repo, runner=None, **options: GitHubRoadmapStore(
            repo, runner=RecordedGh({}), **options
        )
    )
    item = labeled(issue_payload(1, updated_at="2026-01-01T09:00:00Z"), "priority/p2-medium")
    listing = f"/repos/{REPO}/issues?state=all"
    github_api.route("GET", f"{listing}&per_page=100", github_json([item]))
    since = "2026-01-01T08:59:00Z"
    changed = f"{listing}&sort=updated&direction=desc&since={since}&per_page=100"
    github_api.route("GET", changed, github_json([]))
    for flags in ((), ("--full",), ()):
        run_intake("--plan", *flags)
    assert [request.url.params.get("since") for request in github_api.sent] == [None, None, since]
