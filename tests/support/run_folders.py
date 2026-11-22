"""A run folder as the container `publish` mounts it (#3700): the root, `state/` and `out/` are
read-only, so a phase that writes into the run folder fails as it does in the cluster."""

from __future__ import annotations

import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from devops_cli.roadmap.phases.files import RunFolders

_READ_ONLY = stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH


@contextmanager
def read_only_run(folders: RunFolders, *also: Path) -> Iterator[RunFolders]:
    """`folders` with the root, `state/` and `out/` made read-only, and each folder of `also`,
    and their modes given back at the end, so `tmp_path` can be removed."""
    held = [path for path in (folders.out, folders.state, folders.root, *also) if path.is_dir()]
    modes = {path: path.stat().st_mode for path in held}
    for path in held:
        path.chmod(_READ_ONLY)
    try:
        yield folders
    finally:
        for path in reversed(held):
            path.chmod(modes[path])
