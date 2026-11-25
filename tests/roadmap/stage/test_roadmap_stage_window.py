"""The first request of a plan run leaves room for the tools of the planner (#3477).

The run hook offers no tool when the messages and a share of the window for the reply reach the
window. A first request over that limit gets no tool, so the model writes a plan about code that
it did not read. These tests use the real hook, a scripted model and a real git checkout, so no
test reaches a model.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, UserPromptPart

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE,
    CONST_ROADMAP_STAGE_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS,
    CONST_ROADMAP_STAGE_SPEC_MAX_CHARS,
    CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
)
from devops_cli.roadmap.stage import stage
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    openspec_tool,
    parse_filters,
    plan_item,
    plan_stage,
)
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, Severity
from devops_cli.roadmap.stage.stage_eval_run import RecordingClient
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel
from devops_cli.roadmap.stage.stage_verify import (
    Finding,
    Locator,
    PlanPart,
    Verification,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    GONE,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    later_review,
    seed_stageable,
    validate_args,
)
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store", "model_fake")

# A small planner window, for the scripted runs that test the caps of the first request.
WINDOW = 65536
# A large review window and a very large model window, for the scripted runs that use a window
# above the small one.
CONFIGURED_WINDOW = 256_000
GATEWAY_WINDOW = 1_048_576
# The body of an item that cites `keep`, the function of the sample module that the clone of
# `tests/support/roadmap_stage.py` writes: the probe writes a line for it, so the content gate
# refuses a `feasibility` that quotes no probe line.
KEEP_BODY = "The job drops the last comment of `keep`."
_PLAN = make_stage_proposal()


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the review, apart from the model edge of the planner."""
    return ModelFake()


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


def _words(tokens: int) -> str:
    """Text of more than `tokens` tokens, with no repeated word."""
    return " ".join(f"word{n}" for n in range(tokens))


def _run(store: InMemoryRoadmapStore, repo: StageRepo, script: Script) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=ToolboxModel(script.model()),
        step_tokens=10**6,
    )


def _plan(store: InMemoryRoadmapStore, repo: StageRepo, script: Script) -> None:
    assert len(_run(store, repo, script).ready) == 1


def _request_json(script: Script, index: int) -> dict[str, Any]:
    """The request at `index`, as the JSON that `_ask_plan` sends."""
    message = script.seen[index][-1]
    assert isinstance(message, ModelRequest)
    text = next(p.content for p in message.parts if isinstance(p, UserPromptPart))
    return json.loads(str(text))


def _first_request(script: Script) -> dict[str, Any]:
    """The first request of the run, as the JSON that `_ask_plan` sends."""
    return _request_json(script, 0)


def _request_tokens(script: Script, index: int) -> int:
    """The tokens of the request at `index` as the run hook counts them: every message, as JSON."""
    return count_tokens(ModelMessagesTypeAdapter.dump_json(script.seen[index]).decode())


def _first_request_tokens(script: Script) -> int:
    """The tokens of the first request as the run hook counts them: every message, as JSON."""
    return _request_tokens(script, 0)


def _return_request(script: Script) -> dict[str, Any]:
    """The request of the first return of a refused reply, as the JSON that `_ask_plan` sends: the
    third request of the run, after the first request and the answer of the tool call."""
    return _request_json(script, 2)


# The tokens that the first request at the caps leaves for a change of the stage prompt: #6091 grew
# the prompt by 243 tokens and took the request 41 tokens over the limit (#6103).
_PROMPT_HEADROOM = 512


def _limit(window: int) -> int:
    """The tokens at which the run hook offers no tool."""
    return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE


def _long_plan() -> StageProposal:
    """The earlier plan of a return request: its `why` is longer than the limit of the tools."""
    return make_stage_proposal(why=_words(20_000))


def _script() -> Script:
    """A model that lists files, then answers the plan. Its replies report the input of their
    request, as a provider does, since the window follows it (#4221)."""
    return Script(
        call("list_files", directory="src"), _PLAN, without_tools=_PLAN, reports_input=True
    )


def _one_open_finding() -> Verification:
    """A review that returns group 1 of the plan to the planner."""
    return Verification(
        findings=[
            Finding(
                type=DefectType.FALSE_PREMISE,
                severity=Severity.MAJOR,
                where=Locator(part=PlanPart.TASKS, section="1"),
                problem="The premise is wrong.",
                quote="The job drops the last comment of a thread.",
            )
        ]
    )


def _code(tokens: int) -> str:
    """Code-like text of more than `tokens` tokens. Quotes, backslashes and newlines grow when
    the request is encoded as JSON, so this text counts more in the request than in the cap."""
    return "\n".join(
        f'    value_{n} = {{"key": "a\\tb", "n": {n}}}  # "quoted" \\ text' for n in range(tokens)
    )


