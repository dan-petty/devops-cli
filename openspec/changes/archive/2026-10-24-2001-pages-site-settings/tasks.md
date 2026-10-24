# Tasks

## 1. One file of site settings, checked by devops gh pages verify

- [x] 1.1 Change the verify tests of `tests/test_github_pages.py` to write `docs/_config.yml`, and add `test_verify_pages_configuration_reads_only_the_file_jekyll_reads` and `test_the_repository_site_settings_are_in_the_one_file_jekyll_reads`, and verify that `uv run devops ci test tests/test_github_pages.py` fails on the base with 5 failed tests
- [x] 1.2 Make `verify_pages_configuration` in `src/devops_cli/github/pages.py` read `docs/_config.yml`, and verify that `uv run devops ci test tests/test_github_pages.py tests/test_gh_cmd.py` passes
- [x] 1.3 Move the site settings of `docs/github-pages.config.yaml` into `docs/_config.yml` and delete the second file, and verify that `uv run devops ci test tests/test_github_pages.py` passes
- [x] 1.4 Name `docs/_config.yml` in `docs/ROUTINE_TASKS.md` and in `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, and verify that `git grep -n "github-pages.config" -- . ':!docs/agent/archive' ':!docs/adr' ':!openspec/changes/archive'` finds only the test fixture of 1.1
- [x] 1.5 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 2. Build the site with the Pages builder

- [x] 2.1 Run the `docker run` command of the `Docs Site Build` job on `docs/`, with a writable directory at `/github/site`, and verify that the log names `docs/_config.yml`, that the site has no `github-pages.config.yaml`, and that `CLI_REFERENCE.html` has the meta description of `docs/_config.yml`, the canonical URL `https://dan-petty.github.io/devops-cli/CLI_REFERENCE.html` and the stylesheet link `/devops-cli/assets/css/style.css`
- [x] 2.2 Run `uv run devops openspec check`, and verify that it passes

## Workflow follow-up

- Pending a person: after the Pages build of the merge commit, verify that `https://dan-petty.github.io/devops-cli/CLI_REFERENCE.html` has the meta description of `docs/_config.yml`, and that `https://dan-petty.github.io/devops-cli/github-pages.config.yaml` returns HTTP 404.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
