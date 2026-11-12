# Design

## Decisions

- Use `branches: ["**"]` on the `push` trigger. The pattern matches each branch, so the branch pushes that start the workflow do not change, and the trigger starts on no tag.
- Guard the cause over all workflows: a contract test refuses a `push` trigger that has a path filter and no branch or tag filter. The test reads each `.github/workflows/*.yml` file, so a new workflow gets the same check.

## Rejected alternatives

- `tags-ignore: ["**"]`: with only a tag filter, the workflow starts on no branch push (the same GitHub rule as above). That removes the run that checks a change to the workflow file.
- `branches: [main]`: this also stops the release tag runs, but it changes which branch pushes start the workflow. The issue keeps the branch behavior, and the `pull_request` trigger checks a topic branch.
- Remove the `push` trigger: the run on `main` after a merge shows that the default branch, which the Copilot cloud agent uses, still sets up. The issue keeps it.
