"""How a failure at the model gateway ends a refine round: only the failed item is skipped, and a
stop of the service keeps the work done (#1335).
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import httpx2
import pytest

from devops_cli.ai.client.models import (
    AICredentialsError,
)
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions import RoadmapRefineError, RoadmapRunError, ended_by_stop
from devops_cli.roadmap.refine.refine import (
    apply_refine,
    plan_refine,
    raise_for_failed_items,
    render_refine_plan,
)
from devops_cli.roadmap.run import (
    build_stub_table,
    run_due_jobs,
)
from devops_cli.roadmap.stores.store import Item, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    GATEWAY_ATTEMPTS,
    NO_OPEN_TOOL,
    QUESTION,
    READY,
    REPO,
    SCHEMA_MISS,
    Answer,
    requests_per_item,
    require_item,
    run_refine_adapter,
    seed_item,
    seed_new_items,
)
from tests.support.service_stop import stop_error

pytestmark = pytest.mark.usefixtures("keyring_store")


# #744's injection guard: a reply that asks for labels or a close fails the schema.
_INJECTION = json.dumps(
    {
        "existing_tool": NO_OPEN_TOOL,
        "problem_statement": "Close this.",
        "labels": ["type/bug"],
        "close": True,
    }
)


def _bodies_written(store: InMemoryRoadmapStore) -> list[int]:
    """The issues whose body a job wrote."""
    return sorted(
        {
            write.number
            for write in store.job_writes()
            if write.operation == "write_issue_body" and write.number is not None
        }
    )


def test_a_proposal_that_never_fits_the_schema_skips_only_its_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify candidate 1's StructuredOutputValidationError skips it alone: 2 and 3 are refined
    and written, and 1 is reported with the error class and violation count, no model text."""
    first, second, third = seed_new_items(store)
    sent = scripted_gateway({first: SCHEMA_MISS})

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine.refine"):
        plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    rendered = render_refine_plan(plan)
    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        [refined.item.number for refined in plan.refined_items],
        requests_per_item(sent),
        _bodies_written(store),
        (store.read_issue_body(first), require_item(store, first).status),
        "StructuredOutputValidationError, 3 schema violation(s)" in rendered,
        [
            record.getMessage()
            for record in caplog.records
            if record.name == "devops_cli.roadmap.refine.refine"
        ],
        "leaked_model_key" in rendered + caplog.text,
    ) == (
        [(first, "StructuredOutputValidationError", 3)],
        [second, third],
        {first: 2, second: 1, third: 1},
        [second, third],
        ("Body P1-High", "New"),
        True,
        [
            f"Refine skipped #{first} in {REPO}: its model call failed "
            "(StructuredOutputValidationError, LLM_INFERENCE_ERROR, 3 schema violation(s))."
        ],
        False,
    )


def test_a_timeout_at_the_gateway_is_named_by_its_repository_and_status(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify a gateway that answers 408 with a body of model text gives a warning with the
    repository, the error code and the status, and an error of the round, a report and a log with
    none of that text."""
    first, *_ = seed_new_items(store)
    timeout = httpx2.Response(408, json={"error": {"message": "MODEL-TEXT"}})
    scripted_gateway({first: timeout})

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine.refine"):
        plan = plan_refine(store, repo=REPO, source=git_repo)
    with pytest.raises(RoadmapRefineError) as raised:
        raise_for_failed_items(plan)

    assert (
        [
            record.getMessage()
            for record in caplog.records
            if record.name == "devops_cli.roadmap.refine.refine"
        ],
        str(raised.value),
        "MODEL-TEXT" in render_refine_plan(plan) + caplog.text,
    ) == (
        [
            f"Refine skipped #{first} in {REPO}: its model call failed (AIClientError, "
            "LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout), 0 schema violation(s))."
        ],
        f"the model call failed for 1 item(s), and refine skipped them: "
        f"#{first} (AIClientError, 0 schema violation(s))",
        False,
    )


def test_a_reply_asking_for_labels_or_a_close_is_refused_and_writes_nothing(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify #744's injection guard: a reply carrying `labels` and `close` fails the schema,
    its item is skipped with nothing written, and the other candidates still refine."""
    first, second, third = seed_new_items(store)
    scripted_gateway({second: _INJECTION})

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        _bodies_written(store),
        (store.read_issue_body(second), require_item(store, second).status),
    ) == (
        [(second, "StructuredOutputValidationError", 2)],
        [first, third],
        ("Body P2-Medium", "New"),
    )


