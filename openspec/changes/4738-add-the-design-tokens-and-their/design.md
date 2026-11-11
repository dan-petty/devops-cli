# Design

## Decisions
- The tokens are three DTCG files with no reference between files, so each Style Dictionary config reads one file, and the build needs no resolver.
- The light and the dark theme are separate files with the same names. A test compares the names in the sources, in the flat JSON and in each CSS file, because a name that one theme lacks draws with no value in that theme.
- The build writes each CSS file twice: to `docs/assets/css/` for Jekyll, which cannot run the build, and to `src/devops_cli/design/` as package data. A test compares the two copies. `src/devops_cli/design/css/` holds only hand-written CSS.
- The CI job installs the lock in the temporary folder of the runner, so `node_modules` never shows in the diff. `git add --intent-to-add` before `git diff --exit-code` makes a new output that is not committed fail the job.
- The lock is no entry of `tools.lock`, because Renovate cannot edit `tools.lock`, and the owner decided that Renovate updates this lock (decision 9 of #4735). A later Renovate rule for this one `package.json` wins over the rule that stops npm updates.
- The ast-grep rule holds `src/devops_cli/design/css/`, the hand-written CSS of the package. The construct gate gets a violation table entry with a `.css` file, because its other rules are Python rules. The docs site and start page items extend the rule to their CSS when they remove their literals.
- `AGENTS.md` is at its budget of 6,500 characters, so the new row comes with two shorter phrases of the same meaning.

## Rejected alternatives
- A path filter on the workflow: `ci.yml` holds the other jobs, and a job filter with `dorny/paths-filter` is the form of the job "Docs Site Build".
- `npm ci` in the lock folder: it writes `node_modules` under `src/`, which `.gitignore` does not exclude and the wheel build would take.
- A rule for all CSS with `ignores` for the generated `tokens-*.css`: the construct gate refuses `ignores` (#1902), and its scan covers only `src` and `tests`.
