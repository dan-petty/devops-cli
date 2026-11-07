"""The one registry of the tools of every roadmap job and MCP role (#3244).

Three hosts choose the tools of a model that works on the project: the stage planner, the implement
step and the MCP role servers. `TOOLS` names each tool once, with its one-line purpose, its
read-only flag and the holders that name it. A holder is one table of a host: the toolsets `stage`,
`stage-extended` and `implement`, and the MCP job roles `planning`, `implementation` and `review`.
`tool_names` gives the names of one holder in table order, and `check_tables` reports each name of
any table that the registry lacks. The stage tools and the MCP role tables read their names here,
so a name that leaves the table leaves every host, and a name that joins it joins the hosts that
its holders name.

The table holds no function: the stage tools are methods of `StageTools`, the implement tools are
capabilities of the harness `Coder`, and the role tools are generated from the commands of the CLI,
so no single callable exists for each name. The table unifies the names, the purposes and the
flags.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

HOLDER_STAGE: Final = "stage"
HOLDER_STAGE_EXTENDED: Final = "stage-extended"
HOLDER_IMPLEMENT: Final = "implement"
HOLDER_PLANNING: Final = "planning"
HOLDER_IMPLEMENTATION: Final = "implementation"
HOLDER_REVIEW: Final = "review"

# The tables that name tools: the three toolsets and the three MCP job roles.
HOLDERS: Final[tuple[str, ...]] = (
    HOLDER_STAGE,
    HOLDER_STAGE_EXTENDED,
    HOLDER_IMPLEMENT,
    HOLDER_PLANNING,
    HOLDER_IMPLEMENTATION,
    HOLDER_REVIEW,
)

_STAGE: Final[frozenset[str]] = frozenset({HOLDER_STAGE, HOLDER_STAGE_EXTENDED})
_STAGE_EXTENDED: Final[frozenset[str]] = frozenset({HOLDER_STAGE_EXTENDED})
_IMPLEMENT: Final[frozenset[str]] = frozenset({HOLDER_IMPLEMENT})
_EVERY_JOB_ROLE: Final[frozenset[str]] = frozenset(
    {HOLDER_PLANNING, HOLDER_IMPLEMENTATION, HOLDER_REVIEW}
)
_PLANNING: Final[frozenset[str]] = frozenset({HOLDER_PLANNING})
_IMPLEMENTATION: Final[frozenset[str]] = frozenset({HOLDER_IMPLEMENTATION})


@dataclass(frozen=True)
class ToolEntry:
    """One tool of the registry: the one-line purpose that a person reads, the holders that name
    the tool, and whether it changes anything. The key of `TOOLS` is the name of the tool."""

    purpose: str
    holders: frozenset[str]
    read_only: bool


def _read(purpose: str, holders: frozenset[str]) -> ToolEntry:
    """An entry of a tool that changes no file and runs no program."""
    return ToolEntry(purpose, holders, read_only=True)


def _write(purpose: str, holders: frozenset[str]) -> ToolEntry:
    """An entry of a tool that writes a file or runs a program."""
    return ToolEntry(purpose, holders, read_only=False)


TOOLS: Final[dict[str, ToolEntry]] = {
    # The nine tools of the toolset `stage`, which `stage-extended` also holds (#3037). The first
    # two serve the implement step too, so their purpose fits both hosts.
    "list_files": _read("Lists the files and directories under a directory.", _STAGE),
    "read_file": _read("Reads the numbered lines of a file.", _STAGE),
    "search_code": _read(
        "Finds a text in the files of the staged commit and lists each match with its line.",
        _STAGE,
    ),
    "git_log": _read("Lists the newest commits that changed a path of the staged commit.", _STAGE),
    "git_show": _read("Shows the message and the diff of one commit of the history.", _STAGE),
    "file_symbols": _read(
        "Lists the classes, functions and methods of one source file, with their lines.", _STAGE
    ),
    "callers": _read("Lists the places that call a function, a method or a class.", _STAGE),
    "repo_map": _read(
        "Maps the Python files under a directory, with the names of their top-level symbols.",
        _STAGE,
    ),
    "read_spec": _read("Reads a base spec of the project, or one requirement of it.", _STAGE),
    # The three tools that `stage-extended` adds (#3238).
    "references": _read(
        "Lists every file of the commit that holds a text, with the count of lines in each.",
        _STAGE_EXTENDED,
    ),
    "read_issue": _read(
        "Reads one issue or pull request of the repository on GitHub.", _STAGE_EXTENDED
    ),
    "find_issues": _read(
        "Lists the open issues and pull requests of the repository that name some words.",
        _STAGE_EXTENDED,
    ),
    # The tools that the implement step adds to the harness `Coder`.
    "write_file": _write("Writes the whole text of a file of the workspace.", _IMPLEMENT),
    "edit_file": _write(
        "Replaces a text in a file of the workspace with another text.", _IMPLEMENT
    ),
    "grep": _read(
        "Finds a text in the files of the workspace and lists each match with its line.", _IMPLEMENT
    ),
    "shell": _write("Runs a command of the allowlist in the workspace.", _IMPLEMENT),
    # The reads of GitHub, which every job role holds.
    "gh_issues_list": _read(
        "Lists the issues of the repository on GitHub, with their labels and milestone.",
        _EVERY_JOB_ROLE,
    ),
    "gh_issues_status": _read(
        "Shows the counts of the issues of the repository on GitHub by priority, type and milestone.",
        _EVERY_JOB_ROLE,
    ),
    "gh_issues_view": _read("Shows one issue of the repository on GitHub.", _EVERY_JOB_ROLE),
    "gh_labels_list": _read("Lists the labels of the repository on GitHub.", _EVERY_JOB_ROLE),
    "gh_milestones_list": _read(
        "Lists the milestones of the repository on GitHub, with their progress.", _EVERY_JOB_ROLE
    ),
    "gh_pages_status": _read(
        "Shows the state of the GitHub Pages site of the repository.", _EVERY_JOB_ROLE
    ),
    "gh_project_list": _read(
        "Lists the GitHub Projects boards of the repository.", _EVERY_JOB_ROLE
    ),
    "gh_rate_limit": _read("Shows the rate limit of the GitHub API.", _EVERY_JOB_ROLE),
    "gh_runs_list": _read(
        "Lists the recent workflow runs of the repository on GitHub.", _EVERY_JOB_ROLE
    ),
    "gh_runs_view": _read(
        "Shows one workflow run of the repository on GitHub, with the logs of a failure.",
        _EVERY_JOB_ROLE,
    ),
    "pr_checks": _read("Shows the state of the CI checks of a pull request.", _EVERY_JOB_ROLE),
    "pr_diff": _read("Shows the diff of a pull request.", _EVERY_JOB_ROLE),
    "pr_list": _read("Lists the pull requests of the repository on GitHub.", _EVERY_JOB_ROLE),
    "pr_threads_list": _read(
        "Lists the review threads of a pull request, with their files and comments.",
        _EVERY_JOB_ROLE,
    ),
    # The two security lookups, which every job role holds.
    "security_intel_network": _read(
        "Looks up the reputation of a network address or a domain.", _EVERY_JOB_ROLE
    ),
    "security_intel_package": _read(
        "Looks up the advisories of a package in OSV.dev.", _EVERY_JOB_ROLE
    ),
    # The reads of the cluster, which the planning role holds.
    "argo_cd_apps_list": _read("Lists the applications of Argo CD.", _PLANNING),
    "argo_cd_apps_status": _read(
        "Shows the synchronization state of the applications of Argo CD.", _PLANNING
    ),
    "grafana_dashboards_list": _read("Lists the Grafana dashboards.", _PLANNING),
    "k8s_audit": _read("Audits the cluster for security problems.", _PLANNING),
    "k8s_logs": _read("Shows the recent logs of a pod or a namespace of the cluster.", _PLANNING),
    "k8s_pods": _read("Lists the pods of a namespace of the cluster.", _PLANNING),
    "k8s_status": _read("Shows the status of the cluster.", _PLANNING),
    "k8s_tempo_info": _read(
        "Shows the address of the Tempo API and its trace endpoints.", _PLANNING
    ),
    "prometheus_query": _read("Runs a PromQL query on Prometheus.", _PLANNING),
    "telemetry_logfire": _read(
        "Shows the state of the Logfire bridge and its token counts.", _PLANNING
    ),
    "telemetry_profile": _read("Profiles one command of the CLI and shows its trace.", _PLANNING),
    "telemetry_status": _read("Shows the state of the telemetry pipeline.", _PLANNING),
    # The one tool that only the implementation role holds.
    "pr_describe": _read(
        "Builds the title and the body of a pull request from an issue.", _IMPLEMENTATION
    ),
}


def tool_names(holder: str) -> tuple[str, ...]:
    """The names of `holder` in table order. A holder that the table does not know raises
    `ValueError`: a misspelt holder must not give a table that reads as empty."""
    if holder not in HOLDERS:
        raise ValueError(f"Unknown tool holder '{holder}'.")
    return tuple(name for name, entry in TOOLS.items() if holder in entry.holders)


def check_tables(tables: Mapping[str, Iterable[str]]) -> list[str]:
    """One problem for each name of a table that the registry does not hold, with the table and the
    name in the text. An empty list means that every table names only tools of the registry."""
    return [
        f"The table '{table}' names the tool '{name}', which the registry does not hold."
        for table, names in tables.items()
        for name in names
        if name not in TOOLS
    ]


__all__ = ["HOLDERS", "TOOLS", "ToolEntry", "check_tables", "tool_names"]
