## Why

Issue #2800 reports that `devops pr create` warns about a scope with no label. The pull request gets no scope label. The first case was the scope `git`. A later comment on the issue reports the same warning for the scope `agents`.

PR #2821 declared `scope/git`. It added no check, so the same warning came back for the next scope. A scope of a title is free text. Nothing refuses a scope that `.github/labels.yml` does not declare. The warning of `devops pr create` comes after the pull request is open, and nobody has to act on it.

This change fixes the cause. The `Semantic PR title` check accepts only the scopes that the label file declares. The change also declares the scopes that the project uses again and again.

## What Changes

- `.github/labels.yml` declares 15 more scopes: `agents`, `argo`, `cloudflare`, `docker`, `exceptions`, `gh`, `lint`, `openspec`, `pr`, `rag`, `repos`, `sandbox`, `tests`, `ui` and `vault`.
- `.github/workflows/pr-title.yml` sets the `scopes` input of the title action to the declared scopes, and to `main`, the scope of the title of the release pull request.
- A test of the workflow contract fails when the list of the workflow and the scope labels of the file differ.
- `CONTRIBUTING.md` says that the scope of a title is one of the declared scopes.
- The change has no spec delta. It changes a CI workflow and a configuration file, and no command, option or message (`skip_specs: true`).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- None.

## Impact

A pull request title with an unknown scope fails the `Semantic PR title` check. The error names every allowed scope. The author picks a declared scope, or declares the new scope in the same pull request. A title with no scope still passes. `devops pr create` keeps its warning for a title that the author edits after the pull request opens.

## Feasibility

Evidence of the scopes in use. The titles of the 199 newest merged pull requests and of the 169 open issues (read with `devops gh api`, one page per call on 2026-10-31) use 52 distinct scopes. 19 of them have a label. 33 have none: the 15 below, which are used twice or more, 17 scopes used once, and `main`.

| Scope | Uses | Scope | Uses |
| :--- | ---: | :--- | ---: |
| `sandbox` | 5 | `docker` | 3 |
| `repos` | 5 | `agents` | 3 |
| `rag` | 5 | `vault` | 2 |
| `argo` | 5 | `ui` | 2 |
| `pr` | 4 | `lint` | 2 |
| `gh` | 4 | `exceptions` | 2 |
| `tests` | 3 | `cloudflare` | 2 |
| `openspec` | 3 | | |

The other undeclared scopes are used once: `warnings`, `tf`, `testing`, `test`, `settings`, `scan`, `output`, `models`, `image`, `hardening`, `gate`, `floor`, `fail-to-pass`, `coverage`, `core`, `argocd` and `architecture`. The scope `main` is the scope of the release pull request that release-please opens (`chore(main): release 0.26.0`).

The premise of the issue for `git` no longer holds: `.github/labels.yml` declares `scope/git` since PR #2821, and the issue is closed. The comment on the issue (`scope/agents`) still holds, and so does its second option: "make the title scope check list every scope in use".

The `scopes` input of the title action was read in the source of the pinned release (`amannn/action-semantic-pull-request` at `48f256284bd46cdaab1048c3721360e808335d50`, `README.md` and `src/validatePrTitle.js`). It takes a newline-delimited list of patterns. The action wraps each pattern in `^` and `$`. It splits a title scope at commas and checks each part. A title with no scope passes when `requireScope` is off, which is the default. On an unknown scope, the action fails with the message `Scope must match one of: ...`.

The open pull requests (one `k8s` title and the release pull request with the scope `main`) pass the new rule.

The change fits one pull request: one label file, one workflow, one test and one paragraph of CONTRIBUTING.md.

## Existing Tool Considered

The tool is `amannn/action-semantic-pull-request`, which the repository already runs. Its `scopes` input is the standard way to hold the scope vocabulary of Conventional Commits (the same role as `scope-enum` of commitlint). The change builds no parser and no new check. The list in the workflow repeats the names in the label file. One test holds the two lists equal, so a scope added to one place and not to the other fails the test. The change deletes no code.
