# Design

## Context

See `proposal.md` - Why.
`run_gh` paces commands against rate limits by detecting their target resource with `_detect_resource`.
Before this change, `_detect_resource` only mapped `project` or arguments containing `graphql` to `graphql`.
It mapped commands with `search/` anywhere in arguments to `search`.
This caused false negatives for GraphQL porcelain commands and false positives for REST paths containing substrings.

## Goals / Non-Goals

**Goals:**
- Classify `gh` porcelain commands backed by GraphQL as `graphql` using parsed command words.
- Classify `gh api` requests using parsed endpoint path segments.
- Eliminate all `in arg` substring checks in resource detection.
- Maintain existing classification for `api graphql`, `api search/*`, `api code-scanning/*`, and `dependency-graph/sbom`.
- Ensure offline unit tests verify both positive and negative cases.

**Non-Goals:**
- Change the pacing formula or backoff strategy of `GitHubRateLimiter`.
- Replace `gh` porcelain commands with REST equivalents in callers.
- Add network calls during rate-limit resource detection.

## Decisions

### Decision 1: Structured Classification Table in constants.py

Define `CONST_GH_GRAPHQL_PORCELAIN_COMMANDS` and `CONST_GH_GRAPHQL_GROUPS` in `src/devops_cli/config/constants.py`.
Classify porcelain commands using `gh_command_words` parsed group and verb against this table.
This eliminates substring matching on arbitrary arguments such as commit titles or bodies.

*Alternatives considered:*
- Matching arguments by regex: rejected because regex on full arguments still inspects option values and flags.
- Converting all callers to use `gh api` REST endpoints: rejected because porcelain commands provide required higher-level features and formatting.

### Decision 2: Endpoint Parsing for gh api Commands

Use `parse_gh_api_args` to extract the target endpoint for `gh api` commands.
Inspect path segments rather than performing substring checks across all arguments.
Return `core` for repository names or paths containing `graphql` or `search` outside defined API prefixes.

*Alternatives considered:*
- Inspecting `clean_args[1]` directly: rejected because `gh api` accepts flags such as `-X POST` before the endpoint.

### Decision 3: Remove Substring Predicates

Remove `_is_graphql_command`, `_is_code_search_command`, `_is_code_scanning_autofix_command`, and `_is_general_search_command`.
Replace them with pure segment-matching functions `_detect_api_resource` and `_detect_porcelain_resource`.
This complies with the zero-zombie-code invariant and AGENTS.md rules.

*Alternatives considered:*
- Keeping the predicates as wrappers: rejected because pre-1.0 code maintains no backward compatibility shims.
