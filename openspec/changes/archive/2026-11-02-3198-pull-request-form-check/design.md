# Design

## One module of rules, with no reads

`pull_form.py` holds every rule of the title and the body. `title_problems(title, declared)` and `body_problems(body)` return one text for each problem, and an empty list when the form is right. `build_title` and `build_body` join their parts and run the same two functions, so a text that `describe` builds always passes the check of `create`. The module reads no file and makes no request: the caller passes the label names. `pull_describe.py` does the reads (the issue, the change folder, the labels files) and the command in `pr.py` prints.

Rejected: put the rules in `commands/pr.py` (the jobs of the Service could not import them without the command layer, and #3200 will need them in `check_proposal`); a Pydantic model for the title (the problems must name each rule in words for a model and a person, and a `ValidationError` of Pydantic names fields).

## Nothing is cut

`textwrap.shorten(..., placeholder="...")` leaves a text that ends with `...`, and a reader cannot tell that the text is cut. The builders raise `ValidationError` with every problem and the limit, and the caller writes a shorter text. A summary that ends with `...` or `…` is a problem of its own, because that is what a cut text looks like. Rejected: to cut at a word and add no mark (the cut text would still read as broken, and the meaning is lost without notice).

## What a body is

The form is: the text (what the change does, and why), a blank line, `Closes #<issue>`, a blank line, ``Change: `<folder>/` ``, and then, when given, the attribution lines. This is the order of CONTRIBUTING.md section 4 and of the pull request template, and #3195 has it. The text, the `Closes` line and the `Change:` line have at most `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` (1,000) characters, which is the limit the implement job already holds; the attribution lines after the `Change:` line have their own limit of 400 characters, so they are no way around the first limit. The `Closes` line is the only closing reference of the body: GitHub closes every issue that a body names with a closing keyword, and AGENTS.md says one pull request closes one issue. The `Change:` line names the folder of the same issue. The `Change:` line accepts the active folder (`openspec/changes/<issue>-<slug>/`) and the archive folder, because `devops pr create` runs before the last commit archives the change.

A text is a placeholder when it is one of a closed list (`x`, `placeholder`, `tbd`, `todo`, ...) without case and punctuation, and a text under 20 characters is too short to say what the change does and why. A body that keeps `<!--`, `<issue>`, `<date>`, `<slug>` or `<summary>` keeps text of the template, and the real pull requests show it: 9 of 30 merged bodies kept the template comment. `BREAKING CHANGE` is refused because no change is breaking before 1.0.0.

## The title

The title has the form `<type>(<scope>): <summary>`. The type is one of `CONST_BRANCH_TYPES`. The scope is optional, as for the `Semantic PR title` check, and when it is there it is a scope that the labels declare, or `main`. A title has no `!`. The summary has 1 to `SUMMARY_MAX_CHARS` (60) characters, ends with no `...`, and is no placeholder. `SUMMARY_MAX_CHARS` moves from `stage_change.py` to `pull_form.py` and `stage_change.py` imports it, so one module holds the limit.

`create` reads the labels file of the base branch with the same function that adds the labels afterwards (`pull_labels.declared_labels`). CONTRIBUTING.md tells a pull request that uses a new scope to declare the label in the same pull request, so the label is in the checkout and not yet on the base branch. When `--repo` is not given, `create` and `describe` also read `.github/labels.yml` of the checkout and take the union of the two. A labels file that cannot be read on the base branch stops `create` before it opens the pull request, with the error that names the file. Rejected: to skip the scope check when the file cannot be read (a read that fails would turn the check off without notice); to check the scope against the checkout alone (the base branch is what the `Semantic PR title` check and the label step use).

## `devops pr describe`

`describe <issue> --summary <text>` prints the title, a blank line and the body, so a person or a script takes the first line as the title and the rest after the blank line as the body. The type and the scope come from the title of the issue (`commit_type` and `commit_scope`), through `store.item`. The "why" is the section `Why` of `proposal.md` on one line (`safe_text`, as the implement job does, so a handle or a link is in a code span and pings no one); `--why` replaces it, which is the way to shorten a "why" that is over the limit. A "why" that holds a closing keyword for an issue is refused, as the job refuses it. For a change that is not archived, the `Change:` line names the archive folder with the date of today, because the archive is the last commit and `check-readiness` needs that path; the command says so on stderr. `--attribution` can repeat, and each value is a paragraph after the `Change:` line.

The command is of the class `request-plan`: a dry run lists the read of the issue and the read of the labels file, and reads nothing. It is exposed as an MCP tool, because it only reads. Its alias `gh pr describe` is on the excluded list of the MCP test, as the other aliases are.

## The check in `devops pr create`

`create` checks after it finds `gh` and before it sends the create request, and prints every problem to stderr, so a person fixes all of them in one round. A dry run checks the offline rules (the form of the title, its summary, the body) and skips the read of the labels file, because a dry run makes no request. The pull request still opens as a draft, and `--draft` is still not an option. The REST fallback is reached only after the check passed.

The warning `labels_scope_undeclared` of the label step is deleted: the check refuses that title earlier, with the same words. The label step keeps its error for a label that GitHub refuses.

## The jobs of the Service

The stage and the implement jobs still cut with `textwrap.shorten`. To change them to the refusal and one retry, as the issue asks, the jobs must send a refusal back to the model and re-run the step, and the body of the implement job must change its order (`Closes` first today) to the order of this module. That is a change of the job code and of the model loop, with its own tests and replays, and it touches `stage_change.py`, `implement_run.py` and `messages.py`, which other open changes edit. It is the follow-up in `tasks.md`. This change makes the module ready for it: `build_title` and `build_body` are the functions the jobs will call. The diff in `stage_change.py` is one import.

## `check-readiness`

`check-readiness` works on an existing pull request and fetches its body already. Calling `body_problems` there is one line, but the issue #2585 owns the warning at 1,000 characters and its wording. It is a follow-up that uses `body_problems`; this change adds no call.
