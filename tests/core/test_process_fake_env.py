"""Environment validation parity tests for ProcessFake (#5891)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.core import process as process_module
from devops_cli.exceptions import SecurityError
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_run_refuses_denied_environment(process_fake: ProcessFake) -> None:
    """ProcessFake.run refuses a denied key with the same SecurityError as DefaultProcessRunner."""
    with pytest.raises(
        SecurityError,
        match="Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'",
    ):
        process_fake.run(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})


@pytest.mark.asyncio
async def test_run_async_refuses_denied_environment(process_fake: ProcessFake) -> None:
    """ProcessFake.run_async refuses a denied key with SecurityError."""
    with pytest.raises(
        SecurityError,
        match="Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'",
    ):
        await process_fake.run_async(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})


def test_spawn_detached_refuses_denied_environment(process_fake: ProcessFake) -> None:
    """ProcessFake.spawn_detached accepts env and refuses a denied key with SecurityError."""
    with pytest.raises(
        SecurityError,
        match="Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'",
    ):
        process_fake.spawn_detached(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})


@pytest.mark.asyncio
async def test_flags_are_forwarded_and_recorded_on_all_entry_points(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run, run_async, and spawn_detached forward isolate_env and extra_allowed_env and record them."""
    recorded_spy_calls: list[dict[str, Any]] = []
    real_build = process_module.build_subprocess_env

    def spy_build(
        env: dict[str, str] | None = None,
        *,
        isolate_env: bool = True,
        extra_allowed_keys: set[str] | list[str] | frozenset[str] | None = None,
    ) -> dict[str, str]:
        recorded_spy_calls.append(
            {
                "env": env,
                "isolate_env": isolate_env,
                "extra_allowed_keys": set(extra_allowed_keys or ()),
            }
        )
        return real_build(env=env, isolate_env=isolate_env, extra_allowed_keys=extra_allowed_keys)

    monkeypatch.setattr(process_module, "build_subprocess_env", spy_build)

    process_fake.run(
        ["cmd"],
        env={"PATH": "/usr/bin"},
        isolate_env=False,
        extra_allowed_env={"FOO"},
    )
    await process_fake.run_async(
        ["cmd"],
        env={"PATH": "/usr/bin"},
        isolate_env=False,
        extra_allowed_env={"FOO"},
    )
    process_fake.spawn_detached(
        ["cmd"],
        env={"PATH": "/usr/bin"},
        isolate_env=False,
        extra_allowed_env={"FOO"},
    )

    assert recorded_spy_calls == [
        {"env": {"PATH": "/usr/bin"}, "isolate_env": False, "extra_allowed_keys": {"FOO"}},
        {"env": {"PATH": "/usr/bin"}, "isolate_env": False, "extra_allowed_keys": {"FOO"}},
        {"env": {"PATH": "/usr/bin"}, "isolate_env": False, "extra_allowed_keys": {"FOO"}},
    ]
    assert [
        (call.isolate_env, call.extra_allowed_env, call.env) for call in process_fake.calls
    ] == [
        (False, frozenset({"FOO"}), {"PATH": "/usr/bin"}),
        (False, frozenset({"FOO"}), {"PATH": "/usr/bin"}),
        (False, frozenset({"FOO"}), {"PATH": "/usr/bin"}),
    ]


def test_allowed_environment_returns_scripted_answer_and_records_caller_env(
    process_fake: ProcessFake,
) -> None:
    """An allowed env passes build_subprocess_env and preserves the scripted answer and raw env."""
    process_fake.answer(["cmd"], ProcessAnswer(returncode=0, stdout="ok"))

    result = process_fake.run(["cmd"], env={"PATH": "/usr/bin"})

    assert result.returncode == 0
    assert result.stdout == "ok"
    assert process_fake.calls[-1].env == {"PATH": "/usr/bin"}
