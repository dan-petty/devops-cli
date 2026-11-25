### Friction

Every push runs the full local gate (`uv run devops ci`) in the pre-push hook. Measured on 2026-10-24 from the CI cache entries of the 75 passing gates of the last 24 hours (host: 16 CPUs, several agents at once):

- The sum of the check durations: median 23 min, p90 39 min, max 70 min. The checks run in parallel, but `test` alone had a median of 7.2 min (max 24 min), and `security` a median of 5.9 min (max 28 min).
- Nothing limits how many gates run on the host at once, and each gate's pytest uses every CPU. The load average reached 88.
- The gate cache cannot help an agent push: every push follows a rebase or an amend, so the content is new. In 7 days, 1 of 186 passing gates verified content that another worktree had already verified.
- Under that load, tests that wait for a time window fail (#2069, #2092), and the whole gate runs again.

### Decision (owner, 2026-10-22, in #1752)

The pre-push hook runs only the fast static checks (`ruff`, format, `actionlint`, `zizmor`). The full `uv run devops ci` stays a manual command. Remote CI is the authoritative gate (ADR 0004). The change to the pre-push hook can land after the required checks of `main` gate every topic pull request.

That condition holds: on 2026-10-24 the `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`.

### What should happen

- The pre-push hook `devops-ci-pre-push` runs only the fast static checks, in seconds.
- AGENTS.md rule 5 and the documents that say the pre-push hook runs the full gate (docs/SDLC.md Phase 4 and Phase 6, CONTRIBUTING.md, docs/TESTING.md, and any other) say what runs where: the fast static checks before a push, the required checks of CI before a merge, and the full `devops ci` by hand.
- A test holds that the pre-push hook runs only the fast static checks.

### Acceptance criteria

- [ ] `git push` of a branch runs only the fast static checks, and a measured push takes less than 1 minute on a quiet host.
- [ ] No document says that the pre-push hook runs the full gate.


Source: https://github.com/dan-petty/devops-cli/issues/1752