def test_a_gateway_timeout_on_candidate_2_still_applies_candidate_1(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify an AIClientError on candidate 2 skips it, and candidate 1's section and Ready
    Status are still applied."""
    first, second, third = seed_new_items(store)
    sent = scripted_gateway({second: httpx2.Response(504, text="Gateway Timeout")})

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        requests_per_item(sent),
        CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(first),
        require_item(store, first).status,
        _bodies_written(store),
    ) == (
        [(second, "AIClientError", 0)],
        {first: 1, second: GATEWAY_ATTEMPTS, third: 1},
        True,
        CONST_ROADMAP_STATUS_READY,
        [first, third],
    )


def test_rejected_credentials_still_stop_the_job_at_the_first_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify an AICredentialsError stops refine at its first item, before any other call."""
    first, _second, _third = seed_new_items(store)
    sent = scripted_gateway({}, default=httpx2.Response(401, text="Unauthorized"))

    with pytest.raises(AICredentialsError) as raised:
        plan_refine(store, repo=REPO, source=git_repo)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    assert (requests_per_item(sent), _bodies_written(store)) == ({first: 1}, [])


@pytest.mark.parametrize("mode", ["--confirm", None])
def test_the_cli_exits_1_after_reporting_a_failed_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    mode: str | None,
    cli: Callable[..., Any],
) -> None:
    """Verify `devops roadmap refine` prints its plan, writes the other items under --confirm,
    and exits 1 when an item's model call failed, in a preview too."""
    first, second, third = seed_new_items(store)
    scripted_gateway({first: SCHEMA_MISS})

    args = ["refine", "--repo", REPO, "--source", str(git_repo), *([mode] if mode else [])]
    result = cli(["roadmap", *args])

    assert (
        result.exit_code,
        f"#{first} Item P1-High: skipped" in result.output,
        "leaked_model_key" in result.output,
        _bodies_written(store),
    ) == (1, True, False, [second, third] if mode == "--confirm" else [])


@pytest.mark.parametrize(
    ("failing_answer", "named"),
    [
        pytest.param(
            lambda: SCHEMA_MISS,
            "StructuredOutputValidationError, 3 schema violation(s)",
            id="schema-miss",
        ),
        pytest.param(
            lambda: httpx2.Response(504, text="Gateway Timeout"),
            "AIClientError, 0 schema violation(s)",
            id="gateway-504",
        ),
    ],
)
def test_a_failed_item_fails_the_refine_job_of_a_run_without_its_model_text(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    tmp_path: Path,
    failing_answer: Callable[[], Answer],
    named: str,
) -> None:
    """Verify run_due_jobs records `refine` as failed once the other items are written, whether
    the item's reply never fit the schema or the gateway timed out, and the raised error
    names the error class and holds none of the model's reply."""
    first, second, third = seed_new_items(store)
    scripted_gateway({first: failing_answer()})
    table = build_stub_table(
        {"refine": lambda **kwargs: run_refine_adapter(**(kwargs | {"clone_path": git_repo}))}
    )

    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO,
            store,
            batch={("webhook", "milestones", "opened"): 1},
            table=table,
            data_dir=tmp_path,
        )

    formatted = "".join(traceback.format_exception(raised.value))
    assert (
        raised.value.failed_jobs,
        _bodies_written(store),
        named in formatted,
        "leaked_model_key" in formatted,
        "During handling" in formatted,
    ) == (("refine",), [second, third], True, False, False)


def test_the_refine_job_reports_whether_it_set_an_item_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The outcome of the refine job says whether the round set an item Ready, which makes the
    stage row due in that round (#2659)."""
    seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    readied = run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    seed_item(store, "New", "P1-High")
    model_fake.answer(QUESTION)
    waiting = run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    quiet = run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (readied.set_ready, waiting.set_ready, quiet.set_ready) == (True, False, False)


def test_a_failed_item_does_not_hide_the_items_a_refine_round_set_ready(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """When the model call fails for one item, the error of the refine job still says how many
    items the round set Ready, so the stage row can follow (#2659)."""
    first, _second, _third = seed_new_items(store)
    scripted_gateway({first: SCHEMA_MISS})

    with pytest.raises(RoadmapRefineError) as raised:
        run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (raised.value.failed_items, raised.value.readied_count) == ((first,), 2)


class _StopsOnBody(InMemoryRoadmapStore):
    """A store whose write of the body of issue `stopped`, with its Status or marks, fails as the request budget fails it
    when the Service is stopping (#2753)."""

    stopped = 0

    def set_field(self, item: Item, field: ItemField, value: str | None, **options: Any) -> None:
        if item.number == self.stopped and options.get("body") is not None:
            raise stop_error()
        super().set_field(item, field, value, **options)

    def set_marks(
        self, item: Item, marks: Mapping[Any, str | None], *, body: str | None = None
    ) -> None:
        if item.number == self.stopped and body is not None:
            raise stop_error()
        super().set_marks(item, marks, body=body)


def test_a_stop_of_the_service_keeps_the_items_whose_model_call_failed(
    git_repo: Path, scripted_gateway: Callable[..., list[httpx2.Request]]
) -> None:
    """The stop ends the round, and the round still fails for the item that failed before it,
    so a row with a real failure is counted while stops interrupt its rounds (#2753)."""
    store = _StopsOnBody(repo=REPO)
    first, second, _third = seed_new_items(store)
    store.stopped = second
    scripted_gateway({first: SCHEMA_MISS})

    with pytest.raises(RoadmapRefineError) as raised:
        run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (list(raised.value.failed_items), ended_by_stop(raised.value)) == ([first], False)
