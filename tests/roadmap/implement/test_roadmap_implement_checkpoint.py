"""The implement job pushes each passed group to the item branch and withdraws the pushes when a
premise returns the item (#3677).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges. A runner that is killed is read from `origin` at the
first request of the group that follows: the pod is gone and the job pushes nothing more.
"""

from __future__ import annotations

import stat
from collections.abc import Callable

import pytest
from pydantic_ai.exceptions import ModelAPIError

from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.github import github_json
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    PULL,
    TASKS_PATH,
    JobWorld,
)
from tests.support.roadmap_stage import STAGE_REPO, run_git

pytestmark = pytest.mark.usefixtures("keyring_store")

GROUPS = 4
FILES = [f"src/devops_cli/g{n}.py" for n in range(1, GROUPS + 1)]
BASE_KEY = "implement.base"
REFUSE = "refuse-pushes"
PREMISE_REQUEST = (
    "```plan-request\n"
    "{\n"
    '  "kind": "premise",\n'
    '  "group": 3,\n'
    '  "defect": "the premise is false",\n'
    '  "evidence": "upstream removed the API"\n'
    "}\n"
    "```"
)


def _tasks() -> str:
    """A change of four groups of one task each. The task of a group writes one file."""
    groups = "".join(
        f"## {n}. The file {n}\n\n"
        f"Reads: `CONTEXT.md`. Changes: `{FILES[n - 1]}` (new), `tests/test_g{n}.py` (new).\n\n"
        f"- [ ] {n}.1 Add `{FILES[n - 1]}`\n"
        f"  - Verification: `$ uv run devops ci test tests/test_g{n}.py`\n\n"
        for n in range(1, GROUPS + 1)
    )
    criteria = "".join(f"- Group {n}: The job keeps every comment.\n" for n in range(1, GROUPS + 1))
    return f"# Tasks\n\n{groups}## Criteria\n\n{criteria}"


TASKS = _tasks()


@pytest.fixture
def staged_tasks() -> str:
    return TASKS


@pytest.fixture
def planned_tasks() -> str:
    return TASKS


@pytest.fixture(params=["staged", "planned"])
def world(request: pytest.FixtureRequest) -> JobWorld:
    """The job in a runner, once with a Staged item and once with a Planned item."""
    name = "job_world" if request.param == "staged" else "planned_world"
    world: JobWorld = request.getfixturevalue(name)
    return world


def _ticked(count: int) -> str:
    return TASKS.replace("- [ ]", "- [x]", count)


def _passes(first: int, last: int) -> list[object]:
    """The replies of a model that passes the groups `first` to `last`: the files, the tick, and
    the word that ends the step."""
    replies: list[object] = []
    for number in range(first, last + 1):
        replies.append(
            tool_calls(
                ("write_file", {"path": FILES[number - 1], "content": f"VALUE = {number}\n"}),
                ("write_file", {"path": TASKS_PATH, "content": _ticked(number)}),
            )
        )
        replies.append(say(f"Group {number} is done."))
    return replies


def _script(*replies: object, **effects: Callable[[], None]) -> ModelScript:
    """A script of `replies`. An effect is named `at<request>`."""
    numbered = {int(name.removeprefix("at")): effect for name, effect in effects.items()}
    return ModelScript(*replies, effects=numbered)  # type: ignore[arg-type]


def _killed_in_group_three(world: JobWorld, seen: list[list[str]]) -> ModelScript:
    """Groups 1 and 2 pass, and the pod dies in group 3. The effect reads `origin` at the first
    request of group 3."""
    return _script(
        *_passes(1, 2),
        ModelAPIError("example-model", "The pod died."),
        at5=lambda: seen.append(_groups_on_origin(world)),
    )


def _groups_on_origin(world: JobWorld) -> list[str]:
    """The files of the groups that the item branch of `origin` holds, in order."""
    if not world.repo.origin_git("branch", "--list", BRANCH):
        return []
    names = world.repo.origin_git("diff", "--name-only", f"main..{BRANCH}").splitlines()
    return sorted(name for name in names if name in FILES)


