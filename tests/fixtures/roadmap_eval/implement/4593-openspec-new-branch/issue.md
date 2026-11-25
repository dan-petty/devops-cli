### Problem Description

`devops openspec new <issue>` prints "Created openspec/changes/<change> on branch <branch>." The branch in this sentence is the branch name that the command computes from the issue title with `branch_name`. The command does not create, switch to or read that branch. When the checkout is on another branch, the output states a false fact.

Source: `scaffold` in `src/devops_cli/openspec/scaffold.py` computes `branch = branch_name(issue, type_, slug)` and returns it. `new_next_steps` in `src/devops_cli/lang/en/messages.py` formats it as "Created {folder} on branch {branch}." and again as "Branch: {branch}".

### Reproduction Steps

1. `git worktree add <path> -b fix/4498-same-name-test-path origin/main`
2. In that worktree: `uv run devops openspec new 4498`
3. `git branch --show-current`

### Expected vs Actual Behavior

Expected: the output names the current branch, or states that the computed name is a suggestion and that the current branch has another name.

Actual: the output says "Created openspec/changes/4498-name-the-same-name-file-of on branch fix/4498-name-the-same-name-file-of." `git branch --show-current` gives `fix/4498-same-name-test-path`, and no branch `fix/4498-name-the-same-name-file-of` exists.

### Environment Diagnostics

- DevOps CLI: main at 5f75d256
- Execution environment: devcontainer, git worktree

### Logs, Traces, or Terminal Output

