"""The third attempt of a step moves to the next tier of the ladder (#3569).

A repair round used to send the same inputs to the same tier again, so a second failure of the same
kind repeated the strategy that failed. The third attempt of a step now runs on the next healthy
tier of `roadmap.implement.ladder`, in a new conversation whose message is the repair message of the
failed attempt, after the step discards the checkout back to its last kept commit, and it spends no
repair round.

The model of each tier is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a
checkout in `tmp_path`. `ruff check` reads the files of the checkout through `process_fake`, so a
file that holds `import os` fails the lint.

A shell call of an attempt reaches the gateway through the loopback broker of the step, and counts
as a model call of that tier (#3820). The shell is faked at the workspace edge, as in the job tests,
and the gateway answer is the HTTP fake.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx2
import pytest
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior
from pydantic_ai.workspaces import CommandResult
from pydantic_ai.workspaces.local import LocalWorkspaceBackend

from devops_cli.roadmap.implement.implement_limits import new_tokens
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.implement.implement_trace import ImplementTrace, TraceEventKind
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    make_checkout,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

CODER = "devops-coder"
REASONING = "devops-reasoning"
LADDER = [CODER, REASONING]
BAD_TEST = "import os\n\n" + TEST_BODY
UNUSED = "F401 `os` imported but unused\n --> tests/test_sample.py:1:8"
TOO_LONG = "E501 line too long (120 > 100)\n --> src/sample.py:9:1"
NOT_TICKED = (write_call("tests/test_sample.py", BAD_TEST), write_call("src/sample.py", SHOUT_CODE))
TICK = write_call(TASKS_PATH, TICKED)
LONG = write_call("src/sample.py", SHOUT_CODE + "\nLONG = '" + "x" * 120 + "'\n")


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _lint_answers(programs: ProcessFake, *answers: tuple[int, str]) -> None:
    """`ruff check` gives the first answer, then the last answer for each later call."""
    pending = list(answers)

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        code, report = pending.pop(0) if len(pending) > 1 else pending[0]
        return subprocess.CompletedProcess(call.argv, code, stdout=report, stderr="")

    programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=answer),
    )


def _step(
    store: InMemoryRoadmapStore,
    checkout: Path,
    models: dict[str, ModelScript],
    *,
    trace: ImplementTrace | None = None,
) -> StepOutcome:
    """The step on a ladder of two tiers, with one model for each tier."""
    built = {tier: script.model() for tier, script in models.items()}
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model_for_tier=built.__getitem__,
        window=WINDOW,
        ladder=LADDER,
        tier_health=lambda names: dict.fromkeys(names, True),
        trace=trace,
    )


def _attempts(trace: ImplementTrace) -> list[dict[str, object]]:
    return [event.fields for event in trace.events if event.kind is TraceEventKind.ATTEMPT]


def _prompt(script: ModelScript, request: int) -> str:
    return [str(getattr(part, "content", "")) for part in script.seen[request][-1].parts][-1]


def test_the_third_attempt_calls_the_model_of_the_second_tier(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """The first two attempts fail with a repairable class, so the third one moves to the second
    tier of the ladder and ends the step there (#3569)."""
    config(roadmap={"implement": {"repair_rounds": 2}})
    _lint_answers(programs, (1, f"{UNUSED}\n"), (1, f"{UNUSED}\n"), (0, ""))
    coder = ModelScript(tool_calls(*NOT_TICKED, TICK), say("No change."))
    reasoning = ModelScript(
        tool_calls(write_call("tests/test_sample.py", TEST_BODY)), say("Fixed.")
    )
    trace = ImplementTrace(step="group 1")

    outcome = _step(store, checkout, {CODER: coder, REASONING: reasoning}, trace=trace)

    assert (outcome.status, outcome.tier, outcome.tiers, outcome.repair_rounds) == (
        StepStatus.DONE,
        REASONING,
        (CODER, REASONING),
        1,
    )
    assert [(a["number"], a["tier"], a["strategy"]) for a in _attempts(trace)] == [
        (1, CODER, "planned"),
        (2, CODER, "repo_map"),
        (3, REASONING, "tier"),
    ]


def test_the_third_attempt_sends_the_failure_text_in_a_new_conversation(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """The new tier gets the repair message of the second failure and not the message of the step,
    and the work of the failed attempt is discarded back to the commit where the step started,
    before it starts (#3569, #6559)."""
    config(roadmap={"implement": {"repair_rounds": 2}})
    start = (checkout / "src" / "sample.py").read_text("utf-8")
    _lint_answers(programs, (1, f"{UNUSED}\n"), (1, f"{TOO_LONG}\n"), (0, ""))
    seen_at_third: list[str] = []
    coder = ModelScript(
        tool_calls(*NOT_TICKED, TICK), say("Done."), tool_calls(LONG), say("Fixed.")
    )
    reasoning = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE)),
        say("Fixed."),
        effects={
            1: lambda: seen_at_third.append((checkout / "src" / "sample.py").read_text("utf-8"))
        },
    )

    outcome = _step(store, checkout, {CODER: coder, REASONING: reasoning})

    prompt = _prompt(reasoning, 0)
    assert (outcome.status, outcome.repair_rounds) == (StepStatus.DONE, 1)
    assert len(reasoning.seen[0]) == 1
    assert TOO_LONG in prompt
    assert UNUSED not in prompt
    assert seen_at_third == [start]