def _item(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def _pushes(world: JobWorld) -> list[tuple[str, ...]]:
    """Every `git push` of the job."""
    return [
        call.argv for call in world.programs.calls if call.argv[0] == "git" and "push" in call.argv
    ]


def _pull_requests_asked(world: JobWorld) -> int:
    return len(world.sent("POST", "pulls"))


def _claim(world: JobWorld) -> Callable[[], None]:
    """What a person does on GitHub: label the item."""
    return lambda: world.store.as_actor("alice").add_label(1, "owner/human")


def _person_pushes(world: JobWorld) -> Callable[[], None]:
    """A person adds a commit to the item branch of `origin`, from a clone of their own: a fetch in
    the clone of the job would move the tracking ref that the job holds its lease on."""

    def push() -> None:
        own = world.repo.origin.parent / "person"
        run_git(own.parent, "clone", "-q", "--branch", BRANCH, str(world.repo.origin), str(own))
        (own / "person.txt").write_text("A person was here.\n", encoding="utf-8")
        run_git(own, "add", "-A")
        run_git(
            own, "-c", "user.name=Person", "-c", "user.email=person@example.com",
            "commit", "-q", "-m", "A person pushes",
        )  # fmt: skip
        run_git(own, "push", "-q", "origin", BRANCH)

    return push


def _origin_refuses_pushes(world: JobWorld) -> tuple[Callable[[], None], Callable[[], None]]:
    """The two switches of an `origin` whose hook refuses each push while the file exists: one
    that turns the refusal on, one that turns it off."""
    origin = world.repo.origin
    hook = origin / "hooks" / "pre-receive"
    hook.write_text(
        f'#!/bin/sh\nif [ -e "{origin / REFUSE}" ]; then echo "refused by the test" >&2; exit 1; fi\n',
        encoding="utf-8",
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    marker = origin / REFUSE
    return (lambda: marker.write_text("", encoding="utf-8")), (lambda: marker.unlink())


def _refuse_the_draft(world: JobWorld) -> None:
    """GitHub refuses to open the draft pull request."""
    world.api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"message": "Validation Failed"}, status=422),
    )


# ── The checkpoint ────────────────────────────────────────────────────────────────────────


def test_a_runner_killed_after_two_of_four_groups_leaves_both_groups_on_origin(
    world: JobWorld,
) -> None:
    seen: list[list[str]] = []

    applied = world.run(_killed_in_group_three(world, seen))

    assert applied.stopped == (1,)
    assert seen == [FILES[:2]]


def test_a_planned_item_opens_one_draft_at_the_first_checkpoint(planned_world: JobWorld) -> None:
    asked: list[int] = []
    script = _script(
        *_passes(1, 2),
        ModelAPIError("example-model", "The pod died."),
        at3=lambda: asked.append(_pull_requests_asked(planned_world)),
        at5=lambda: asked.append(_pull_requests_asked(planned_world)),
    )

    planned_world.run(script)

    assert asked == [1, 1]
    assert _pull_requests_asked(planned_world) == 1


def test_a_second_job_runs_only_the_groups_that_are_left(world: JobWorld) -> None:
    world.run(_killed_in_group_three(world, []))
    world.store.seed_comment(1, "implement: retry", author_association="OWNER")
    held = world.store.item(1)
    assert held is not None
    # The Service clears the stop and puts the item back to Ready (`clear_stops`).
    world.store.set_field(held, ItemField.STATUS, "Ready")
    second = _script(*_passes(3, 4))

    applied = world.run(second)

    first_message = [str(getattr(part, "content", "")) for part in second.seen[0][-1].parts][-1]
    group = first_message.split("# Your group")[1].split("# The tasks file")[0]
    assert applied.ready == (1,)
    assert ("- [ ] 3.1" in group, "1.1" in group, len(second.seen)) == (True, False, 4)
    assert _groups_on_origin(world) == FILES


def test_the_end_boundary_pushes_nothing(world: JobWorld) -> None:
    seen: list[list[str]] = []
    script = _script(*_passes(1, GROUPS), at7=lambda: seen.append(_groups_on_origin(world)))

    applied = world.run(script)

    assert applied.ready == (1,)
    assert seen == [FILES[:3]]
    # The checkpoints of groups 1 to 3 and the final push. The end boundary adds none.
    assert len(_pushes(world)) == GROUPS


# ── The claim ─────────────────────────────────────────────────────────────────────────────


def test_a_claim_seen_at_a_boundary_pushes_nothing_at_that_boundary(world: JobWorld) -> None:
    script = _script(*_passes(1, 2), at2=_claim(world))

    applied = world.run(script)

    assert (applied.yielded, applied.ready, applied.stopped) == ((1,), (), ())
    assert _groups_on_origin(world) == []
    assert (_pull_requests_asked(world), world.pull.ready_calls) == (0, [])


