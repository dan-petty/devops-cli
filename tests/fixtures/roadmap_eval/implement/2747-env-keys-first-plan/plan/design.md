# Design

## Decisions

- **Deny the NPM_CONFIG_* family with a single fnmatch pattern rather than listing npm_config_logs_dir and npm_config_cache individually.**: npm reads every setting from a key with the NPM_CONFIG_ prefix, so any member can direct a file write. The existing guard already uses family patterns for dangerous families: DYLD_* and BASH_FUNC_*. A single-key list would miss future or unprobed members.
- **Add PYTEST_ADDOPTS as an exact-name entry, not a family pattern.**: PYTEST_ADDOPTS is a single key. There is no PYTEST_* family of dangerous keys. The existing constant holds exact names for single keys (LD_AUDIT, ENV) and family patterns for families (DYLD_*, BASH_FUNC_*).
- **Place both entries in CONST_CODE_LOADING_ENV_PATTERNS, not in DEFAULT_DENIED_ENV_PATTERNS.**: CONST_CODE_LOADING_ENV_PATTERNS is the list that _is_env_override_refused checks for caller overrides. DEFAULT_DENIED_ENV_PATTERNS filters ambient environment variables. These keys are a caller-override risk, so they belong in the override list, consistent with the existing entries.

## Rejected alternatives

- **Deny only npm_config_logs_dir and npm_config_cache individually.**: npm's config system is open-ended: it reads each npm setting from a key with the NPM_CONFIG_ prefix. A future or unprobed npm_config_* key could also direct a file write. The existing design uses family patterns for this case (DYLD_*, BASH_FUNC_*).
- **Add the keys to DEFAULT_DENIED_ENV_PATTERNS instead of CONST_CODE_LOADING_ENV_PATTERNS.**: DEFAULT_DENIED_ENV_PATTERNS filters ambient environment variables. The risk here is a caller override, which _is_env_override_refused checks against CONST_CODE_LOADING_ENV_PATTERNS. Placing the keys in the wrong constant would not block the override path.