def test_an_attempt_after_a_change_tier_failure_names_the_second_tier_and_the_tier_strategy(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A failure whose class selects `change_tier` moves the tier at once, spends no repair round,
    and its next attempt event names that tier and the strategy `tier` (#3569)."""
    coder = ModelScript(
        UnexpectedModelBehavior("Ollama_chatException: failed to parse the tool call")
    )
    reasoning = ModelScript(tool_calls(*NOT_TICKED, TICK), say("Done."))
    trace = ImplementTrace(step="group 1")

    outcome = _step(store, checkout, {CODER: coder, REASONING: reasoning}, trace=trace)

    assert (outcome.status, outcome.repair_rounds) == (StepStatus.DONE, 0)
    assert [(a["number"], a["tier"], a["outcome"], a["strategy"]) for a in _attempts(trace)] == [
        (1, CODER, "failed", "planned"),
        (2, REASONING, "passed", "tier"),
    ]


# ── A shell call through the broker of the step (#3820) ───────────────────────────────────

BROKER_GATEWAY = "https://gateway.example.com/v1"
BROKER_CHAT = f"{BROKER_GATEWAY}/chat/completions"
BROKER_KEY = "gateway-secret-key-3820"
# The answer of the gateway: the provider read 20 of the 120 input tokens from its cache, so the
# budget of the step counts 130 new tokens for the shell call.
BROKER_USAGE = {
    "prompt_tokens": 120,
    "completion_tokens": 30,
    "prompt_tokens_details": {"cached_tokens": 20},
}
SHELL_INPUT, SHELL_CACHED, SHELL_OUTPUT = 120, 20, 30
SHELL_CALL = 'uv run devops ai rag-query "the sample"'


@pytest.fixture
def gateway(config: Callable[..., Path], keyring_store: FakeKeyring) -> None:
    """The gateway as the provider of the step, with its key in the credential store."""
    config(ai={"provider": "gateway", "gateway_url": BROKER_GATEWAY})
    keyring_store.set_password("devops-cli", "ai_api_key", BROKER_KEY)


def _shell_reaches_the_broker(monkeypatch: pytest.MonkeyPatch, *, reach: bool) -> list[str]:
    """The shell of a step: the workspace answers each command with `ran`, and `SHELL_CALL` sends
    one request to the live broker of the step when `reach` is true. The control run reads the same
    text from the shell, so its model sees the messages of the run that calls the broker."""
    calls: list[str] = []

    async def run(self: object, command: str, **options: object) -> CommandResult:
        env = options.get("env")
        if reach and SHELL_CALL in command and isinstance(env, Mapping):
            calls.append(command)
            headers = {"authorization": f"Bearer {env['DEVOPS_CLI_BROKER_TOKEN']}"}
            with httpx2.Client() as shell:
                shell.post(
                    f"{env['DEVOPS_CLI_BROKER_URL']}/chat/completions",
                    headers=headers,
                    content=b'{"model": "devops-coder", "messages": []}',
                )
        return CommandResult(exit_code=0, stdout="ran", stderr="")

    monkeypatch.setattr(LocalWorkspaceBackend, "run", run)
    return calls


def _broker_scripts() -> dict[str, ModelScript]:
    """One shell call on the first tier, which then fails over to the second tier, and the group
    done there."""
    return {
        CODER: ModelScript(
            tool_calls(("run_command", {"command": SHELL_CALL})),
            ModelAPIError("example-model", "The provider broke."),
        ),
        REASONING: ModelScript(tool_calls(*NOT_TICKED, TICK), say("Done.")),
    }


def test_a_shell_call_lands_on_the_tier_of_its_attempt(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    gateway: None,
    web: WebFake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A shell call through the broker counts as a model call of the attempt that ran it: its
    request and its tokens join the record of that tier, its new tokens join the totals of the
    step, and the tier that ran no shell call keeps its own counts (#3820). The control run makes
    the same calls through the same scripts without a request, so the tokens of the model are the
    same in both runs."""
    web.respond("POST", BROKER_CHAT, 200, {"usage": BROKER_USAGE})
    control_calls = _shell_reaches_the_broker(monkeypatch, reach=False)
    control = _step(store, make_checkout(tmp_path / "control"), _broker_scripts())

    calls = _shell_reaches_the_broker(monkeypatch, reach=True)
    outcome = _step(store, checkout, _broker_scripts())

    coder, reasoning = control.tier_spend[CODER], control.tier_spend[REASONING]
    assert (outcome.status, outcome.tiers) == (StepStatus.DONE, (CODER, REASONING))
    assert (control_calls, len(calls)) == ([], 1)
    assert [record.url for record in web.recorded] == [BROKER_CHAT]
    assert outcome.tier_spend[CODER] == coder.model_copy(
        update={
            "requests": coder.requests + 1,
            "input_tokens": coder.input_tokens + SHELL_INPUT,
            "cache_read_tokens": coder.cache_read_tokens + SHELL_CACHED,
            "output_tokens": coder.output_tokens + SHELL_OUTPUT,
        }
    )
    assert outcome.tier_spend[REASONING] == reasoning
    assert (outcome.requests, outcome.input_tokens, outcome.cache_read_tokens) == (
        control.requests + 1,
        control.input_tokens + SHELL_INPUT,
        control.cache_read_tokens + SHELL_CACHED,
    )
    assert new_tokens(outcome) - new_tokens(control) == SHELL_INPUT - SHELL_CACHED + SHELL_OUTPUT
