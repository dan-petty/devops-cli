# Design

## Decisions
- **Base directory for identity cache**: Use `platformdirs.user_cache_dir(CONST_APP_NAME)` for the root cache directory. This resolves under the platform user cache directory rather than the working directory repository.
- **Identity digest subdirectories**: Keep the first characters of the SHA-256 digest of the identity key under the user cache directory. This keeps each identity and token separate while hiding tokens.
- **Session and rate limiter shared root**: Both `resolve_quota_cache_path()` and `resolve_identity_cache_dir()` use `_identity_cache_root()`, which ensures consistency across the quota ledger and response cache.

## Rejected alternatives
- **Use working directory `.data/cache`**: Rejected because commands executed in clones write cache files into those repositories and pollute git status.
- **Flat user cache directory with no identity digest**: Rejected because different identities and tokens would collide in one ledger.
- **Custom platform directory resolver**: Rejected because `platformdirs` is already a maintained dependency that handles platform differences.
