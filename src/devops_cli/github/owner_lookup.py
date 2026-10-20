"""What a gh project command whose owner lookup failed was, asked of GraphQL's own budget (#983).

gh project resolves `--owner <login>` with a GraphQL query and, for any failure of it that is not
a not-found for both a user and an organization, writes "unknown owner type" and drops the cause:
a refused token, a SAML refusal, a GitHub or network failure, or a rate limit. The gh classifier
reads it as a rate limit. A command with no `@me` fallback, such as the roadmap store's board
writes and `github/projects.py`'s board reads, asks GraphQL for its budget, the source the
project trusts for it since #1125 (`gh api rate_limit` can report points GraphQL has not), at
the cost of about one point. A budget at or above `DEFAULT_GH_GRAPHQL_BUDGET_FLOOR` makes the
failure a plain one that names the points left and the causes still possible, a secondary limit
among them; a budget below the floor, a budget read refused for a rate limit or unread, keeps the
rate limit, which stops an intake round; a budget read GitHub refuses the token for is the
unauthenticated error.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from pydantic import ValidationError

from devops_cli.config.defaults import DEFAULT_GH_GRAPHQL_BUDGET_FLOOR
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.github.error_classifier import classify_gh_failure
from devops_cli.roadmap.board_read import GraphQLBudgetPayload, graphql_budget_args

# Runs one gh command, given without its leading `gh`, and returns the finished process.
GhRead = Callable[[list[str]], subprocess.CompletedProcess[str]]


def owner_lookup_failure(
    classified: GitHubOperationError, *, read: GhRead, failed: str, operation: str
) -> GitHubOperationError:
    """The error of a command whose owner lookup gh dropped the cause of, `classified` being the
    rate limit the gh classifier made of it and `failed` what the command could not do, decided
    by GraphQL's own budget, which `read` asks for."""
    answer = read(graphql_budget_args())
    if answer.returncode != 0:
        return _refused_budget_read(answer, classified, failed=failed, operation=operation)
    try:
        left = GraphQLBudgetPayload.model_validate_json(answer.stdout or "").rate_limit.remaining
    except ValidationError:
        return classified
    if left < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR:
        return classified
    return GitHubOperationError(
        f"{failed}: gh could not look up the board's owner and did not say why. GraphQL answered "
        f"with {left} points left, so its quota is not spent; gh dropped the cause, which may be "
        "a secondary rate limit, a refusal of the owner lookup such as SAML authorization, or a "
        "GitHub or network failure, so the command can be run again",
        operation=operation,
        details={**classified.details, "graphql_remaining": left},
    )


def _refused_budget_read(
    answer: subprocess.CompletedProcess[str],
    classified: GitHubOperationError,
    *,
    failed: str,
    operation: str,
) -> GitHubOperationError:
    """A refused token is the unauthenticated error naming the failed command; any other
    failed budget read keeps the rate limit."""
    refused = classify_gh_failure(
        answer.stderr or "", exit_code=answer.returncode, operation=operation
    )
    if not isinstance(refused, GitHubUnauthenticatedError):
        return classified
    return GitHubUnauthenticatedError(
        f"{failed}: {refused.message}", operation=operation, details=refused.details
    )
