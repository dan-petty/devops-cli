# Design

## Decisions

- **One function draft_readiness, with a kind enum and the recorded item, sits in src/devops_cli/roadmap/implement_pull.py beside mark_ready.**: The stage row and the implement job already import implement_pull, so one module holds the decision and the call that acts on it.
- **draft_readiness takes an optional list of extra check callables and refuses when one fails.**: The evaluator of #2867 plugs in as a check, and the function stays the single decision point.
- **The existing devops pr check-readiness reports the refusal as one blocker of the merge-readiness verdict.**: The command already exists and prints blockers with a non-zero exit, so a script or hook blocks the merge and the developer reads the unticked group.

## Rejected alternatives

- **Separate readiness functions per kind.**: Issue #2916 asks for one function as the only place that decides, and separate functions split the decision and the evaluator seam.
- **A new module src/devops_cli/roadmap/pr_readiness.py.**: implement_pull.py already holds mark_ready and both callers import it, so a new file splits the readiness logic across two modules for one function.
- **Add a second devops pr check-readiness command beside the existing one.**: search_code check_readiness showed the command at src/devops_cli/commands/pr.py:1472, so a second command would make the name decide two things.
- **Print a generic refuse message from check-readiness.**: The acceptance criteria of #2916 require the unticked group to be named so the developer knows what to fix.
