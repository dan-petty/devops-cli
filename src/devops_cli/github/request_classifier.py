"""Whether a GitHub request writes, decided from the request itself (#1125).

GitHub asks for at least a second between mutative requests, whichever API they use, so the rate
limiter paces a write with `mutation_min_interval`. The classifier reads a `GitHubRequest`: its
method, endpoint and, for GraphQL, its document and operation name. `run_gh` builds one from gh's
argv with `describe_gh_api_request`; a caller that builds its own request classifies it directly.

A request that can't be read counts as a write: a false write costs one interval, while a false
read sends an unpaced write toward GitHub's secondary limit and its minutes-long backoff.
"""

from __future__ import annotations

import argparse
import functools
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.constants import (
    CONST_GH_API_DEFAULT_METHOD,
    CONST_GH_API_FIELD_SEPARATOR,
    CONST_GH_API_FILE_VALUE_PREFIX,
    CONST_GH_API_GRAPHQL_ENDPOINT,
    CONST_GH_API_PARAMS_METHOD,
    CONST_GH_API_STDIN_PATH,
    CONST_GH_API_SUBCOMMAND,
    CONST_GH_API_SWITCH_FLAGS,
    CONST_GH_API_VALUE_FLAGS,
    CONST_GH_COMMAND_VALUE_FLAGS,
    CONST_GH_MUTATION_HTTP_METHODS,
    CONST_GH_READ_GROUPS,
    CONST_GH_READ_VERBS,
    CONST_GRAPHQL_OPERATION_NAME_KEY,
    CONST_GRAPHQL_QUERY_KEY,
    CONST_GRAPHQL_REQUEST_KEYS,
)


@dataclass(frozen=True, slots=True)
class GitHubRequest:
    """One request as GitHub receives it.

    `endpoint` is a REST path, or `graphql` for the GraphQL API, whose `document` and
    `operation_name` are the request's `query` and `operationName`.
    """

    method: str
    endpoint: str
    document: str | None = None
    operation_name: str | None = None


@dataclass(frozen=True, slots=True)
class GhApiArgs:
    """What a `gh api` argv tells gh to send: its endpoint, method, fields and body file."""

    endpoint: str | None
    method: str
    raw_fields: tuple[str, ...]
    typed_fields: tuple[str, ...]
    input_path: str | None

    @property
    def has_params(self) -> bool:
        """Whether the request carries fields or a body."""
        return bool(self.raw_fields or self.typed_fields) or self.input_path is not None


def is_write_request(request: GitHubRequest) -> bool:
    """Whether the request writes: a REST POST, PUT, PATCH or DELETE, or a GraphQL request whose
    operation is not a query, including one whose document is missing or doesn't parse."""
    if request.endpoint != CONST_GH_API_GRAPHQL_ENDPOINT:
        return request.method.upper() in CONST_GH_MUTATION_HTTP_METHODS
    return not _runs_a_query(request.document, request.operation_name)


def is_write_gh_command(
    args: Sequence[str], *, input: str | None = None, cwd: Path | None = None
) -> bool:
    """Whether the gh command (without the leading `gh`) writes.

    `gh api` is classified from the request it sends, reading a document from `input` (stdin)
    or a file relative to `cwd`. Any other command reads only when its group only reads or its
    verb, the second word after gh's `-R`/`--repo` and `--owner` flags, is a read verb; every
    other verb is a write, and so is an argv that doesn't parse.
    """
    if args and args[0] == CONST_GH_API_SUBCOMMAND:
        request = describe_gh_api_request(args[1:], input=input, cwd=cwd)
        return request is None or is_write_request(request)
    words = gh_command_words(args)
    if words is None:
        return True
    group, verb = words
    if group in CONST_GH_READ_GROUPS:
        return False
    return verb not in CONST_GH_READ_VERBS


def gh_command_words(args: Sequence[str]) -> tuple[str | None, str | None] | None:
    """A high-level gh command's group and verb, the first two words once gh's `-R`/`--repo`
    and `--owner` flags are skipped, or None when the argv doesn't parse."""
    try:
        command, _ = _gh_command_parser().parse_known_args(list(args))
    except argparse.ArgumentError:
        return None
    return command.group, command.verb


def parse_gh_api_args(api_args: Sequence[str]) -> GhApiArgs | None:
    """Parse the arguments after `gh api`, or None when gh would reject them."""
    try:
        parsed, _ = _gh_api_parser().parse_known_args(list(api_args))
    except argparse.ArgumentError:
        return None
    raw_fields = tuple(parsed.raw_field or ())
    typed_fields = tuple(parsed.field or ())
    has_params = bool(raw_fields or typed_fields) or parsed.input is not None
    default = CONST_GH_API_PARAMS_METHOD if has_params else CONST_GH_API_DEFAULT_METHOD
    return GhApiArgs(
        endpoint=parsed.endpoint,
        method=parsed.method.upper() if parsed.method is not None else default,
        raw_fields=raw_fields,
        typed_fields=typed_fields,
        input_path=parsed.input,
    )


