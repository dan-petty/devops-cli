# Design

## Decisions

- **The command lives in `devops roadmap` as `plan-check`.**: It reads a roadmap plan pull request and shares the stage gates, which live under `src/devops_cli/roadmap/`; `devops openspec` stays the gate of the OpenSpec tree and reads no pull request.
- **The plan reader builds a `StageProposal` from the change folder, and the gates stay unchanged.**: `check_proposal` and `validate_change` already take a `StageProposal` and the change files, so one reader joins the two, and the round-trip test against `render_change` bounds the file format. The writer does not put the estimate of a created file in `tasks.md`; the estimate is no gate input, so the reader gives each created path one line.
- **The command finds the change folder by the issue number in the `Plans #` line of the body.**: A change folder is named `<issue>-<slug>`, so the issue number names it, and a pull request that holds zero or more than one matching folder is a problem.
- **A moved base spec is found by comparing the base spec at the commit that added the change folder with the base spec at the pull request base.**: The parent of that commit is the tree the plan was written against, so a difference measures movement since the plan and not the delta that the change itself holds.
- **A missing `Semantic PR title` check is a problem, as a failed one is.**: `docs/adr/0004-ci-is-the-authoritative-gate.md` makes `Semantic PR title` a required check on `main`, so a plan pull request with no successful check cannot merge.
- **The body needs `Plans #` and must hold no closing keyword.**: A plan pull request closes no issue; `src/devops_cli/roadmap/stage_change.py` writes `Plans #<issue>` and holds `closing_keyword_in` to refuse a closing keyword.
- **Problems print as one line each with the file, the rule and the stage message, and `--json` prints objects with `path`, `rule` and `message`.**: A person reads a line in the terminal and an agent reads the JSON, and the message text comes from `MESSAGES.roadmap`, so the stage job and the command name a defect with the same words.

- **The command runs in a checkout of the repository, fetches `refs/pull/<number>/head` and reads the head files and the file list with `git show` and `git ls-tree`. The GitHub client gives only the title, the body, the base and the check runs.**: `validate_change` takes `source`, a checkout that holds the base specs, and `StagedTree` takes the tracked files of a checkout, so a run on API calls alone has neither. `--dry-run` lists the git commands and the requests.
- **A file that the reader cannot parse is a problem that names the file, and no crash.**: `render_change` drops facts that the reader must infer (the `kind` of a group, `process`, `documentation`), and a plan that a person edited may not match the writer's text. The command must report it and go on with the other files.

## Rejected alternatives

- **Put the command under `devops openspec`.**: `src/devops_cli/commands/roadmap.py` shows that each roadmap command opens the roadmap store and reads GitHub, and the gates and the change folder live under `src/devops_cli/roadmap/`; an `openspec` command would reach across that boundary for the stage gates.
- **Change `check_proposal` and `validate_change` to read raw files.**: `src/devops_cli/roadmap/stage_change.py` and `src/devops_cli/roadmap/stage_validate.py` take a `StageProposal` and a `Mapping[str, str]` of files today, so a raw-file path would split each gate in two and double the checks.
- **Write a `plan.json` at stage time and read it back.**: The plan pull requests that already exist hold no plan file, and `git show --stat` of merged plan pull request #3248 lists five files under `openspec/changes/` and no `plan.json`, so the command could not check them.
- **Accept `Plans #` or a closing keyword in the body.**: `CONTEXT.md` says a plan pull request closes no issue, and `closing_keyword_in` in `src/devops_cli/roadmap/stage_change.py` exists to refuse one, so accepting `Closes` would close the issue when the plan merges.
- **Report only a failed `Semantic PR title` check and not a missing one.**: `docs/adr/0004-ci-is-the-authoritative-gate.md` lists `Semantic PR title` among the required checks of the `main` ruleset, so a pull request with no such check cannot merge.
