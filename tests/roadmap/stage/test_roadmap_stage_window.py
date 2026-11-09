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
import yaml
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, UserPromptPart

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE,
    CONST_ROADMAP_REFINE_TOOL_MAX_CHARS,
    CONST_ROADMAP_STAGE_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS,
    CONST_ROADMAP_STAGE_SPEC_MAX_CHARS,
    CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS,
)
from devops_cli.config.defaults import DEFAULT_AI_CONTEXT_WINDOW
from devops_cli.roadmap.refine.refine_investigation import tokens_of, tool_stop
from devops_cli.roadmap.stage import stage
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    openspec_tool,
    parse_filters,
    plan_item,
    plan_stage,
)
from devops_cli.roadmap.stage.stage_eval_run import RecordingClient
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel
from devops_cli.roadmap.stage.stage_verify import VerificationInput, agent_instructions
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
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
# The window of the `analysis` task in the example ConfigMap, and of its model in the gateway.
CONFIGURED_WINDOW = 200_000
GATEWAY_WINDOW = 1_000_000
# The first plan request at its caps, measured on 2026-11-07 (#3880), and the tokens of the longest
# tool answer, at about 4 characters for a token. The tools end when the messages reach the limit.
FIRST_REQUEST_TOKENS = 38_000
TOOL_ANSWER_TOKENS = CONST_ROADMAP_REFINE_TOOL_MAX_CHARS // 4
_PLAN = make_stage_proposal()


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


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


def _first_request(script: Script) -> dict[str, Any]:
    first = script.seen[0][0]
    assert isinstance(first, ModelRequest)
    text = next(p.content for p in first.parts if isinstance(p, UserPromptPart))
    return json.loads(str(text))


def _first_request_tokens(script: Script) -> int:
    """The tokens of the first request as the run hook counts them: every message, as JSON."""
    return count_tokens(ModelMessagesTypeAdapter.dump_json(script.seen[0]).decode())


def _limit(window: int) -> int:
    """The tokens at which the run hook offers no tool."""
    return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE


def _script() -> Script:
    """A model that lists files, then answers the plan. Its replies report the input of their
    request, as a provider does, since the window follows it (#4221)."""
    return Script(
        call("list_files", directory="src"), _PLAN, without_tools=_PLAN, reports_input=True
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
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    stage_repo.track(
        {"docs/adr/0001-a-decision.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)}
    )
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
    request, so for code the reserve is smaller, and the request must still stay under the limit."""
    monkeypatch.setattr(stage, "task_window", lambda task: WINDOW)
    stage_repo.track(
        {"docs/adr/0001-a-decision.md": _code(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)}
    )
    seed_stageable(store, body=_code(3 * CONST_ROADMAP_STAGE_BODY_MAX_TOKENS))
    script = _script()

    _plan(store, stage_repo, script)

    assert (
        "read_spec" in script.tools_offered[0],
        _first_request_tokens(script) < _limit(WINDOW),
    ) == (True, True)


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
    stage_repo.track(
        {"docs/adr/0001-a-decision.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)}
    )
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
    stage_repo.track(
        {"docs/adr/0001-a-decision.md": _words(3 * CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS)}
    )
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


def _data_of(path: str) -> Any:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _example_task(name: str) -> dict[str, Any]:
    return yaml.safe_load(_data_of("k8s/devops/configmap.example.yaml")["data"]["devops-cli.yaml"])[
        "ai"
    ]["tasks"][name]


def test_the_planner_window_of_the_example_configmap_fits_the_first_request_and_the_minimum_calls() -> (
    None
):
    """The task `stage` takes the window of `analysis`. At 65,536 tokens the tools end after 4 to 6
    calls, and the model writes `x` in every text field of its plan (#3880)."""
    needed = (
        FIRST_REQUEST_TOKENS + constants.CONST_ROADMAP_STAGE_MIN_TOOL_CALLS * TOOL_ANSWER_TOKENS
    )
    window = _example_task("analysis")["context_window"]

    assert (_limit(window) >= needed, _limit(WINDOW) < needed) == (True, True)


def _review_first_request_tokens() -> int:
    """The tokens of the first request of a review run with no cited file, counted as the run hook
    counts them: the issue body at its cap, the plan, and the instructions of the review. The
    request keeps its files below the limit, so a window that fits this request leaves the tools
    their room (`VerificationInput.of`)."""
    given = VerificationInput(
        1,
        "A title",
        _words(CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS),
        _PLAN.model_dump(mode="json"),
        {},
    )
    request = ModelRequest(
        parts=[UserPromptPart(content=given.text())],
        instructions=agent_instructions(load_task_prompt("roadmap_stage_verify.md")),
    )
    return tokens_of([request])


def test_the_review_window_of_the_example_configmap_fits_the_first_request_and_the_minimum_calls() -> (
    None
):
    """The task `verification` has no parent task, so it takes the window of `ai` when it sets
    none: 32,768 tokens, which ends the tools of a review at 24,576 (#3911)."""
    needed = (
        _review_first_request_tokens()
        + constants.CONST_ROADMAP_STAGE_MIN_TOOL_CALLS * TOOL_ANSWER_TOKENS
    )
    window = _example_task("verification").get("context_window", DEFAULT_AI_CONTEXT_WINDOW)

    assert (tool_stop(window) >= needed, tool_stop(DEFAULT_AI_CONTEXT_WINDOW) < needed) == (
        True,
        True,
    )


def test_the_review_keeps_deepseek_and_a_window_that_fits_while_the_planner_trials_sonnet() -> None:
    """The planner runs on `claude-sonnet-5-5` by the trial of 2026-11-09 (#4204), and the review
    stays on the one model of the other slots (#3874). Each window fits its own first request."""
    verification, analysis = _example_task("verification"), _example_task("analysis")

    assert (
        verification["model"],
        verification["context_window"],
        analysis["model"],
        analysis["context_window"],
    ) == ("deepseek-v4.1-flash-1017", 256_000, "claude-sonnet-5-5", 200_000)


def test_the_documented_window_of_analysis_and_its_source_are_the_files_values() -> None:
    configured = _example_task("analysis")
    gateway = {
        entry["model_name"]: entry
        for entry in _data_of("k8s/llm/gateway/config.yaml")["model_list"]
    }
    model_window = gateway[configured["model"]]["model_info"]["max_input_tokens"]
    page = (REPO_ROOT / "docs/roadmap/stage.md").read_text(encoding="utf-8")

    assert (configured["context_window"], model_window) == (CONFIGURED_WINDOW, GATEWAY_WINDOW)
    assert all(
        text in page
        for text in (
            f"`context_window` {CONFIGURED_WINDOW:,}",
            "k8s/devops/configmap.example.yaml",
            f"`max_input_tokens` {GATEWAY_WINDOW:,}",
            "k8s/llm/gateway/config.yaml",
        )
    )