```shell
✓ Created openspec/changes/4498-name-the-same-name-file-of on branch fix/4498-name-the-same-name-file-of.

Branch:  fix/4498-name-the-same-name-file-of
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-13: none.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=b15faabb76277bff8bae0b2f4d7182a15ef6ac3a -->
## Proposed design

### Problem statement
`devops openspec new <issue>` prints that it created the change folder on a branch, and the branch name in that sentence is computed from the issue title. The command never creates, switches to or reads that branch, so a checkout on another branch reads a false fact, and the change folder can hold a slug that differs from the slug of the worktree branch. The command must name the branch of the checkout and take the change folder slug from that branch when the branch names the same issue.

### Acceptance criteria

### Requirement: The output names the branch of the checkout
`devops openspec new` SHALL name the branch that the checkout is on in its output.

#### Scenario: Checkout on the default branch
- **WHEN** The checkout is on `main` and the user runs `devops openspec new 4593 --title "fix(openspec): alpha"`.
- **THEN** The output holds `Created openspec/changes/4593-alpha on branch main.` and `Branch:  main`.

### Requirement: The change folder takes its slug from the branch of the issue
The command SHALL take the slug of the change folder from the branch of the checkout when that branch is `<type>/<issue>-<slug>` for the same issue.

#### Scenario: The branch slug differs from the title slug
- **WHEN** The worktree is on `fix/4593-alpha` and the user runs `devops openspec new 4593 --title "fix(openspec): beta"`.
- **THEN** The command creates `openspec/changes/4593-alpha/` and creates no folder `openspec/changes/4593-beta/`.

### Requirement: The output marks the computed name as a suggestion
The command SHALL state that the computed branch name is a suggestion and that the checkout is not on it, when the branch of the checkout does not name the same issue.

#### Scenario: Checkout on a branch of another issue
- **WHEN** The checkout is on `docs/5225-adr-front-matter-and-rules` and the user runs `devops openspec new 4593 --title "fix(openspec): alpha"`.
- **THEN** The output holds `Branch:  docs/5225-adr-front-matter-and-rules` and `The branch fix/4593-alpha is a suggestion for this change. This checkout is not on it.`

### Requirement: A checkout with no branch names no branch
The command SHALL state that the checkout is on no branch when HEAD is detached.

#### Scenario: Detached HEAD
- **WHEN** The checkout has a detached HEAD and the user runs `devops openspec new 4593 --title "fix(openspec): alpha"`.
- **THEN** The output holds `Branch:  HEAD detached` and no `on branch`, and the command creates `openspec/changes/4593-alpha/`.

### Requirement: The dry run names the folder and the branch of a real run
The dry run SHALL name the folder and the branch that a real run creates in the same checkout.

#### Scenario: Dry run in a worktree on the branch of the issue
- **WHEN** The worktree is on `fix/4593-alpha` and the user runs `devops openspec new 4593 --dry-run --title "fix(openspec): beta"`.
- **THEN** The output holds `Would create openspec/changes/4593-alpha on branch fix/4593-alpha.` and `Branch: fix/4593-alpha`, and the command creates no folder.

### Existing Tool Considered
No open tool covers the need: the alternatives check of 2026-11-13 found none. GitPython (``https://pypi.org/project/GitPython``) can report the active branch, but it formats no message and reconciles no slug, and the project removed it for one git seam (`docs/TESTING.md:80`). The project builds the change itself, on helpers that already exist: `current_branch` reads the branch and `parse_branch` parses it. Written cost: about 5k tokens to build, keep and fix the code, and about 2 hours of elapsed time.

### Key questions
- **Which git command reports the branch of the checkout?**: `git branch --show-current` reports it, and it prints nothing when HEAD is detached. The project already wraps it as `current_branch(repo_dir)`, which returns an empty string on a detached HEAD, and `commands/repos.py` renders that as `HEAD detached`. [sources: src/devops_cli/git/operations.py:278, src/devops_cli/git/operations.py:280, src/devops_cli/commands/repos.py:92]
- **Which branch name does `devops openspec new` report?**: The branch of the checkout, read with `current_branch`. The folder is written into the working tree of that branch, so the sentence is true in every checkout. (best practice) [sources: src/devops_cli/openspec/scaffold.py:172, src/devops_cli/commands/openspec.py:126, src/devops_cli/git/operations.py:278]
  - Chosen: The branch of the checkout. The command writes the folder into the working tree of that branch, so the name is true.
  - Rejected: The computed `<type>/<issue>-<slug>` name. The command creates no branch and switches to none, so the output states a false fact, which is the defect.
  - Rejected: No branch name at all. The user then loses the name of the branch that the change belongs to, and the next steps name no branch.
- **Where does the slug of the change folder come from?**: From the branch of the checkout when `parse_branch` reads that branch as `<type>/<issue>-<slug>` for the same issue; otherwise from the issue title, as today. CONTRIBUTING.md makes the branch slug the slug of the change folder, and the implement job makes the branch with the slug of the folder. (best practice) [sources: CONTRIBUTING.md:216, CONTEXT.md:122, src/devops_cli/git/branch_form.py:59]
  - Chosen: The slug of the branch of the checkout. The folder and the branch then hold the same slug, and the implement job derives the branch `<type>/<issue>-<slug>` from the folder.
  - Rejected: The slug of the issue title always. The folder and the worktree branch hold different slugs, and the implement job derives a branch name that no worktree has.
- **What does the command print when the checkout is on another branch or on no branch?**: It names the branch of the checkout, or `HEAD detached` when HEAD is detached, which is the wording `commands/repos.py` already uses. It then states that the computed `<type>/<issue>-<slug>` is a suggestion and that the checkout is not on it. (best practice) [sources: src/devops_cli/commands/openspec.py:126, src/devops_cli/commands/repos.py:92, src/devops_cli/git/branch_form.py:59]
  - Chosen: State the computed name as a suggestion. The user learns the branch name that the roadmap jobs use, and no sentence claims that the command made that branch.
  - Rejected: Print the computed name with no note. It repeats the false fact of the defect.
  - Rejected: Create the branch and switch to it. The command writes files only, and the roadmap jobs own the branch of an item; a switch would move the working tree of the user.
- **How does `ScaffoldResult` carry the two names?**: It keeps `branch` as the computed `<type>/<issue>-<slug>` and adds `current_branch`, which is `None` on a detached HEAD (from `current_branch(root) or None`). The command reads both. (best practice) [sources: src/devops_cli/openspec/scaffold.py:25, tests/openspec/test_openspec_new.py:368]
  - Chosen: Add `current_branch` and keep `branch`. The callers and the tests that read `branch` keep their meaning.
  - Rejected: Change `branch` to the branch of the checkout. It silently changes the meaning of the field for every caller and for the tests that read it.
- **Which code reads the branch of the checkout and which code parses it?**: The helpers that already exist: `current_branch` in `git/operations.py` reads the branch through the one git seam, and `parse_branch` in `git/branch_form.py` returns its type, issue and slug. `scaffold.py` calls both and starts no git command of its own. (best practice) [sources: src/devops_cli/git/operations.py:278, src/devops_cli/git/branch_form.py:59, docs/TESTING.md:80]
  - Chosen: Reuse `current_branch` and `parse_branch`. Both exist, and the read goes through the one git seam that the invariant test enforces.
  - Rejected: A new subprocess call in `scaffold.py`. It repeats the branch types and the slug rule in a second place and starts git outside the seam.
- **Where does the command build its output text?**: Inline in `new_cmd`, at `commands/openspec.py:120` for the dry run and `:126` for the real run. `MESSAGES.openspec.new_dry_run_output` and `new_next_steps` hold the same text, and nothing reads them. [sources: src/devops_cli/commands/openspec.py:120, src/devops_cli/commands/openspec.py:126, src/devops_cli/lang/en/messages.py:553, src/devops_cli/lang/en/messages.py:554]
- **Where does the new wording live?**: In `MESSAGES.openspec.new_dry_run_output` and `new_next_steps`, formatted from `new_cmd`. The other openspec commands already print their text from that catalog, and the catalog already holds both messages. (best practice) [sources: src/devops_cli/commands/openspec.py:75, src/devops_cli/lang/en/messages.py:553, src/devops_cli/lang/en/messages.py:554]
  - Chosen: The message catalog. The other openspec commands print from `MESSAGES.openspec`, and the two messages are already defined there, so the text has one home.
  - Rejected: The inline strings of `new_cmd` only. It leaves two copies of the same text, and the catalog entry that the issue names keeps the old wording.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.adr_hash": "a1cd29eb2588913c344a50dcec7edc599fc9cc39aed976ed694194eb1398099a", "alternatives.body_hash": "14e058fd41136367a8edcd59d939f2d3aedb47bdfcd6a9a7cb15bd10af015a54", "alternatives.checked_at": "2026-11-13T00:09:50.769304+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": null, "alternatives.tool_id": null, "alternatives.verdict": "none", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "14e058fd41136367a8edcd59d939f2d3aedb47bdfcd6a9a7cb15bd10af015a54", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.returned_body_hash": null, "refine.rules": "2026-11-06T19:25:37+00:00", "refine.section_hash": "8a99d880377f07a311981573bbbceab49259abea4052a6d8e01cdba6034055bc"} -->
