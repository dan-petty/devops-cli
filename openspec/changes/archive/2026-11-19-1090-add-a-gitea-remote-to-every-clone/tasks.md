# Tasks

## 1. Settings and Credentials

- [x] 1.1 Add tests for Gitea settings and credentials validation
  - Verification: `$ uv run pytest tests/config/test_gitea_settings.py`
- [x] 1.2 Implement Gitea settings in `src/devops_cli/config/settings.py` and credential in `src/devops_cli/config/env.py`
  - Verification: `$ uv run pytest tests/config/test_gitea_settings.py`

## 2. Gitea API Client

- [x] 2.1 Add tests for Gitea API client, models, and error handling
  - Verification: `$ uv run pytest tests/gitea/test_gitea_client.py`
- [x] 2.2 Implement Gitea client in `src/devops_cli/gitea/client.py` with typed calls, token masking, and Access blocked handling
  - Verification: `$ uv run pytest tests/gitea/test_gitea_client.py`

## 3. Gitea Connect and Credential Helper Commands

- [x] 3.1 Add tests for `devops repos gitea connect` and `credential get|store|erase`
  - Verification: `$ uv run pytest tests/commands/test_repos_gitea.py`
- [x] 3.2 Implement `devops repos gitea connect` and `devops repos gitea credential` subcommands
  - Verification: `$ uv run pytest tests/commands/test_repos_gitea.py`

## 4. Repos Remotes Command

- [x] 4.1 Add tests for `devops repos remotes`
  - Verification: `$ uv run pytest tests/commands/test_repos_remotes.py`
- [x] 4.2 Implement `devops repos remotes` command ensuring org, repo, branch protection, config helper, and default branch seed
  - Verification: `$ uv run pytest tests/commands/test_repos_remotes.py`

## 5. Repos Sync and Clone Integration

- [x] 5.1 Add tests for `devops repos sync` and `devops repos clone` with Gitea
  - Verification: `$ uv run pytest tests/commands/test_repos_sync_gitea.py`
- [x] 5.2 Implement Gitea sync pushing default branch via porcelain and clone remote setup
  - Verification: `$ uv run pytest tests/commands/test_repos_sync_gitea.py`

## 6. Documentation and Quality Gates

- [x] 6.1 Update help messages in `lang/en/help.py` and documentation in `docs/`
  - Verification: `$ uv run devops docs generate && uv run devops docs check`
- [x] 6.2 Run full CI quality gates
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck,test-tree,docs,openspec`
