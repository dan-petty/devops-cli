# Proposal

## Why

Issue #3198: the title and the body of a pull request are free text, and they break the form of the project often. `devops pr create` passes `--title` and `--body` to `gh` and checks neither. CONTRIBUTING.md section 4 sets the form: a Conventional Commit title with a summary of at most 60 characters and a scope that `.github/labels.yml` declares, and a body of at most 1,000 characters that ends with `Closes #<issue>` and the `Change:` line. In one session of agent work, the first drafts of several titles had a summary over 60 characters, and a body put the attribution lines before `Closes`. The `Semantic PR title` check catches a bad title only after the pull request is open, and no check reads the body. A model that writes `x` or `placeholder` for a text gets a pull request with that text (#3167, #3174, #3175).

## What Changes

- A new module `src/devops_cli/roadmap/pull_form.py` holds the rules of the form: `title_problems`, `body_problems`, `build_title` and `build_body`. It reads no file and makes no request. It cuts no text: a text that breaks a rule is refused with every problem named, and the caller writes a shorter one.
- A new command `devops pr describe <issue> --summary <text>` reads the issue (type and scope of the title), the change folder of the issue (the "why" of the proposal, and the `Change:` line, archived or not) and the labels file, and prints the title, a blank line and the body. `--why` replaces the "why" of the proposal, and `--attribution` adds a paragraph after the `Change:` line.
- `devops pr create` checks `--title` and `--body` with the same functions before it sends any request. It exits 1 with every problem on stderr and opens nothing when one rule fails. It still opens a draft. The scope is checked against the labels file of the base branch and, when the repository is the checkout, the labels file of the checkout, because a pull request that adds a scope adds its label too.
- `SUMMARY_MAX_CHARS` moves from `stage_change.py` to `pull_form.py`, and `stage_change.py` imports it, so one module holds the limit. The body limit is the existing `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`.
- `devops pr create` no longer warns about a scope with no label: it refuses the title before the pull request opens. The post-open label step keeps its error for a label that GitHub refuses.
- `devops pr describe` is exposed as an MCP tool, and its `gh pr describe` alias is on the excluded list of `tests/ai/mcp/test_mcp.py`.
- The change adds a command, an option set and messages that a consumer sees, so it carries spec deltas: a new capability `pull-request-form`, and the modified requirements of `pr-title-labels` whose scenarios open a pull request with a title and no body.
- The change fits one pull request.

The answers to the open questions of the issue are in the design. The jobs of the Service keep their own title and body code in this change (see Workflow follow-up in `tasks.md`).

## Capabilities

### New Capabilities

- `pull-request-form`: the rules of the title and the body of a pull request, `devops pr describe`, and the check of `devops pr create`.

### Modified Capabilities

- `pr-title-labels`: `devops pr create` refuses a title whose scope has no label, before it opens the pull request, and every scenario that opens a pull request gives a body in the form.

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py` (new), `src/devops_cli/roadmap/pull_describe.py` (new), `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Documents: `CONTRIBUTING.md`, `.github/pull_request_template.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/gh.md`, `docs/commands/pr.md` (generated), `openspec/specs/pull-request-form/spec.md` and `openspec/specs/pr-title-labels/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_pull_form.py` (new), `tests/commands/test_pr_describe.py` (new), `tests/commands/test_pr_form_check.py` (new), `tests/commands/test_pr_title_labels.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_status.py`, `tests/commands/test_pr_dry_run.py`, `tests/invariants/test_workflow_contracts.py`, `tests/ai/mcp/test_mcp.py`.

## Feasibility

- The premise "`devops pr create` checks neither the title nor the body" holds. `src/devops_cli/commands/pr.py` at `19a08788` passes both texts to `pr_create_args` and to the REST fallback unchanged, and its only title rule is the post-open label step. A scope with no label gives a warning (`labels_scope_undeclared`) after the pull request is open.
- The premise "the Service cuts text with `...`" holds. `staging_title` and `delivery_title` call `textwrap.shorten(..., placeholder="...")` in `src/devops_cli/roadmap/stage_change.py`, and `_why` in `src/devops_cli/roadmap/implement_run.py` does the same with `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`. `implement_pull_body` then adds `Closes #<n>` and the `Change:` line to a "why" that already has up to 1,000 characters, so a body of the job can have more than 1,000 characters. The rule of this change counts the whole body before its trailers.
- The open question "can the `Semantic PR title` workflow and the template read the same rule list" has the answer no. `action.yml` of `amannn/action-semantic-pull-request` at the pinned commit `48f256284bd46cdaab1048c3721360e808335d50` runs on `node24` and takes `types`, `scopes`, `requireScope`, `disallowScopes`, `subjectPattern` and other static inputs, read with `curl https://raw.githubusercontent.com/amannn/action-semantic-pull-request/48f256284bd46cdaab1048c3721360e808335d50/action.yml`. It has no input that names a file, it never reads the body, and it cannot import a Python module. The template is a Markdown file. So the change adds a test (`test_the_title_check_and_the_workflow_hold_the_same_rule`) that holds the pattern and the scope list of the workflow equal to the module, as the existing test already holds the scope list equal to the labels file.
- The open question "should `check-readiness` call the body check" is out of this change: it works on an existing pull request and is the subject of #2585. The function `body_problems` is ready for it (see Workflow follow-up).
- The rules were run on real pull requests. `gh api "repos/dan-petty/devops-cli/pulls?state=closed&per_page=40"` gave the 30 merged pull requests that release-please did not open. `title_problems` refused none of the 30 titles. `body_problems` accepted 9 of the 30 bodies and refused 21 (a body can break more than one rule): 9 kept the comment of the template, 9 had 1,026 to 3,355 characters before the trailers, 7 had no `Change:` line, 3 had no `Closes` line, #3177 put the attribution lines before `Closes` (the failure named in the issue), and #3133 put `Closes` after `Change:`. So the rules find the failures that occur, and they do not refuse the titles the project writes today.
- `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/commands/test_pr_describe.py tests/commands/test_pr_form_check.py` passes, and the three files fail on `origin/main` because the modules and the command do not exist there.

## Existing Tool Considered

`commitlint` and the `amannn/action-semantic-pull-request` action (already used in `.github/workflows/pr-title.yml`) check a Conventional Commit title. They run in CI after the pull request is open, take static inputs, read no body, and cannot build a body from a change folder or run offline in `devops pr create` and in the jobs. GitHub's pull request template guides a body and checks nothing. No open tool builds a body from an OpenSpec change folder. So the change builds one small module on the title code that the project already has (`commit_title.py`, `title_labels.py`, `pull_labels.py`). Written cost: about 120 000 tokens and 3 hours to build the module, the command, the check and the tests; about 4 000 tokens a month to keep it, as a new rule needs a case; about 20 000 tokens to fix a rule that refuses a good text. The change deletes the warning `labels_scope_undeclared` of `devops pr create` and the definition of `SUMMARY_MAX_CHARS` in `stage_change.py`.
