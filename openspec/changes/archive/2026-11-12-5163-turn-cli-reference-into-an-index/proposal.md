# Proposal: #5163 Turn CLI_REFERENCE into an index of the command group pages

## Why
#5163: `docs/CLI_REFERENCE.md` is one generated page that holds the full text of every command. A reader, a page fetch and the docs site cannot use it well, and a web fetch reads only the first 100,000 characters. The 43 generated pages in `docs/commands/` already hold each command group. `README.md` also holds a generated command matrix that `devops docs generate --sync-readme` and `devops docs sync-readme` write. The owner approved the held row of #4880 on 2026-11-12.

## What Changes
- `devops docs generate` writes `docs/CLI_REFERENCE.md` as a short index: one row for each command group, with its one-line help and a link to `commands/<group>.md`, and then the command matrix, with one row for each command. The full text of each command stays only on the page of its group. The page of a group also gets the description of the group, which only the old CLI reference held.
- The command matrix moves out of `README.md` into the CLI reference. `README.md` links the CLI reference and holds no generated block. The command row of `AGENTS.md` links the CLI reference too, so each group page stays within two links of `AGENTS.md`. The row of the knowledge base drops `devops <command> --help` to stay within the 6,500-character cap, because the group pages hold the same text.
- The README sync is deleted with no shim: the command `devops docs sync-readme`, the options `--sync-readme/--no-sync-readme` of `devops docs generate` and `--check-readme/--no-check-readme` of `devops docs check`, and the generator functions `render_synced_readme`, `sync_readme`, `check_readme`, `_check_readme_matrix_content` and `_find_readme`. `devops ci docs --fix`, the `docs` row of `devops ci`, the implement job, its request plan, the stage plan text and the scaffold checklist run `devops docs generate`.
- `devops docs check` checks the new index as each other generated page. The `CLI reference` tab of the docs site opens on the index.
- Each living file that names `--sync-readme` names `devops docs generate`. ADR 0025 gets a note at its top.
- A command and its options are observable, so the change carries spec deltas.

## Capabilities
- `docs-cli-reference` (new): the CLI reference is an index of the command group pages, `README.md` holds no generated block, and the site tab opens on the index.
- `command-dry-run-class`: `docs-no-external-request` names `docs check` and `docs generate` only.
- `new-command-scaffold`: the checklist names `devops docs generate`.
- `roadmap-implement-job/pull-request`: the docs step runs `uv run devops docs generate`.
- `roadmap-stage/task-groups`: a documentation task ends with `uv run devops docs generate`.

## Impact
- `docs/CLI_REFERENCE.md` falls from 421,673 to 56,887 characters at `050a6ef72`. `README.md` falls from 66,508 to 14,715 bytes.
- A script or a person that runs `devops docs generate --sync-readme` or `devops docs sync-readme` gets a usage error. The implement job runs the command of the checkout, so an old runner image on a new `main` stops at the docs step until the image of this change rolls out.
- The change fits one pull request.

## Feasibility
- `wc -c docs/CLI_REFERENCE.md` at `8fdeea033` printed 419,983 bytes (419,891 characters), more than the 343,000 characters that the issue gives. The block between the matrix markers of `README.md` held 364 lines and 51,581 bytes.
- `DocGenerator().introspect_all_groups()` returned 43 groups, and `ls docs/commands` listed 43 pages, one for each group. Seven groups have a description that is not their summary, and only the old CLI reference showed it.
- `git grep -l -e sync-readme` at `8fdeea033` listed 718 files: 589 under `openspec/changes/archive/`, 14 in 9 active change folders, 76 under `tests/fixtures/roadmap_eval/`, 3 ADRs, 1 file under `docs/agent/archive/` and 35 other files. `CONST_DOCS_INVENTORY` classes the change folders, the eval fixtures, the ADRs and the agent archive as records ("history, never rewritten"), so they keep the old name. The 35 other files change (the 4 specs through the archive of this change), but for 2 recorded inputs: the log excerpt of #3484 in `tests/roadmap/test_roadmap_failure.py` and the refused finding in `tests/fixtures/roadmap/stage_refused_findings.json`. Of the eval fixtures, only the good plan of the case `good-3264-the-stage-marks-a-plan-ready` changes: the `paths` gate resolves each cited command against the live command tree, and a good plan must pass every gate. The other fixtures record bad plans and model output.
- `uv run --group docs devops docs site build --strict` (Zensical 0.1.1) built 108 pages with "No issues found", and the built index links `../commands/repos/`.
- #4781 is open with no pull request. It changes `_commit_if_changed` in `src/devops_cli/roadmap/implement/implement_run.py`. This change edits only the argv of `_generate_docs` in that file.

## Existing Tool Considered
No new tool. The generator already writes the group pages and the matrix, and the awesome-nav plugin of Zensical builds the tab from `.nav.yml`. The change deletes internal code: the README marker functions, the `sync-readme` command and the README options.
