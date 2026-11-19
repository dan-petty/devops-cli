# Design

## Decisions
- Map `MissingParameter` from strict `make_context` to `CommandReferenceDefect.MISSING_REQUIRED`.
- Report both missing required options and missing required arguments when parameters are omitted.
- Skip bare command mentions with no tokens after the command path so prose mentions remain valid.
- Treat placeholders (such as `<issue>`) as arguments only, ensuring they do not satisfy missing required options.
- Update skill and documentation references to supply required options and arguments:
  - `.agents/skills/devops-pr-ci/SKILL.md` line 26: add `--summary "<summary>"`.
  - `.claude/skills/devops-pr-ci/SKILL.md` line 26: add `--summary "<summary>"`.
  - `.kilocode/skills/devops-pr-ci/SKILL.md` line 26: add `--summary "<summary>"`.
  - `docs/ROADMAP_WORKFLOW.md` line 281: add `<args>`.
  - `docs/ROUTINE_TASKS.md` line 291: add `<args>`.
  - `docs/roadmap/implement.md` line 105: add `<args>`.
  - `docs/roadmap/onboard.md` line 9: specify endpoint `repos/<repo>` and flag `-f has_issues=true`.
  - `k8s/README.md` line 190: add required option `--title "<title>"`.

## Rejected alternatives
- Separate validator outside Click: Rejected because Click already inspects parameters and handles parameter conversion.
- Only check options: Rejected because missing required arguments also cause CLI runtime errors.
- Flag bare mentions: Rejected because prose frequently names commands without executing arguments.
