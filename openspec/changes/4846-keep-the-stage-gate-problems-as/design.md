# Design

## Decisions

- **The code is the key of the message.** Every gate writes its problem from a template of `MESSAGES.roadmap`, so the key (such as `stage_problem_missing_test_file`) is a stable name that `git grep` finds. `string.Formatter.parse` turns each template into a pattern: the literal text must match, and each field matches any text. When two templates match a text, the one with more literal text wins. A template with less than 12 characters of literal text (such as `{reference}`) matches almost any text, so it gives no code. A text that no template matches gets `uncoded`, so a gap shows in the log line and does not stop a plan.
- **The code is found from the text, not set at each gate.** The 61 gate messages are formatted in 9 modules, and 4 open pull requests change those modules. A lookup in one place keeps the change small. A parametrized test fills each `stage_problem_` message and fails when it does not give its own key, so a new message with no code, or with the code of another message, fails the suite.
- **The planner keeps the findings under the problem text.** `_refusal` joins the texts and keeps the findings in a dict by that text. The list of refused replies keeps its `(reply, problem)` form, so the callers that add to it need no change.
- **Stuck is the same gate and the same text with the digits masked.** A finding that moves from group 1 to group 2 is the same finding. Two findings that differ only in a number count as one, which is rare and errs to stuck.
- **The class rule.** `mechanical` for the codes whose message names the one edit and the text to add (`dependencies`, `missing_module_test`, `missing_perimeter_test`). Fewer than 5 samples: `model_fixable`, because the job returns such a reply today. Else `never` when no return fixed one, `model_fixable` when the Wilson lower bound (95 %) is at least 0.5, and `low_share` below.
- **The histogram has the labels `repo` and `reply`.** `reply` is at most 3, the hard ceiling of the gate returns, so one repository adds at most 4 series. Codes stay out of the labels: the log line holds them.
- **The fixture holds the saved problems split into their messages.** The refused files held one joined string per reply. A scratch script cut each string at sentence ends into pieces that each match a gate message, and gave each piece the gate of its code. The fixture holds the texts, so the test runs the product code on them.

## Rejected alternatives

- **Return a coded problem from each gate function.** It changes about 60 call sites in 9 modules, and four open pull requests change `stage_change.py`, `stage_commands.py` and `stage.py`. It also makes the gate functions return a new type to every test that compares their lists of strings.
- **Hand rules per message, as the stage drought study used.** The study needed 40 regular expressions, and each new message needs one more. The templates already hold that text.
- **Add the field to `_Refused`.** An open pull request adds a method on the same lines of `_Refused`.
- **Change the existing `roadmap-stage` capability.** Four open pull requests change that spec file, and one splits it. A new capability does not conflict.
