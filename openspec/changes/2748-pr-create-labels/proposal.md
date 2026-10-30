# Proposal

## Why

Issue #2748. No code gives a pull request its `type/*` and `scope/*` labels. The author adds them by hand, and often copies the old type of the issue. Pull request 2738 has the title `fix(ai): ...` and the labels `type/security` and `scope/security`. Its scope is `ai`, and its type is `fix`. The audit in `github/labels.py` and the hardening audit then read labels that disagree with the title.

Issue #2715 made the title the only source of the labels of an issue. A pull request has no such rule. This change gives `devops pr create` the same rule.

## What Changes

- `devops pr create` adds to the new pull request the labels that its title gives. `fix(ai): ...` gets `type/bug` and `scope/ai`. A title with no scope gets only the type label. A title with no Conventional Commit type gets no label.
- A scope that `.github/labels.yml` does not declare gets no label. The command prints a warning that names the label and the file. The command still exits 0.
- The declared labels come from `.github/labels.yml` of the repository on the base branch, as intake reads them. They do not come from the local checkout, so `--repo` works for another repository.
- The rule is one function, `title_labels` in the new module `roadmap/title_labels.py`. Intake calls it too. The mapping from title to label stays in `CONST_ROADMAP_COMMIT_TYPE_LABELS`. The parse of the label file moves out of intake into the same module.
- A label is added with `RoadmapStore.label_issue`. It posts to the `issues/{number}/labels` endpoint, which GitHub also uses for pull requests. The in-memory store accepts a pull request number for this call, as GitHub does.
- The pull request exists when the labels are added. When the label file cannot be read, or a label cannot be added, the command prints an error that names the pull request, the labels, and the reason. It exits 1. It never closes or deletes the pull request. The write of the Status (#2717) and the write of the labels both run. Each failure is reported, and the exit status is 1 if either failed.
- A dry run changes nothing: `gh pr create` returns a planned request with no number, so the command reads and writes no label.
- The stage job and the implement job open pull requests through their own client. They do not use this helper in this change (see Design). A follow-up item covers them.
- The change carries a spec delta, because a command, its messages and its exit status are observable. It adds the capability `pr-title-labels`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `pr-title-labels`: the labels that `devops pr create` gives a pull request from its title, and what it does when a label cannot be added.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/title_labels.py` (new), `src/devops_cli/roadmap/pull_labels.py` (new), `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_pr_title_labels.py` (new).
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The defect is real. `devops gh api repos/dan-petty/devops-cli/pulls/2738` shows the title `fix(ai): the mcp benchmark tool takes no file path` and the labels `type/security` and `scope/security`. Pull request 2746 has the title `fix(security): ...` and the label `type/security`, but the type of a `fix` title is `type/bug`.
- No code adds a label to a pull request. A search of `src/` for the labels endpoint finds one builder, `label_args` in `roadmap/github_store.py`. Only intake calls `label_issue`. `gh pr create` in `commands/pr.py` passes no `--label`.
- The rule exists and can be reused. `_title_labels` in `roadmap/intake.py` maps the title with `commit_type`, `commit_scope` and `CONST_ROADMAP_COMMIT_TYPE_LABELS`, and checks the result against the labels of `.github/labels.yml`. It needs only the title and the declared names, so a pure function can serve both callers.
- The endpoint takes a pull request. `label_args` posts to `repos/{repo}/issues/{number}/labels`, and a pull request is an issue for this endpoint. The issue text states the same.
- The declared file is readable for any repository. `RoadmapStore.repository_file(path, ref=...)` reads the raw file through the contents API on a given ref, and it raises `GitHubFileNotFoundError` for a missing file.
- `.github/labels.yml` declares every type label of the mapping, and a scope label for each of `ai`, `security`, `cli`, `roadmap` and the others.
- In a dry run, `run_subprocess` returns a `PlannedProcessResult` with an empty `stdout` for the mutating `gh pr create`. The command then finds no pull request number and sends no label request.
- The first check the change runs is `uv run devops ci test tests/test_pr_title_labels.py`.

## Existing Tool Considered

`gh pr create --label` adds labels in the same call. It is rejected for three reasons. It does not apply the rule: the caller must still map the title and check the declared file. It uses GraphQL, which `devops pr create` already leaves for REST when the quota is out (`_fallback_create_pr`), and the REST `POST /pulls` call has no label field. And it runs before the pull request exists, so a label problem would stop a pull request that the author wants. The issues labels endpoint covers both paths.

Python has no maintained package for the Conventional Commit form of a title; `roadmap/commit_title.py` already states this. The change reuses `commit_type`, `commit_scope`, `CONST_ROADMAP_COMMIT_TYPE_LABELS` and `LabelSpec`, and moves the rule out of intake into a function that both callers use. It deletes the private copy of the rule in `_title_labels` and the parse of the label file in `_Run.declared`. It builds no new parser.
