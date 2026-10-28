# Tasks

## 1. Scope each installation token to the roadmap jobs' permissions

- [x] Add failing tests: the exchange's body holds exactly the six permissions; a reply that grants one more keeps the token and logs only the permission names; a 422 names each permission that the token asks for
  - Verification: `uv run devops ci test tests/test_github_app_identity.py`
- [x] Add `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, post the exchange with its `permissions` body through gidgethub's `GitHubAPI`, log the names of the reply's permissions, and name the asked permissions on HTTP 422
  - Verification: `uv run devops ci test tests/test_github_app_identity.py`
- [x] Update ADR 0015, the "Roadmap service" text of `k8s/README.md` and the knowledge base's GitHub CLI page, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2473-app-token-permissions`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