def test_a_claim_during_group_two_keeps_group_one_and_pushes_nothing_more(
    world: JobWorld,
) -> None:
    staged = _staged(world)
    script = _script(*_passes(1, 3), at3=_claim(world))

    applied = world.run(script)

    status, record = _item(world)
    assert (applied.yielded, applied.ready, applied.stopped) == ((1,), (), ())
    assert _groups_on_origin(world) == FILES[:1]
    assert (record.get("implement.stopped"), status) == (None, "In Progress")
    # A Planned item keeps its draft: one request opened it, and none closed it.
    assert world.sent("PATCH", f"pulls/{PULL}") == []
    assert _pull_requests_asked(world) == (0 if staged else 1)


# ── The base ──────────────────────────────────────────────────────────────────────────────


def test_the_base_is_written_once_and_cleared_at_ready(world: JobWorld) -> None:
    start = world.repo.origin_git("rev-parse", BRANCH) if _staged(world) else "new"
    during: list[str | None] = []
    first = _script(
        *_passes(1, 2),
        ModelAPIError("example-model", "The pod died."),
        at1=lambda: during.append(_item(world)[1].get(BASE_KEY)),
        at5=lambda: during.append(_item(world)[1].get(BASE_KEY)),
    )
    world.run(first)
    world.store.seed_comment(1, "implement: retry", author_association="OWNER")
    held = world.store.item(1)
    assert held is not None
    world.store.set_field(held, ItemField.STATUS, "Ready")
    second = _script(*_passes(3, 4), at1=lambda: during.append(_item(world)[1].get(BASE_KEY)))

    applied = world.run(second)

    assert during == [start, start, start]
    assert applied.ready == (1,)
    assert _item(world)[1].get(BASE_KEY) is None


def _staged(world: JobWorld) -> bool:
    return bool(world.repo.origin_git("branch", "--list", BRANCH))


# ── The withdraw ──────────────────────────────────────────────────────────────────────────


def test_a_false_premise_after_two_checkpoints_withdraws_them(world: JobWorld) -> None:
    before = world.repo.origin_git("rev-parse", BRANCH) if _staged(world) else ""
    seen: list[list[str]] = []
    script = _script(
        *_passes(1, 2),
        say(PREMISE_REQUEST),
        at5=lambda: seen.append(_groups_on_origin(world)),
    )

    applied = world.run(script)

    status, record = _item(world)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())
    assert seen == [FILES[:2]]
    assert (status, record.get(BASE_KEY), record.get("implement.group")) == ("New", None, None)
    if before:
        assert world.repo.origin_git("rev-parse", BRANCH) == before
    else:
        assert world.repo.origin_git("branch", "--list", BRANCH) == ""
        assert world.sent("PATCH", f"pulls/{PULL}") == [{"state": "closed"}]


def test_a_person_who_pushes_before_the_withdraw_keeps_the_push_and_blocks_the_item(
    world: JobWorld,
) -> None:
    script = _script(*_passes(1, 2), say(PREMISE_REQUEST), at5=_person_pushes(world))

    applied = world.run(script)

    status, record = _item(world)
    assert (applied.stopped, applied.ready) == ((1,), ())
    assert status == "Blocked"
    assert record.get("implement.stopped") is not None
    assert "person.txt" in world.repo.origin_git("ls-tree", "-r", "--name-only", BRANCH)
    assert _groups_on_origin(world) == FILES[:2]


def test_a_withdraw_that_fails_blocks_the_item_and_does_not_return_it(world: JobWorld) -> None:
    refuse, _allow = _origin_refuses_pushes(world)
    script = _script(*_passes(1, 2), say(PREMISE_REQUEST), at5=refuse)

    applied = world.run(script)

    status, record = _item(world)
    assert (applied.stopped, applied.ready) == ((1,), ())
    assert status == "Blocked"
    assert record.get("implement.stopped") is not None
    assert _groups_on_origin(world) == FILES[:2]


