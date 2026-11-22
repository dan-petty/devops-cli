"""The disk use of the worktree and the home of a runner Job, and the by-products of a step
(#6076).

The kubelet evicts the pod of a runner Job when one of its emptyDir volumes goes over the
`sizeLimit` of `k8s/devops/cronjob-runner.yaml`. The eviction stops the Job at once, so the Job
writes no line about what filled the volume. The worktree holds the clone and its venv, and the
home holds the cache of uv and the files that the steps write. They are on one volume in a
template of one container, and on two on the three containers of #3700: the run folder and the
home of `agent`.

- `log_disk_use` writes one line to the Job log: the use of the volumes and their largest
  folders. It reads `du -x -B1 -d 1 <worktree> <home>`, the bytes on the disk of each folder, as
  the kubelet counts them. du counts a folder once, at the first argument that holds it. So the
  folders of the worktree come first, named `worktree/<name>`, and the folders of home hold the
  rest. The line goes to the console stream, as the lines of the tool calls do
  (`implement_tool_log`), so it reaches the Job log. Outside a runner
  Job, home is the home of a person and not a volume of the Job, and the function reads nothing.
- `remove_by_products` removes the files that the agent of a step leaves in the worktree and that
  git ignores, so neither the commit nor the reset of the step removes them: the tree of a
  mutation run of its own (`mutants/`) and the files of its scratch folder. Each step is a new
  conversation, so no later step reads them.
- `end_step` does both, in that order, so the line names what the step wrote.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.commands import BIN_DU
from devops_cli.config.constants import (
    CONST_MUTMUT_TREE_DIR,
    CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.output.formatters.scalars import format_bytes

# The label of the folders of the worktree in the line, before the name of each.
_WORKTREE_LABEL = "worktree/"
# The most folders that the line names, largest first. The worktree and the home hold about 8 of
# note: the clone, the venv, the uv cache, `mutants/`, the scratch folder and the caches of the
# checks.
_FOLDERS = 8


@dataclass(frozen=True)
class DiskUse:
    """The bytes on the disk of the worktree and the home, and their largest folders with their
    labels and bytes, largest first."""

    total: int
    folders: tuple[tuple[str, int], ...]


def read_disk_use(worktree: Path, home: Path) -> DiskUse:
    """The use of `worktree` and `home` together, from one run of `du`.

    du exits 1 when it cannot read a file, such as a file that a process removes while du runs,
    and it still prints the other folders. So the function reads the lines and not the status.
    """
    command = [BIN_DU, "-x", "-B1", "-d", "1", str(worktree), str(home)]
    done = run_subprocess(command, quiet=True, local_read=True)
    labels = {worktree: _WORKTREE_LABEL, home: ""}
    total = 0
    folders: list[tuple[str, int]] = []
    for line in (done.stdout or "").splitlines():
        size, _, name = line.partition("\t")
        path = Path(name)
        if path in labels:
            total += int(size)
        elif path.parent in labels:
            folders.append((f"{labels[path.parent]}{path.name}", int(size)))
    folders.sort(key=lambda folder: folder[1], reverse=True)
    return DiskUse(total, tuple(folders[:_FOLDERS]))


def log_disk_use(worktree: Path, step: str) -> None:
    """Write the use of the worktree and the home at the end of `step` to the Job log, in a
    runner Job. On the three containers they are on two volumes, the run folder and the home of
    `agent` (#3700)."""
    if not load_settings().roadmap.implement.in_runner:
        return
    use = read_disk_use(worktree, Path.home())
    if not use.total:
        return
    folders = ", ".join(f"{label} {format_bytes(size)}" for label, size in use.folders)
    line = MESSAGES.roadmap.implement_disk_use.format(
        step=step, total=format_bytes(use.total), folders=folders
    )
    print_muted(line, to_stderr=True, safe=True)


def _remove(path: Path) -> bool:
    """Remove the folder, file or link `path`, and say whether there was one. A link goes, not
    the folder that it points to."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.is_symlink() or path.exists():
        path.unlink()
    else:
        return False
    return True


def remove_by_products(worktree: Path) -> None:
    """Remove the tree `mutants/` of `worktree`, and empty its scratch folder."""
    _remove(worktree / CONST_MUTMUT_TREE_DIR)
    scratch = worktree / CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR
    if _remove(scratch):
        scratch.mkdir(parents=True)


def end_step(worktree: Path, step: str) -> None:
    """At the end of `step`: write the disk use line, then remove the by-products of the step."""
    log_disk_use(worktree, step)
    remove_by_products(worktree)