def describe_gh_api_request(
    api_args: Sequence[str], *, input: str | None = None, cwd: Path | None = None
) -> GitHubRequest | None:
    """The request `gh api <api_args>` sends, or None when its argv doesn't parse."""
    args = parse_gh_api_args(api_args)
    if args is None or args.endpoint is None:
        return None
    if args.endpoint != CONST_GH_API_GRAPHQL_ENDPOINT:
        return GitHubRequest(method=args.method, endpoint=args.endpoint)
    params = _graphql_params(args, input=input, cwd=cwd)
    return GitHubRequest(
        method=args.method,
        endpoint=args.endpoint,
        document=params.get(CONST_GRAPHQL_QUERY_KEY),
        operation_name=params.get(CONST_GRAPHQL_OPERATION_NAME_KEY),
    )


@functools.cache
def _gh_command_parser() -> argparse.ArgumentParser:
    """A high-level gh command's group and verb, past the value flags gh takes before the verb."""
    parser = argparse.ArgumentParser(
        prog="gh", add_help=False, allow_abbrev=False, exit_on_error=False
    )
    parser.add_argument("group", nargs="?")
    parser.add_argument("verb", nargs="?")
    for flags in CONST_GH_COMMAND_VALUE_FLAGS:
        parser.add_argument(*flags)
    return parser


@functools.cache
def _gh_api_parser() -> argparse.ArgumentParser:
    """`gh api`'s flags in the forms gh's flag parser accepts (`-XPOST`, `-X=POST`, ...).

    argparse takes neither a switch given a value (`--paginate=true`) nor a value starting with
    a dash (`--jq -.a`), which gh's parser accepts; such an argv doesn't parse, so it counts as
    a write.
    """
    parser = argparse.ArgumentParser(
        prog="gh api", add_help=False, allow_abbrev=False, exit_on_error=False
    )
    parser.add_argument("endpoint", nargs="?")
    parser.add_argument("-X", "--method")
    parser.add_argument("-f", "--raw-field", action="append")
    parser.add_argument("-F", "--field", action="append")
    parser.add_argument("--input")
    for flags in CONST_GH_API_VALUE_FLAGS:
        parser.add_argument(*flags, action="append")
    for flags in CONST_GH_API_SWITCH_FLAGS:
        parser.add_argument(*flags, action="store_true")
    return parser


def _graphql_params(args: GhApiArgs, *, input: str | None, cwd: Path | None) -> dict[str, str]:
    """The `query` and `operationName` gh sends: from the `--input` body when there is one,
    otherwise from the fields, where a typed field reads `@path` and a raw one sends it as is."""
    if args.input_path is not None:
        return _body_params(_read_user_file(args.input_path, input=input, cwd=cwd))
    params: dict[str, str | None] = {}
    for field in args.raw_fields:
        key, _, value = field.partition(CONST_GH_API_FIELD_SEPARATOR)
        params[key] = value
    for field in args.typed_fields:
        key, _, value = field.partition(CONST_GH_API_FIELD_SEPARATOR)
        if key in CONST_GRAPHQL_REQUEST_KEYS and value.startswith(CONST_GH_API_FILE_VALUE_PREFIX):
            path = value.removeprefix(CONST_GH_API_FILE_VALUE_PREFIX)
            params[key] = _read_user_file(path, input=input, cwd=cwd)
        else:
            params[key] = value
    return {
        key: sent for key in CONST_GRAPHQL_REQUEST_KEYS if (sent := params.get(key)) is not None
    }


def _body_params(body: str | None) -> dict[str, str]:
    """The `query` and `operationName` of a JSON request body; none when it isn't JSON."""
    try:
        data = json.loads(body) if body is not None else None
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key in CONST_GRAPHQL_REQUEST_KEYS if isinstance(value := data.get(key), str)
    }


def _read_user_file(path: str, *, input: str | None, cwd: Path | None) -> str | None:
    """What gh reads for `path`: stdin for `-`, else the file relative to `cwd`; None if unreadable."""
    if path == CONST_GH_API_STDIN_PATH:
        return input
    try:
        return ((cwd or Path()) / path).read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return None


def _runs_a_query(document: str | None, operation_name: str | None) -> bool:
    """Whether the operation the document runs is a query; graphql-core loads only here."""
    if document is None:
        return False
    from graphql import GraphQLError, OperationType, parse
    from graphql.utilities import get_operation_ast

    try:
        operation = get_operation_ast(parse(document, no_location=True), operation_name)
    except GraphQLError:
        return False
    return operation is not None and operation.operation is OperationType.QUERY
