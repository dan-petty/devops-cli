# Tasks

## 1. Failing tests

- [x] Add the test that walks the links from `AGENTS.md`, its negative control, and the matrix cell that links the page of a command group
  - Verification: `uv run devops ci test tests/test_agents_md_claims.py tests/test_docs.py`

## 2. Links and rows

- [x] List the settings, error, telemetry, knowledge base, OpenTofu and agent record documents in `README.md`, and link `k8s/llm/profiles/README.md` from `k8s/README.md`
  - Verification: `uv run devops ci test tests/test_agents_md_claims.py`
- [x] Link each command group to its page in `render_readme_matrix` of `src/devops_cli/docs/generator.py`
  - Verification: `uv run devops ci test tests/test_docs.py`
- [x] Add the lookup row and the OpenTofu link to `AGENTS.md` within `CONST_AGENTS_MD_MAX_CHARS`
  - Verification: `uv run devops ci test tests/test_agents_md_claims.py`

## 3. Documentation

- [x] Regenerate the documentation with `devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## 4. Verification and static checks

- [x] Verify the fail-to-pass check run against `origin/main`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify that the full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