def test_a_first_request_with_the_context_and_the_body_at_their_caps_offers_the_tools_and_a_reserve(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The job reads the windows of its own two tasks and of no other (#5903).
    monkeypatch.setattr(stage, "task_window", {"stage": WINDOW, "stage_review": WINDOW}.__getitem__)
    stage_repo.track({"CONTEXT.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)})
    seed_stageable(store, body=_words(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    _plan(store, stage_repo, script)

    request = _first_request(script)
    assert (
        count_tokens(request["context"]),
        count_tokens(request["body"]),
        "read_spec" in script.tools_offered[0],
        _first_request_tokens(script) <= _limit(WINDOW) - CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
    ) == (CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS, CONST_ROADMAP_STAGE_BODY_MAX_TOKENS, True, True)


def test_a_first_request_of_code_with_the_context_and_the_body_at_their_caps_offers_the_tools(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reserve of the spec holds for plain text. Quotes and newlines grow in the JSON of the
    request, so for code the reserve is smaller, and the request must still stay under the limit,
    with room for a small change of the stage prompt (#6103)."""
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    stage_repo.track({"CONTEXT.md": _code(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)})
    seed_stageable(store, body=_code(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    _plan(store, stage_repo, script)

    assert (
        "read_spec" in script.tools_offered[0],
        _first_request_tokens(script) < _limit(WINDOW) - _PROMPT_HEADROOM,
    ) == (True, True)


def _decision(index: int) -> str:
    return f"Decision {index}: take the next free ADR number, as 0028 and 0029 are taken."


def test_the_first_request_holds_the_comments_of_persons_and_of_jobs_whole(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    """The first request gives the planner every comment of the item, oldest first, with its
    author: the decision of a person and the report of a roadmap job (#6167)."""
    number = seed_stageable(store)
    report = f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\nNo open tool covers the need."
    store.seed_comment(number, report)
    store.seed_comment(number, _decision(1), author_login="alice")
    script = _script()

    _plan(store, stage_repo, script)

    comments = _first_request(script)["comments"]
    assert [(entry["number"], entry["text"]) for entry in comments["comments"]] == [
        (1, report),
        (2, _decision(1)),
    ]
    assert (comments["unlisted"], "read_comment" in script.tools_offered[0]) == (0, True)


def test_a_first_request_of_code_at_its_caps_with_comments_offers_the_tools(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The comments take room of the context, so a first request of code with the context, the
    body and many long comments at their caps stays under the limit with the headroom of #6103,
    and gives the newest comment whole (#6167)."""
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    stage_repo.track({"CONTEXT.md": _code(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)})
    number = seed_stageable(store, body=_code(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    for index in range(40):
        store.seed_comment(number, f"{_decision(index)}\n{_code(300)}")
    store.seed_comment(number, _decision(40))
    script = _script()

    _plan(store, stage_repo, script)

    request = _first_request(script)
    entries = request["comments"]["comments"]
    assert (
        "read_spec" in script.tools_offered[0],
        _first_request_tokens(script) < _limit(WINDOW) - _PROMPT_HEADROOM,
        entries[-1].get("text"),
        len(entries) + request["comments"]["unlisted"],
    ) == (True, True, _decision(40), 41)


def test_a_return_request_keeps_the_full_earlier_plan_when_it_fits(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full earlier plan fits: a plan whose request stays under the limit goes back whole, and
    the keys of the earlier plan stay: every key of the plan is in `previous`."""
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    seed_stageable(store, body=KEEP_BODY)
    earlier = make_stage_proposal()
    script = Script(
        call("list_files", directory="src"), earlier, without_tools=earlier, reports_input=True
    )

    _run(store, stage_repo, script)

    request = _return_request(script)
    print(f"return request: {_request_tokens(script, 2)} tokens; limit {_limit(WINDOW)} tokens")
    assert (request["previous"], list(request["previous"])) == (
        earlier.model_dump(),
        list(earlier.model_dump()),
    )


def test_a_gate_return_with_the_full_earlier_plan_leaves_room_for_the_tools(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gate return with a long earlier plan: the plan of 20,000 words goes back with the problem,
    and the request that the planner receives stays under the limit at which the run offers no
    tool, so the planner keeps `read_spec`."""
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    seed_stageable(store, body=KEEP_BODY)
    earlier = _long_plan()
    script = Script(
        call("list_files", directory="src"), earlier, without_tools=earlier, reports_input=True
    )

    _run(store, stage_repo, script)

    measured = _request_tokens(script, 2)
    print(f"return request: {measured} tokens; limit {_limit(WINDOW)} tokens")
    request = _return_request(script)
    previous = request["previous"]
    assert (
        measured < _limit(WINDOW),
        "read_spec" in script.tools_offered[2],
        "problem" in request,
        previous["why"] != earlier.why,
        list(previous) == list(earlier.model_dump()),
    ) == (True, True, True, True, True)


def test_a_repair_return_request_of_a_large_plan_leaves_room_for_the_tools(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
    verifier: ModelFake,
) -> None:
    """A review repair with a long earlier plan: the full earlier plan passes the limit of the
    tools, so the plan goes back bounded with the open finding of the review, and the request that
    the planner receives stays under the limit at which the run offers no tool, so the planner
    keeps `read_spec`. The review reads the plan at its own window, which the tasks can set apart
    from the window of the planner (#3039)."""
    monkeypatch.setattr(
        stage,
        "task_window",
        lambda task: CONFIGURED_WINDOW if task == "stage_review" else WINDOW,
    )
    seed_stageable(store)
    earlier = _long_plan()
    verifier.answer(_one_open_finding(), later_review(GONE))
    script = Script(
        call("list_files", directory="src"), earlier, without_tools=earlier, reports_input=True
    )

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        model=ToolboxModel(script.model()),
        verifier=ToolboxModel(verifier),
        step_tokens=10**6,
    )

    measured = _request_tokens(script, 2)
    print(f"repair return request: {measured} tokens; limit {_limit(WINDOW)} tokens")
    request = _return_request(script)
    previous = request["previous"]
    assert (
        len(plan.ready),
        measured < _limit(WINDOW),
        "read_spec" in script.tools_offered[2],
        "problem" in request,
        previous["why"] != earlier.why,
        list(previous) == list(earlier.model_dump()),
    ) == (1, True, True, True, True, True)


def test_the_first_request_names_the_capabilities_and_holds_no_capability_json(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    names = [f"capability-{n:03d}" for n in range(170)]
    stage_repo.track(
        {
            f"openspec/specs/{name}/spec.md": (
                f"# {name} Specification\n\n## Purpose\nThe purpose of {name} is long. "
                f"{_words(30)}\n\n## Requirements\n\n"
                + "".join(
                    f"### Requirement: Rule {n} of {name}\nThe rule SHALL hold.\n\n"
                    for n in range(8)
                )
            )
            for name in names
        }
    )
    seed_stageable(store)
    script = _script()

    _plan(store, stage_repo, script)

    capabilities = _first_request(script)["capabilities"]
    prompt = json.dumps(_first_request(script))
    assert (
        capabilities,
        "purpose" in prompt,
        "Rule 1 of capability-000" in prompt,
        "read_spec" in script.tools_offered[0],
    ) == (sorted([*names, "roadmap-refine"]), False, False, True)


def test_the_recorder_of_the_golden_set_keeps_the_names_only_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    """The golden set wraps the toolbox client in the recorder, and plans as the job does."""
    names = [f"capability-{n:03d}" for n in range(5)]
    stage_repo.track(
        {
            f"openspec/specs/{name}/spec.md": (
                f"# {name} Specification\n\n## Purpose\nThe purpose of {name}.\n\n"
                f"## Requirements\n\n### Requirement: Rule of {name}\nThe rule SHALL hold.\n"
            )
            for name in names
        }
    )
    target = store.item(seed_stageable(store))
    assert target is not None
    sha = stage_repo.git("rev-parse", "HEAD")
    script = _script()

    with openspec_tool() as tool:
        toolbox = ToolboxClient(
            script.model(),
            cast("StageClient", object()),
            stage_repo.clone,
            sha,
            openspec=tool,
        )
        plan_item(target, client=RecordingClient(toolbox), checkout=stage_repo.clone, sha=sha)

    assert (
        _first_request(script)["capabilities"],
        "read_spec" in script.tools_offered[0],
    ) == (sorted([*names, "roadmap-refine"]), True)


@pytest.mark.parametrize("window", [WINDOW, GATEWAY_WINDOW])
def test_the_caps_of_the_context_and_the_body_do_not_grow_with_the_window(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
    window: int,
) -> None:
    monkeypatch.setattr(stage, "task_window", lambda task: window)
    stage_repo.track({"CONTEXT.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)})
    seed_stageable(store, body=_words(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    _plan(store, stage_repo, script)

    request = _first_request(script)
    assert (count_tokens(request["context"]), count_tokens(request["body"])) == (
        CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS,
        CONST_ROADMAP_STAGE_BODY_MAX_TOKENS,
    )


def test_a_small_window_cuts_the_caps_to_a_share_of_itself(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stage, "task_window", lambda task: 8192)
    stage_repo.track({"CONTEXT.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)})
    seed_stageable(store, body=_words(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    # A window of 8192 tokens ends the tools at once, so the run fails (#3880).
    _run(store, stage_repo, script)

    request = _first_request(script)
    assert (count_tokens(request["context"]), count_tokens(request["body"])) == (4096, 2048)


def test_a_window_that_ends_the_tools_too_soon_fails_the_item_and_names_the_setting(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window of 8192 tokens ends the tools after one call, and the model then answers a plan.
    The job records the window and not the faults of the plan (#3880)."""
    monkeypatch.setattr(stage, "task_window", lambda task: 8192)
    seed_stageable(store, body=_words(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    plan = _run(store, stage_repo, script)

    (failure,) = plan.failed
    assert (plan.ready, failure.error) == ((), "RoadmapStageError")
    assert "ai.tasks.stage.context_window" in failure.reason


def test_the_context_and_the_largest_spec_answer_stay_under_half_of_the_window() -> None:
    """The largest answer of `read_spec` is the cap in characters; plain English runs at about
    4 characters for a token, so this text counts the most that an answer can hold."""
    answer = "The rule SHALL hold for every request of the job. " * (
        CONST_ROADMAP_STAGE_SPEC_MAX_CHARS // 50
    )

    assert CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS + count_tokens(answer) < WINDOW // 2
