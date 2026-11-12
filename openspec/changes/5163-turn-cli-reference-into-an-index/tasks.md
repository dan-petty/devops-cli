# Tasks

## 1. The CLI reference is an index, and the README sync is gone

- [ ] 1.1 Add failing tests: the index rows and the matrix rows of the CLI reference, the description on the group page, no README command or option in `devops docs`, the README link, no `README.md` from the generator, and the nav of the `CLI reference` tab
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py tests/docs/test_docs_inventory.py tests/github/test_github_pages.py`
- [ ] 1.2 Render the CLI reference as the index and the command matrix, put the group description on the group page, and delete the README sync from the generator, `devops docs`, `devops ci docs`, the help and the messages
  - Verification: `$ uv run devops ci test tests/docs tests/github/test_github_pages.py tests/commands/test_config_workspace_docs_dry_run.py tests/commands/test_ci_dry_run.py`
- [ ] 1.3 Run `devops docs generate` in the implement job, its request plan, the stage plan text and the scaffold checklist
  - Verification: `$ uv run devops ci test tests/roadmap tests/commands/test_new.py tests/commands/test_roadmap_eval_implement.py`

## 2. Documents

- [ ] 2.1 Move the matrix out of `README.md`, link the CLI reference from `README.md` and `docs/index.md`, open the site tab on the index, name `devops docs generate` in each living file that named `--sync-readme`, add the note to ADR 0025, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
