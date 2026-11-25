# Design

## The pattern

The hook fails when its pattern matches the branch name. The pattern is a negative lookahead, so it matches each name that is not `<type>/<issue>-<slug>`:

```text
^(?!(?:feat|fix|perf|refactor|revert|docs|test|build|ci|style|chore)/[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*$)
```

`main` stays in the first entry (`--branch main`) and is also refused by the pattern. A detached `HEAD`, as in a rebase, has no branch name, and the hook passes. The failure line shows the name of the hook: `branch name is <type>/<issue>-<slug> (CONTRIBUTING.md, Naming)`.

A commit on a branch that breaks the form is refused. The fix is `git branch -m <type>/<issue>-<slug>`.

## Scope of the rule

The rule covers the branches that a person or an agent pushes to this repository. GitHub makes the branches of bots (`release-please--*`, `renovate/*`), and nobody commits on them locally, so the hook never reads them. `devops branches jira` (`feature/<TICKET>-<slug>`) and `devops scan fix` (`fix/security-<package>-<cve>`) name branches in other repositories, with the form of those repositories.

## Rejected alternatives

- **A CI check of `github.head_ref`.** The check would run for the branches of bots, which need an exemption list, and it would report a name after the commits exist. The hook refuses at the first commit.
- **The pre-push stage.** `test_the_pre_push_hook_runs_only_the_fast_static_checks` holds that stage to the fast `devops ci` checks. A hook there needs an exception to that test.
- **A check in `devops pr create`.** It is new code for a check that an open tool gives, and it reads the name after the work is done.
- **The Git Flow prefixes (`feature/`, `hotfix/`, `release/`).** They are not the types of the pull request title, and the project has no release branches. A branch type that is the title type keeps one list.
- **An exemption for bot branches in the pattern.** The hook runs on local commits, and bots make none.
- **Changing `devops branches jira` and `devops scan fix`.** They name branches of other repositories.
- **A rule for each artifact without a check.** The table says "None" for them. A rule with no check is a convention, and a check for it is a separate item.
