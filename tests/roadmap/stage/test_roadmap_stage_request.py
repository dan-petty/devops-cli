"""`devops roadmap stage`: the planner request is a typed model that the gates read (#4046).

The request holds the fields that the model reads and the inputs of the gates. The model sees the
same JSON as before. A gate runs again from the request and the tree, with no planner object.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import ProposalGate, check_gates, check_proposal
from devops_cli.roadmap.stage.stage_overlap import Overlap
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_request import GATE_ONLY_FIELDS, StageRequest, gate_arguments
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

METRIC = "devops_cli_github_requests_total"
SAMPLE = "src/devops_cli/sample.py"
SAMPLE_PROBE = f"The path `{SAMPLE}` is a file of the staging commit."
CRITERION = "`uv run pytest tests/test_sample.py` - the sample keeps the last comment."
ISSUE_BODY = f"Fix `{SAMPLE}`.\n\n## Acceptance criteria\n\n- [ ] {CRITERION}\n"
TREE = StagedTree([SAMPLE])
KNOWN = {"comment-thread"}
MODULE = "src/devops_cli/roadmap/stage/stage_paths.py"
MODULE_TEST = "tests/roadmap/stage/test_roadmap_stage_paths.py"
PULL = Overlap(
    number=3173,
    title="docs(openspec): plan #3173 the telemetry page",
    state="open",
    plan=True,
    paths=(SAMPLE,),
)
# The keys that the model reads, in the order that the planner writes them.
MODEL_KEYS = [
    "number",
    "title",
    "body",
    "context",
    "capabilities",
    "budget",
    "rejected_plan",
    "overlaps",
    "metric_senders",
    "probes",
]


def _fields(**overrides: Any) -> dict[str, Any]:
    """The fields of a request with every optional key set, and `overrides` over them."""
    return {
        "number": 1,
        "title": "fix(roadmap): the job drops a comment",
        "body": f"Fix `{SAMPLE}`.",
        "context": "### Context\n\nThe sample keeps the comments.",
        "capabilities": ["comment-thread"],
        "budget": 6000,
        "rejected_plan": "A person rejected the plan: the sample is out of date.",
        "overlaps": [PULL.entry()],
        "metric_senders": {METRIC: ["docs/TELEMETRY.md"]},
        "probes": SAMPLE_PROBE,
        "issue_body": ISSUE_BODY,
        "probe_lines": (SAMPLE_PROBE,),
        "overlap_pulls": (PULL,),
        "creators": {"tests/test_sample.py": 3308},
        **overrides,
    }


def _request(**overrides: Any) -> StageRequest:
    return StageRequest(**_fields(**overrides))


# ── The JSON that the model reads ─────────────────────────────────────────────


def test_model_json_unchanged_for_a_request_with_every_key() -> None:
    request = _request()

    sent = request.for_model()

    assert list(sent) == MODEL_KEYS
    assert sent == {
        "number": 1,
        "title": "fix(roadmap): the job drops a comment",
        "body": f"Fix `{SAMPLE}`.",
        "context": "### Context\n\nThe sample keeps the comments.",
        "capabilities": ["comment-thread"],
        "budget": 6000,
        "rejected_plan": "A person rejected the plan: the sample is out of date.",
        "overlaps": [PULL.entry()],
        "metric_senders": {METRIC: ["docs/TELEMETRY.md"]},
        "probes": SAMPLE_PROBE,
    }


def test_model_json_unchanged_for_a_request_with_no_optional_key() -> None:
    request = _request(
        rejected_plan=None,
        overlaps=None,
        metric_senders=None,
        probes=None,
        overlap_pulls=(),
        probe_lines=(),
    )

    assert list(request.for_model()) == MODEL_KEYS[:6]


def test_model_json_unchanged_holds_no_gate_only_field() -> None:
    sent = _request().for_model()

    assert GATE_ONLY_FIELDS == {"issue_body", "probe_lines", "overlap_pulls", "creators"}
    assert GATE_ONLY_FIELDS.isdisjoint(sent)
    assert set(sent) | GATE_ONLY_FIELDS == set(StageRequest.model_fields)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def _openspec(openspec_fake: OpenSpecFake) -> None:
    """OpenSpec, found, and valid about the change of #1 for every plan."""
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))