class TestAGuardThatTheBranchTipDefines:
    """Group 3 is a behavior group whose task adds a guard that the default branch defines
    (#3417). The check returns the item at the boundary of group 3, after the checkpoint of
    group 1."""

    GUARD = "_delivery_title"
    TITLES = f'"""The titles."""\n\n\ndef {GUARD}(text: str) -> str:\n    return text.strip()\n'

    @staticmethod
    def _guard_tasks() -> str:
        files = "".join(
            f"## {n}. The file {n}\n\n"
            f"Reads: `CONTEXT.md`. Changes: `{FILES[n - 1]}` (new), `tests/test_g{n}.py` (new).\n\n"
            f"- [ ] {n}.1 Add `{FILES[n - 1]}`\n"
            f"  - Verification: `$ uv run devops ci test tests/test_g{n}.py`\n\n"
            for n in (1, 2)
        )
        behavior = (
            "## 3. The guard\n\n"
            "Reads: `CONTEXT.md`. Changes: `tests/test_g3.py` (new), `src/devops_cli/g3.py` (new).\n\n"
            "- [ ] 3.1 Add the failing test `tests/test_g3.py` for `src/devops_cli/g3.py`\n"
            "  - Verification: `$ uv run devops ci test tests/test_g3.py` fails on the base\n"
            "- [ ] 3.2 Add the guard `_delivery_title` to `src/devops_cli/g3.py`\n"
            "  - Verification: `$ uv run devops ci test tests/test_g3.py`\n\n"
        )
        criteria = "".join(f"- Group {n}: The job keeps every comment.\n" for n in (1, 2, 3))
        return f"# Tasks\n\n{files}{behavior}## Criteria\n\n{criteria}"

    @pytest.fixture
    def staged_tasks(self) -> str:
        return self._guard_tasks()

    @pytest.fixture
    def planned_tasks(self) -> str:
        return self._guard_tasks()

    def test_the_check_withdraws_the_checkpoint_of_group_one(self, world: JobWorld) -> None:
        world.repo.track(
            {"tests/conftest.py": '"""The tests."""\n', "src/devops_cli/titles.py": self.TITLES}
        )
        before = world.repo.origin_git("rev-parse", BRANCH) if _staged(world) else ""
        ticked_two = self._guard_tasks().replace("- [ ]", "- [x]", 1)
        script = _script(
            tool_calls(
                ("write_file", {"path": FILES[0], "content": "VALUE = 1\n"}),
                ("write_file", {"path": TASKS_PATH, "content": ticked_two}),
            ),
            say("Group 1 is done."),
            tool_calls(
                ("write_file", {"path": FILES[1], "content": "VALUE = 2\n"}),
                (
                    "write_file",
                    {"path": TASKS_PATH, "content": ticked_two.replace("- [ ]", "- [x]", 1)},
                ),
            ),
            say("Group 2 is done."),
        )

        applied = world.run(script)

        status, record = _item(world)
        (comment,) = world.issue_comments()
        assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())
        assert (status, record.get(BASE_KEY), len(script.seen)) == ("New", None, 4)
        assert self.GUARD in comment
        # The checkpoint of group 1 and the withdraw: two pushes, then no group on origin.
        assert len(_pushes(world)) == 2
        if before:
            assert world.repo.origin_git("rev-parse", BRANCH) == before
        else:
            assert world.repo.origin_git("branch", "--list", BRANCH) == ""
            assert world.sent("PATCH", f"pulls/{PULL}") == [{"state": "closed"}]


# ── A push that fails ─────────────────────────────────────────────────────────────────────


def test_a_failed_checkpoint_push_does_not_stop_the_run_and_ends_the_checkpoints(
    world: JobWorld,
) -> None:
    refuse, allow = _origin_refuses_pushes(world)
    refuse()
    before_final: list[int] = []

    def let_the_final_push_through() -> None:
        before_final.append(len(_pushes(world)))
        allow()

    script = _script(*_passes(1, GROUPS), at5=let_the_final_push_through)

    applied = world.run(script)

    assert applied.ready == (1,)
    # One refused checkpoint at the boundary of group 2, none at the boundaries of groups 3 and 4,
    # and the final push.
    assert before_final == [1]
    assert len(_pushes(world)) == 2


def test_a_draft_that_github_refuses_is_asked_for_once_and_ends_the_checkpoints(
    planned_world: JobWorld,
) -> None:
    _refuse_the_draft(planned_world)
    asked: list[int] = []
    script = _script(
        *_passes(1, GROUPS), at5=lambda: asked.append(_pull_requests_asked(planned_world))
    )

    applied = planned_world.run(script)

    status, _record = _item(planned_world)
    assert asked == [1]
    # The final push asks again, and the refusal stops the item as it does without a checkpoint.
    assert (applied.stopped, applied.ready, status) == ((1,), (), "Blocked")
    assert _pull_requests_asked(planned_world) == 2


def test_a_withdraw_after_a_refused_draft_finds_no_branch_and_does_nothing(
    planned_world: JobWorld,
) -> None:
    _refuse_the_draft(planned_world)
    script = _script(*_passes(1, 2), say(PREMISE_REQUEST))

    applied = planned_world.run(script)

    status, record = _item(planned_world)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())
    assert (status, record.get(BASE_KEY)) == ("New", None)
    assert _pull_requests_asked(planned_world) == 1
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert planned_world.sent("PATCH", f"pulls/{PULL}") == []
