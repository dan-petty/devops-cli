"""The one registry of the tools that a roadmap job and an MCP role server may hold (#3244).

Four places choose the tools of a model that works on the project: the plan run of the stage job
(`stage`, and `stage-extended` for the three tools that the toolset `extended` adds), the
implementation step (`implement`), and the role servers of the MCP host (`planning`,
`implementation` and `review`). Each one reads its names from this table, so a tool that leaves the
table leaves every host, and a tool that joins it joins the hosts that its `holders` name.

An entry holds no callable. The stage tools are methods of `StageTools`, the implement tools are
capabilities of the harness `Coder`, and the role tools are generated from the commands of the CLI,
so no one function serves every name. The table unifies the names, the purposes and the read-only
flags, and `check_tables` reports a table that names a tool that the registry does not hold.
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

# Every table that holds a tool. A role server serves one job role, and a toolset of a job names one
# or two holders.
HOLDERS: Final[tuple[str, ...]] = (
    HOLDER_STAGE,
    HOLDER_STAGE_EXTENDED,
    HOLDER_IMPLEMENT,
    HOLDER_PLANNING,
    HOLDER_IMPLEMENTATION,
    HOLDER_REVIEW,
)

# The three job roles hold a table each, and every role but `review` adds the tools after it.
_EVERY_ROLE: Final[tuple[str, ...]] = (HOLDER_PLANNING, HOLDER_IMPLEMENTATION, HOLDER_REVIEW)
_PLANNING_ONLY: Final[tuple[str, ...]] = (HOLDER_PLANNING,)


@dataclass(frozen=True)
class ToolEntry:
    """One tool of the registry: its name, its one-line purpose, whether every call of it only
    reads, and the tables that hold it."""

    name: str
    purpose: str
    read_only: bool
    holders: frozenset[str]


def _entry(name: str, purpose: str, *holders: str, read_only: bool = True) -> ToolEntry:
    return ToolEntry(name, purpose, read_only, frozenset(holders))


# The tools of each table, in the order that a host offers them. The stage tools come first, so the
# plan run offers the nine of `base` in their order and then the three of `stage-extended`.
TOOLS: Final[tuple[ToolEntry, ...]] = (
    _entry(
        "list_files",
        "List the files and the directories of one directory of the workspace.",
        HOLDER_STAGE,
        HOLDER_IMPLEMENT,
    ),
    _entry(
        "read_file",
        "Read the lines of one file of the workspace.",
        HOLDER_STAGE,
        HOLDER_IMPLEMENT,
    ),
    _entry(
        "search_code",
        "Search the staged commit for a text, and list the matches of each file.",
        HOLDER_STAGE,
    ),
    _entry(
        "git_log",
        "List the newest commits that changed a path of the staged commit.",
        HOLDER_STAGE,
    ),
    _entry(
        "git_show",
        "Show one commit of the staged history: its message and its diff.",
        HOLDER_STAGE,
    ),
    _entry(
        "file_symbols",
        "List the classes, the functions and the methods of one source file, with their lines.",
        HOLDER_STAGE,
    ),
    _entry(
        "callers",
        "List the places that call a function, a method or a class.",
        HOLDER_STAGE,
    ),
    _entry(
        "repo_map",
        "Map the source files under one directory, with the names of their top-level symbols.",
        HOLDER_STAGE,
    ),
    _entry(
        "read_spec",
        "List the capabilities of the project, or read the requirements of one spec.",
        HOLDER_STAGE,
    ),
    _entry(
        "references",
        "List every file of the staged commit that holds a text, with the count of its lines.",
        HOLDER_STAGE_EXTENDED,
    ),
    _entry(
        "read_issue",
        "Read one issue or pull request of the repository on GitHub.",
        HOLDER_STAGE_EXTENDED,
    ),
    _entry(
        "find_issues",
        "List the open issues and pull requests of the repository that name the terms.",
        HOLDER_STAGE_EXTENDED,
    ),
    _entry(
        "write_file",
        "Write the whole text of one file of the workspace.",
        HOLDER_IMPLEMENT,
        read_only=False,
    ),
    _entry(
        "edit_file",
        "Replace a text of one file of the workspace.",
        HOLDER_IMPLEMENT,
        read_only=False,
    ),
    _entry(
        "grep",
        "Search the files of the workspace for a regular expression, and list the matches.",
        HOLDER_IMPLEMENT,
    ),
    _entry(
        "shell",
        "Run one command in the shell of the workspace.",
        HOLDER_IMPLEMENT,
        read_only=False,
    ),
    _entry(
        "gh_issues_list",
        "List the issues of the repository on GitHub, with their milestones and labels.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_issues_status",
        "Show the counts of the issues of the repository, by priority, type and milestone.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_issues_view",
        "Read one issue of the repository on GitHub: its state, its labels and its body.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_labels_list",
        "List the labels of the repository on GitHub.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_milestones_list",
        "List the milestones of the repository on GitHub, with their completion.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_pages_status",
        "Show the status of GitHub Pages: its URL, its branch and its HTTPS setting.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_project_list",
        "List the GitHub Projects boards of the user or of the organization.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_rate_limit",
        "Show the REST and GraphQL rate limits of GitHub, with their reset times.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_runs_list",
        "List the newest workflow runs of the repository or of one branch.",
        *_EVERY_ROLE,
    ),
    _entry(
        "gh_runs_view",
        "Show one workflow run, with the log of its failed steps.",
        *_EVERY_ROLE,
    ),
    _entry(
        "pr_checks",
        "Show the checks of a pull request, and whether each one passed.",
        *_EVERY_ROLE,
    ),
    _entry(
        "pr_diff",
        "Show the diff of a pull request.",
        *_EVERY_ROLE,
    ),
    _entry(
        "pr_list",
        "List the pull requests of the repository, with their review state.",
        *_EVERY_ROLE,
    ),
    _entry(
        "pr_threads_list",
        "List the review threads of a pull request, with their files and comments.",
        *_EVERY_ROLE,
    ),
    _entry(
        "security_intel_network",
        "Check the threat intelligence of an IP address or a domain.",
        *_EVERY_ROLE,
    ),
    _entry(
        "security_intel_package",
        "Look up the known vulnerabilities of a package version in OSV.dev.",
        *_EVERY_ROLE,
    ),
    _entry(
        "pr_describe",
        "Print the title and the body of the pull request that delivers an issue.",
        HOLDER_IMPLEMENTATION,
    ),
    _entry(
        "argo_cd_apps_list",
        "List the Argo CD applications of the cluster.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "argo_cd_apps_status",
        "Show the sync and the health of one Argo CD application, and the images it pins.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "grafana_dashboards_list",
        "List the dashboards of Grafana.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "k8s_audit",
        "Audit the health of the resources of the cluster with Popeye.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "k8s_logs",
        "Read the logs of a pod, or run a LogQL query over the logs of the cluster.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "k8s_pods",
        "List the pods of the cluster, with their health, their restarts and their age.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "k8s_status",
        "Show the nodes and the pods of the current context of the cluster.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "k8s_tempo_info",
        "Show the endpoints of Tempo that hold the traces of the cluster.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "prometheus_query",
        "Run an instant PromQL query on Prometheus.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "telemetry_logfire",
        "Show the status of the Logfire bridge, with the metrics of its token.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "telemetry_profile",
        "Show the span waterfall of one trace, as Tempo recorded it.",
        *_PLANNING_ONLY,
    ),
    _entry(
        "telemetry_status",
        "Check the health of the OpenTelemetry collector and the endpoints of the traces.",
        *_PLANNING_ONLY,
    ),
)


def tool_names(holder: str) -> tuple[str, ...]:
    """The names of the tools of one holder, in table order. A holder that the table does not know
    raises `ValueError`, so a misspelt role or toolset stops its caller instead of serving no
    tool."""
    if holder not in HOLDERS:
        raise ValueError(f"The tool registry holds no holder '{holder}'.")
    return tuple(entry.name for entry in TOOLS if holder in entry.holders)


def check_tables(tables: Mapping[str, Iterable[str]]) -> list[str]:
    """One problem for each name of a table that the registry does not hold, in table order. The
    key of `tables` is the name of a table, such as a role or a toolset, and a problem text gives
    it with the missing tool, so a person sees which table to fix."""
    known = {entry.name for entry in TOOLS}
    return [
        f"The table {table} names the tool {name}, which the registry does not hold."
        for table, names in tables.items()
        for name in names
        if name not in known
    ]


__all__ = ["HOLDERS", "TOOLS", "ToolEntry", "check_tables", "tool_names"]