@pytest.fixture
def pulls_api(github_api: GitHubApiFake) -> GitHubApiFake:
    """GitHub, answering the read of the open pull requests with one plan that edits the sample."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    node = {
        "number": PULL.number,
        "title": PULL.title,
        "state": "OPEN",
        "files": {"nodes": [{"path": SAMPLE}]},
    }
    page = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [node],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    }
    github_api.route("POST", "/graphql", github_json(page))
    return github_api


def _plan(store: InMemoryRoadmapStore, stage_repo: StageRepo) -> None:
    plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        item_number=None,
        step_tokens=6000,
        model=None,
    )


def test_model_json_unchanged_through_the_planner(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    pulls_api: GitHubApiFake,
) -> None:
    stage_repo.track(
        {
            "src/devops_cli/telemetry/instruments.py": f'NAME = "{METRIC}"\n',
            "docs/TELEMETRY.md": f"| `{METRIC}` | requests |\n",
        }
    )
    body = f"Fix `{SAMPLE}` and `{METRIC}`."
    seed_stageable(store, body=body)
    model_fake.answer(
        make_stage_proposal(
            feasibility=[f"The probe shows: {SAMPLE_PROBE}"],
            dependencies=[f"#{PULL.number} changes `{SAMPLE}`, so this plan waits for it."],
        )
    )

    _plan(store, stage_repo)

    (call,) = model_fake.calls
    request = json.loads(call.prompt)
    assert list(request) == [key for key in MODEL_KEYS if key != "rejected_plan"]
    assert {key: request[key] for key in ("number", "title", "body", "budget")} == {
        "number": 1,
        "title": "fix(roadmap): the job drops a comment",
        "body": body,
        "budget": 6000,
    }
    assert request["overlaps"] == [PULL.entry()]
    assert request["metric_senders"] == {
        METRIC: ["docs/TELEMETRY.md", "src/devops_cli/telemetry/instruments.py"]
    }
    assert request["probes"].splitlines()[0] == SAMPLE_PROBE
    assert call.prompt == json.dumps(request, ensure_ascii=False, indent=1)


def test_model_json_unchanged_on_the_return_of_a_refused_reply(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    pulls_api: GitHubApiFake,
) -> None:
    seed_stageable(store, body=f"Fix `{SAMPLE}`.")
    model_fake.answer(make_stage_proposal(), make_stage_proposal(feasibility=[SAMPLE_PROBE]))

    _plan(store, stage_repo)

    first, again = (json.loads(call.prompt) for call in model_fake.calls)
    assert list(again) == [*first, "previous", "problem"]
    assert {key: again[key] for key in first} == first
    assert "quotes no line of the probes" in again["problem"]


# ── The gates read the request ────────────────────────────────────────────────


def _gates(request: StageRequest) -> dict[ProposalGate, list[str]]:
    """The problems of each gate for a plan that every gate of the request refuses."""
    return check_gates(make_stage_proposal(), **gate_arguments(request, TREE, known=KNOWN))


def test_gates_from_request_equal_the_direct_call() -> None:
    request = _request()
    proposal = make_stage_proposal()

    from_request = check_proposal(proposal, **gate_arguments(request, TREE, known=KNOWN))

    direct = check_proposal(
        proposal,
        KNOWN,
        TREE,
        issue_body=ISSUE_BODY,
        probes=(SAMPLE_PROBE,),
        overlaps=(PULL,),
        plan_creates={"tests/test_sample.py": 3308},
    )
    assert from_request == direct
    assert len(direct) >= 4


def test_gates_from_request_run_each_gate_that_reads_the_request() -> None:
    found = {gate for gate, problems in _gates(_request()).items() if problems}

    assert {
        ProposalGate.CONTENT,
        ProposalGate.CRITERIA,
        ProposalGate.DEPENDENCIES,
        ProposalGate.CREATES,
    } <= found


def test_gates_from_request_find_nothing_for_a_request_with_no_gate_input() -> None:
    request = _request(issue_body="Fix the sample.", probe_lines=(), overlap_pulls=(), creators={})

    found = {gate for gate, problems in _gates(request).items() if problems}

    assert found.isdisjoint(
        {
            ProposalGate.CONTENT,
            ProposalGate.CRITERIA,
            ProposalGate.DEPENDENCIES,
            ProposalGate.CREATES,
        }
    )


def test_gates_from_request_read_the_whole_issue_body_not_the_cut_one() -> None:
    cut = _request(body="Fix `src/devops_cli/sample.py`. [cut]")

    problems = _gates(cut)[ProposalGate.CRITERIA]

    assert any(CRITERION in problem for problem in problems)


def test_gates_from_request_pass_the_keyword_inputs_through() -> None:
    texts = {"src/devops_cli/sample.py": "VALUE = 1\n"}

    arguments = gate_arguments(
        _request(),
        TREE,
        known=KNOWN,
        requirements={"comment-thread": {"Keep"}},
        read_text=texts.get,
        constants={"CONST_PANEL_LIMIT": 3},
    )

    assert arguments["known"] == KNOWN
    assert arguments["tree"] is TREE
    assert arguments["requirements"] == {"comment-thread": {"Keep"}}
    assert arguments["read_text"] == texts.get
    assert arguments["constants"] == {"CONST_PANEL_LIMIT": 3}


def test_gates_from_request_pass_the_manifest_references_through() -> None:
    """The tests that each changed manifest reaches reach the `paths` gate (#3972)."""
    references = {
        "k8s/logging/networkpolicy.yaml": ("tests/commands/k8s/test_k8s_logging_stack.py",)
    }

    arguments = gate_arguments(_request(), TREE, known=KNOWN, manifest_references=references)

    assert arguments["manifest_references"] == references


def test_gates_from_request_pass_the_module_tests_through() -> None:
    """The tests of each changed module reach the `paths` gate (#3414)."""
    arguments = gate_arguments(_request(), TREE, known=KNOWN, module_tests={MODULE: (MODULE_TEST,)})

    assert arguments["module_tests"] == {MODULE: (MODULE_TEST,)}


def test_a_request_round_trips_through_json_so_a_gate_runs_again_from_a_file() -> None:
    request = _request()

    again = StageRequest.model_validate_json(request.model_dump_json())

    assert again == request
    assert check_proposal(
        make_stage_proposal(), **gate_arguments(again, TREE, known=KNOWN)
    ) == check_proposal(make_stage_proposal(), **gate_arguments(request, TREE, known=KNOWN))


# ── The keys are checked ──────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["budjet", "probe_lines_", "overlap", "extra"])
def test_forbid_extra_refuses_an_unknown_key(key: str) -> None:
    with pytest.raises(ValidationError, match=key):
        StageRequest(**_fields(**{key: 1}))
