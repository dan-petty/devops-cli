"""The work in progress of a step (#3054).

A step runs one task group, and a stopped step resets the checkout. Without this module the
minutes of work in a group would go with the reset. The step keeps what is green: when the agent
ticks a task and the verification commands of that task pass, `WipKeeper` commits the checkout as
a `wip:` commit and tells the job, which pushes it. A stop then resets to the last `wip:` commit,
not to the start of the step, so a tick that the job verified stays on the branch and the next
attempt runs only the tasks that are not ticked.

The job owns `tasks.md`, so the commit holds the file as it was before the run with the ticks that
the job verified, never the text of the agent. After the commit, the file has the text of the agent
again. A step that ends done folds the `wip:` commits into its own commit (`fold`), so a finished
group is one commit, as it was before. The commits of a stopped step stay on the branch, and the
squash merge removes them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_WIP_PREFIX
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.step_files import (
    CHECKBOXES,
    GroupTask,
    TaskGroup,
    file_lines,
    parse_task_groups,
)

# Runs git in the checkout and returns what it printed. It raises when git fails.
GitOutput = Callable[..., str]
# The reason that some commands fail, or None when all of them pass.
Verify = Callable[[Sequence[str]], str | None]
_FIELD_SEPARATOR = "\x1f"
_LOOK_BACK = "200"


@dataclass(frozen=True)
class WipCommit:
    """A work-in-progress commit: the group, the tasks done, the tasks of the group, and the commit."""

    group: int
    done: int
    total: int
    sha: str


def wip_base(git: GitOutput) -> str:
    """The last commit of the first-parent line of `HEAD` that is no `wip:` commit. A checkout with
    no `wip:` commit gives `HEAD`."""
    listed = git("log", "--first-parent", "--format=%H" + _FIELD_SEPARATOR + "%s", "-n", _LOOK_BACK)
    sha = ""
    for line in listed.splitlines():
        sha, _, subject = line.partition(_FIELD_SEPARATOR)
        if not subject.startswith(CONST_ROADMAP_IMPLEMENT_WIP_PREFIX):
            return sha
    return sha


def kept_commits(git: GitOutput, upstream: str) -> list[str]:
    """The `wip:` commits between `upstream` and `HEAD`, the newest first."""
    listed = git("log", "--format=%H" + _FIELD_SEPARATOR + "%s", f"{upstream}..HEAD")
    pairs = (line.partition(_FIELD_SEPARATOR) for line in listed.splitlines())
    return [
        sha for sha, _, subject in pairs if subject.startswith(CONST_ROADMAP_IMPLEMENT_WIP_PREFIX)
    ]


@dataclass
class WipKeeper:
    """Commits the green tasks of one step. `before` is the text of the `tasks.md` before the run,
    `group` is the group as that text has it, `item` is the issue number, `git` runs git in the
    checkout, `verify` runs the verification commands of a task, and `strays` lists the stray files
    of the group, which no commit holds. `blocked` says why the staged work must not be kept (a test
    that existed at the start is lost), or None. `on_commit` tells the job of each commit.

    `tip` is the commit that a stop resets to: the last `wip:` commit, or the commit that the step
    started at. `base` is the last commit that is no `wip:` commit. The exit checks of the step
    judge everything since `base`, so `fold` puts the `wip:` commits back into the index first, and
    `folded` says that `HEAD` is `base`."""

    source: Path
    tasks_file: Path
    group: TaskGroup
    before: str
    item: int
    git: GitOutput
    verify: Verify
    strays: Callable[[], list[str]]
    blocked: Callable[[], str | None]
    on_commit: Callable[[WipCommit], None] | None = None
    tip: str = ""
    base: str = ""
    folded: bool = False
    kept: set[int] = field(default_factory=set[int])
    commits: int = 0
    _stamp: int = field(default=-1, init=False, repr=False)

    def __post_init__(self) -> None:
        self.tip = self.git("rev-parse", "HEAD").strip()
        self.base = wip_base(self.git)
        self._stamp = self._mtime()

    @property
    def expected_head(self) -> str:
        """The commit that `HEAD` must be at: no commit of the agent may move it."""
        return self.base if self.folded else self.tip

    def _mtime(self) -> int:
        try:
            return self.tasks_file.stat().st_mtime_ns
        except OSError:
            return -1

    def _own_tasks(self, text: str) -> tuple[GroupTask, ...] | None:
        """The tasks of the own group in `text`, or None when the group is gone or has another
        number of tasks than before the run: a tick has no meaning then."""
        found = next((g for g in parse_task_groups(text) if g.number == self.group.number), None)
        if found is None or len(found.tasks) != len(self.group.tasks):
            return None
        return found.tasks

    def _canonical(self) -> str:
        """The text before the run with the ticks that the job verified."""
        lines = file_lines(self.before)
        for index in self.kept:
            number = self.group.tasks[index].line
            lines[number] = lines[number].replace(CHECKBOXES[0], CHECKBOXES[1], 1)
        return "".join(lines)

    def _fresh(self, tasks: tuple[GroupTask, ...]) -> list[int]:
        """The tasks that the agent ticked and that the job has not kept."""
        return [
            index
            for index, (was, now) in enumerate(zip(self.group.tasks, tasks, strict=True))
            if now.ticked and not was.ticked and index not in self.kept
        ]

    def _stage(self) -> list[str]:
        """Stage the checkout except the stray files, and give their names."""
        strays = self.strays()
        self.git("add", "-A")
        if strays:
            self.git("reset", "-q", "--", *strays)
        return strays

    def _green(self, fresh: list[int]) -> list[int]:
        """The tasks of `fresh` whose verification commands pass, and none when the staged work
        must not be kept (`blocked`)."""
        if self.blocked() is not None:
            return []
        return [
            index for index in fresh if self.verify(self.group.tasks[index].verification) is None
        ]

    def check(self) -> None:
        """Commit the tasks that the agent ticked since the last call and that pass their
        verification. It reads the file only when it changed. It does nothing for a step that
        ticks no task. Raises when git fails."""
        stamp = self._mtime()
        if stamp == self._stamp:
            return
        self._stamp = stamp
        try:
            text = self.tasks_file.read_text(encoding="utf-8", newline="")
        except OSError, UnicodeDecodeError:
            return
        tasks = self._own_tasks(text)
        if tasks is None or not (fresh := self._fresh(tasks)):
            return
        self.unfold()
        self._stage()
        green = self._green(fresh)
        if not green:
            self.git("reset", "-q")
            return
        self.kept.update(green)
        self._commit(text)

    def _commit(self, agent_text: str) -> None:
        """Commit the checkout, with the `tasks.md` that the job owns, and give the file back to
        the agent as it wrote it."""
        self.tasks_file.write_text(self._canonical(), encoding="utf-8", newline="")
        done = len(self.kept) + sum(task.ticked for task in self.group.tasks)
        total = len(self.group.tasks)
        message = MESSAGES.roadmap.implement_wip_commit.format(
            prefix=CONST_ROADMAP_IMPLEMENT_WIP_PREFIX,
            done=done,
            total=total,
            group=self.group.number,
            title=self.group.title,
            item=self.item,
        )
        self._stage()
        self.git("commit", "-q", "-m", message)
        self.tasks_file.write_text(agent_text, encoding="utf-8", newline="")
        self._stamp = self._mtime()
        self.tip = self.git("rev-parse", "HEAD").strip()
        self.commits += 1
        if self.on_commit is not None:
            self.on_commit(WipCommit(self.group.number, done, total, self.tip))

    def fold(self) -> None:
        """Put the `wip:` commits back into the index, so that the exit checks and the commit of
        the step see all the work since `base`. The checkout and the index stay as they are."""
        if not self.folded and self.tip != self.base:
            self.git("reset", "--soft", self.base)
        self.folded = True

    def unfold(self) -> None:
        """Undo `fold`: `HEAD` goes back to `tip` and the index stays as it is."""
        if self.folded and self.tip != self.base:
            self.git("reset", "--soft", self.tip)
        self.folded = False

    def discard(self) -> None:
        """Reset the checkout to `tip`: the work after the last `wip:` commit goes, the `wip:`
        commits stay."""
        self.git("reset", "--hard", self.tip)
        self.git("clean", "-fd")
        self.folded = False
