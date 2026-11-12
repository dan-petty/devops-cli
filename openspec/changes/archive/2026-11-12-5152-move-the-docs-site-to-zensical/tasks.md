# Tasks

## 1. The site build (behavior)

- [x] 1.1 Write failing tests: the stage, the link change, the staged config, the build data and the checks of the built site.
  - Verification: `$ uv run devops ci test tests/docs/test_site.py`
- [x] 1.2 Write failing tests of `devops docs site build`: the strict build, a page in no tab, a failed Zensical build and `--serve`.
  - Verification: `$ uv run devops ci test tests/commands/test_docs_site.py`
- [x] 1.3 Add `src/devops_cli/docs/site.py`, `DocsSiteError` and the `site build` command.
  - Verification: `$ uv run devops ci test tests/docs/test_site.py tests/commands/test_docs_site.py`

## 2. The MCP tool anchors (behavior)

- [x] 2.1 Write a failing test: the table of the MCP tool catalog links to `#ai_ask_jev`.
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py`
- [x] 2.2 Keep the underscores of the tool name in the anchor, and write `docs/MCP_TOOLS.md` again.
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py`

## 3. The check of the site settings (behavior)

- [x] 3.1 Write failing tests: `devops gh pages verify` checks `zensical.toml`.
  - Verification: `$ uv run devops ci test tests/github/test_github_pages.py tests/commands/test_gh_cmd.py`
- [x] 3.2 Read `zensical.toml` in `src/devops_cli/github/pages.py`.
  - Verification: `$ uv run devops ci test tests/github/test_github_pages.py tests/commands/test_gh_cmd.py`

## 4. The site sources and the workflows

- [x] 4.1 Add `zensical==0.1.1` to the `docs` group, `zensical.toml`, `.nav.yml` and `overrides/`. Delete `docs/_config.yml`, `docs/_layouts/default.html` and `docs/assets/css/style.css`.
  - Verification: `$ uv run devops docs site build --strict`
- [x] 4.2 Build and deploy with the command in `pages.yml`, and build with it in `docs-site.yml`.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 5. Documents

- [x] 5.1 Describe the site build in `docs/SDLC.md`, and replace `docs/_config.yml` and Jekyll in `docs/DESIGN.md`, `docs/ROUTINE_TASKS.md`, `docs/index.md` and the knowledge base page of GitHub project management. Write the generated references again.
  - Verification: `$ uv run devops ci docs`
