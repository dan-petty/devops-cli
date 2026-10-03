"""Whether the running command reads a tree it does not own, as a review does (#972).

A review must treat the repository it reads as untrusted (#946): its files may be written to
steer the review. While such a command runs, devops-cli takes nothing from the repository the
working directory is in unless the user named it. The project config layer is not read
(`config.settings`), and a relative data path resolves under the user-level data root rather
than under that repository (`core.repo.resolve_data_path`), so the hallucination catalog, the
review history and baselines, the library contracts and the caches are the user's own. What a
review keeps there, every other command reads and writes there too
(`core.repo.resolve_review_data_path`). A location the user names, `DEVOPS_CLI_CONFIG` or an
absolute data directory, still counts: that is the explicit opt-in.

One repository is exempt: the one whose checkout holds the running devops-cli's own source
(`core.repo.is_own_source_repository`). Its code already runs in this process, so a review
started in it, or in any worktree of it, reads its project config and keeps its data under its
main worktree's `.data`, as before #972.

The root command enters the rule for `devops review` and `devops ai review` before it opens the
command's span (`main._delegate`), since that builds the process's tracer from the config; the
review group enters it as well, for whatever runs the group without the root command.

The state is the process's, not a context variable's. A review's work runs on worker threads,
some of which start without the context of the thread that made them, and a lost flag would read
the reviewed tree's config without a sign. In the MCP server, which runs commands in one process,
a command that runs while a review does reads the user-level config and data too.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_LOCK = threading.Lock()
# How many commands that read a tree they do not own are running in this process.
_RUNNING = 0


@contextmanager
def reading_untrusted_trees() -> Iterator[None]:
    """Mark the process as running a command that reads a tree it does not own, for the block."""
    global _RUNNING
    with _LOCK:
        _RUNNING += 1
    try:
        yield
    finally:
        with _LOCK:
            _RUNNING -= 1


def reads_untrusted_trees() -> bool:
    """Whether the rule holds: a command that reads a tree it does not own is running in this
    process, and the working directory is outside devops-cli's own repository."""
    if _RUNNING == 0:
        return False
    from devops_cli.core.repo import is_own_source_repository

    return not is_own_source_repository()
