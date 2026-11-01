# Design

## Decisions

- **Add LESS to CONST_CODE_LOADING_ENV_PATTERNS rather than to DEFAULT_DENIED_ENV_PATTERNS**: CONST_CODE_LOADING_ENV_PATTERNS is the list that _is_env_override_refused checks for caller overrides. DEFAULT_DENIED_ENV_PATTERNS filters ambient environment variables. LESS is a caller-override risk, so it belongs in the override list, consistent with LESSOPEN and LESSCLOSE.
- **Refuse LESS unconditionally, in upper and lower case, with and without isolation**: _is_env_override_refused upper-cases the key before matching, so a single entry "LESS" covers both cases. The check runs before the isolate_env branch, so it applies regardless of isolation. This matches the behavior of LESSOPEN and LESSCLOSE.

## Rejected alternatives

- **Accept LESS and document the risk in SECURITY.md**: The project standard in ARCHITECTURE.md and the #2483 spec is to refuse keys that make a child run a program. Accepting LESS leaves a known code-execution path open. A probe with less 668 confirmed execution via git --paginate and gh help reference.
