"""No commit of the branch names a configured domain: the `domain` row of `devops ci` (#5295,
SECURITY.md rule 8).

The row reads `k8s.domain` and `cloudflare.domain` from the config of the person at run time, so
the value goes into no file of the repository. `git log -p` gives the patch of each commit from
`origin/main` to `HEAD`, and `unidiff` gives the path and the line number of each added line. A
pull request shows each commit of its branch, so the row reads each commit, not only the net diff.

A path or an added line names a domain when it holds the domain, in any case, with no letter, digit
or hyphen just before or just after it: so a name under the domain, such as `api.example.net`, and
a file name such as `grafana.example.net.yaml` name `example.net`, and `notexample.net` and
`example.network` do not. Each finding names the path, the line, the commit and the settings key,
never the value. A path that names a domain is not printed: its finding names the commit only.
"""

from __future__ import annotations

import functools
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping
from typing import Final

from unidiff.errors import UnidiffParseError
from unidiff.patch import Line, PatchedFile, PatchSet

from tests.support.paths import REPO_ROOT

_ROW: Final[str] = "domain"
_RANGE: Final[str] = "origin/main..HEAD"
_RANGE_TEXT: Final[str] = "origin/main to HEAD"
# The fixed options make the output the same for each git config of a person: no color, no
# external diff program, no rename detection, no signature lines and the `a/` and `b/` prefixes
# that `unidiff` strips. `%x00` starts the record of each commit with a NUL, which no text patch
# holds: git shows a file with a NUL as a binary file.
_GIT_LOG: Final[tuple[str, ...]] = (
    "git",
    "log",
    "-p",
    "-U0",
    "--no-color",
    "--no-ext-diff",
    "--no-renames",
    "--no-show-signature",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--format=%x00%H",
    _RANGE,
)
_GIT_TIMEOUT_SECONDS: Final[int] = 60
_ERROR_DETAIL_CHARACTERS: Final[int] = 256
_SHORT_SHA: Final[int] = 12
# A letter, a digit or a hyphen next to the domain makes another name, such as `notexample.net`. A
# dot does not: before the domain it starts a name under it, and after it a file extension.
_NAME_CHARACTERS: Final[str] = "a-z0-9-"


@functools.cache
def _name_pattern(domain: str) -> re.Pattern[str]:
    """The pattern of `domain` with no character of a name just before or just after it."""
    return re.compile(
        rf"(?<![{_NAME_CHARACTERS}]){re.escape(domain)}(?![{_NAME_CHARACTERS}])", re.IGNORECASE
    )


def named_setting(text: str, domains: Mapping[str, str]) -> str | None:
    """The settings key of the first domain of `domains` that `text` names, or None."""
    return next(
        (key for key, domain in domains.items() if _name_pattern(domain).search(text)), None
    )


def _added_lines(patched: PatchedFile) -> Iterator[Line]:
    """Each line that the patch of one file adds."""
    return (line for hunk in patched for line in hunk if line.is_added)


def _commit_findings(sha: str, patch: str, domains: Mapping[str, str]) -> list[str]:
    """The finding of each path and added line of the patch of one commit that names a domain."""
    commit = sha[:_SHORT_SHA]
    found: list[str] = []
    for patched in PatchSet(patch):
        # A commit that removes a file names its old path, which `main` holds already. The removal
        # is the fix, so only the path of a file that stays is a finding.
        if not patched.is_removed_file and (key := named_setting(patched.path, domains)):
            found.append(f"a path in commit {commit} names the value of {key}")
            continue
        found += [
            f"{patched.path}:{line.target_line_no} in commit {commit} names the value of {key}"
            for line in _added_lines(patched)
            if (key := named_setting(line.value, domains))
        ]
    return found


def findings(log: str, domains: Mapping[str, str]) -> list[str]:
    """The finding of each path and added line that names a domain, in the output of `git log`
    with the options of the row. Raises `UnidiffParseError` for a patch that unidiff cannot read."""
    found: list[str] = []
    for record in log.split("\0")[1:]:
        sha, _, patch = record.partition("\n")
        found += _commit_findings(sha, patch, domains)
    return found


def outcome(log: str, domains: Mapping[str, str]) -> tuple[int, list[str]]:
    """The exit status of the row and the lines that it prints, for the output of `git log`.

    The message of `UnidiffParseError` can quote a line of the patch, so that failure prints the
    count of commits only.
    """
    commits = log.count("\0")
    counts = f"commits: {commits}"
    try:
        found = findings(log, domains)
    except UnidiffParseError:
        return 1, [
            f"{_ROW}: unidiff cannot read the patches of the commits from {_RANGE_TEXT} ({counts})."
        ]
    if not found:
        return 0, [f"{_ROW}: the commits from {_RANGE_TEXT} name no configured domain ({counts})."]
    return 1, [
        *(f"{_ROW}: {finding}" for finding in found),
        f"{_ROW}: the commits from {_RANGE_TEXT} name a configured domain (findings: {len(found)}, "
        f"{counts}). Remove each name: write example.com or a role such as <domain>. Then change "
        "each commit that holds a name, because a push publishes each commit.",
    ]


def main(argv: list[str] | None = None) -> int:
    """Read the configured domains and the commits of the branch, print the findings, and return
    1 when there is one."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.dns_names import configured_domains
    from devops_cli.lang import MESSAGES

    domains = configured_domains(load_settings())
    if not domains:
        print(f"{_ROW}: {MESSAGES.ci.domain_not_configured}")
        return 0
    done = subprocess.run(
        list(_GIT_LOG),
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if done.returncode:
        detail = done.stderr.decode("utf-8", "replace")[:_ERROR_DETAIL_CHARACTERS]
        print(f"{_ROW}: git log {_RANGE} failed: {detail}", file=sys.stderr)
        return 1
    status, lines = outcome(done.stdout.decode("utf-8", "replace"), domains)
    for line in lines:
        print(line, file=sys.stderr if status else sys.stdout)
    return status
