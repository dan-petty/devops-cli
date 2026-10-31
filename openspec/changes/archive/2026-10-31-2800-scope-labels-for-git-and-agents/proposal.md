## Why

Issue #2800 reports that `devops pr create` warns about a scope with no label. The pull request gets no scope label. The first case was the scope `git`. A later comment on the issue reports the same warning for the scope `agents`.

PR #2821 declared `scope/git`. It added no check, so the same warning came back for the next scope. A scope of a title is free text. Nothing refuses a scope that `.github/labels.yml` does not declare. The warning of `devops pr create` comes after the pull request is open, and nobody has to act on it.

This change fixes the cause. The `Semantic PR title` check accepts only the scopes that the label file declares. The change also declares the scopes that the project uses again and again.

## What Changes

- `.github/labels.yml` declares 22 more scopes: `agents`, `argo`, `argocd`, `cloudflare`, `contributing`, `docker`, `exceptions`, `fail-to-pass`, `gate`, `gh`, `lint`, `openspec`, `output`, `pr`, `rag`, `repos`, `sandbox`, `scan`, `sdlc`, `tests`, `ui` and `vault`.
- `.github/workflows/pr-title.yml` sets the `scopes` input of the title action to the declared scopes, and to `main`, the scope of the title of the release pull request.
- A test of the workflow contract fails when the list of the workflow and the scope labels of the file differ.
- `CONTRIBUTING.md` and `docs/SDLC.md` say that the scope of a title is one of the declared scopes. Two title examples in the docs use declared scopes.
- The delivery pull request of the implement job drops a scope that the labels file does not declare, so a one-off scope in an issue title cannot fail the check.
- The spec `roadmap-implement-job` changes one requirement: the delivery title leaves out an undeclared scope.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `roadmap-implement-job`: the title of the delivery pull request keeps only a declared scope.

## Impact

A pull request title with an unknown scope fails the `Semantic PR title` check. The error names every allowed scope. The author picks a declared scope, or declares the new scope in the same pull request. A title with no scope still passes. The implement job makes the title of its pull request from the issue title, and it leaves out a scope that no label declares. The issue keeps its title. `devops pr create` keeps its warning for a title that the author edits after the pull request opens.

## Feasibility

Evidence of the scopes in use. The subjects of the 549 commits of `origin/main` (`git log origin/main --format=%s`) and the titles of the 170 open issues (read with `devops gh api`) were counted on 2026-10-31. They use 61 distinct scopes, and 22 of them had a label before this change. The rule is that a scope used twice or more, in the two sources together, is declared. 22 scopes with no label meet the rule:

| Scope | Uses | Scope | Uses |
| :--- | ---: | :--- | ---: |
| `tests` | 8 | `openspec` | 4 |
| `repos` | 8 | `gh` | 4 |
| `rag` | 7 | `docker` | 3 |
| `argo` | 6 | `contributing` | 3 |
| `agents` | 6 | `vault` | 2 |
| `sandbox` | 5 | `ui` | 2 |
| `scan` | 4 | `sdlc` | 2 |
| `pr` | 4 | `output` | 2 |
| `lint` | 2 | `gate` | 2 |
| `fail-to-pass` | 2 | `exceptions` | 2 |
| `cloudflare` | 2 | `argocd` | 2 |

The other undeclared scopes are used once and are left out: `warnings`, `tf`, `testing`, `test`, `settings`, `models`, `llm`, `image`, `hardening`, `floor`, `dependabot`, `dashboard`, `coverage`, `core`, `cache`, `architecture` and `adr`. The scope `main` is the scope of the release pull request that release-please opens (`chore(main): release 0.26.0`).

A first count used the 199 newest merged pull requests and the open issues. That window was too short: it missed `scan`, `contributing`, `sdlc`, `fail-to-pass`, `argocd`, `output` and `gate`. The count above uses the whole history of `origin/main`.

The implement job copies the type and the scope of the issue title into the title of its pull request (`delivery_title`). Open issues hold 12 scopes that no label declares, each used once. A delivery pull request for such an issue would fail the new check. The change therefore makes `delivery_title` leave out a scope that the labels file on the default branch does not declare. Intake is not changed: it keeps its note that names the label to add, and it never refuses an issue.

The premise of the issue for `git` no longer holds: `.github/labels.yml` declares `scope/git` since PR #2821, and the issue is closed. The comment on the issue (`scope/agents`) still holds, and so does its second option: "make the title scope check list every scope in use".

The `scopes` input of the title action was read in the source of the pinned release (`amannn/action-semantic-pull-request` at `48f256284bd46cdaab1048c3721360e808335d50`, `README.md` and `src/validatePrTitle.js`). It takes a newline-delimited list of patterns. The action wraps each pattern in `^` and `$`. It splits a title scope at commas and checks each part. A title with no scope passes when `requireScope` is off, which is the default. On an unknown scope, the action fails with the message `Scope must match one of: ...`.

The open pull requests (one `k8s` title and the release pull request with the scope `main`) pass the new rule.

The change fits one pull request: one label file, one workflow, one function of the implement job, their tests and two paragraphs of documents.

## Existing Tool Considered

The tool is `amannn/action-semantic-pull-request`, which the repository already runs. Its `scopes` input is the standard way to hold the scope vocabulary of Conventional Commits (the same role as `scope-enum` of commitlint). The change builds no parser and no new check. The list in the workflow repeats the names in the label file. One test holds the two lists equal, so a scope added to one place and not to the other fails the test. The change deletes no code.
