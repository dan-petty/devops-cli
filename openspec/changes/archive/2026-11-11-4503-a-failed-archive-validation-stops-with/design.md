# Design

## Decisions

- The archive step passes the class, as other stop sites do (#3476). The site reads the checkout after the program failed: the change folder is gone and a dated folder of the item is in the archive. With exit status 1, the archive applied and the validation of the specs refused a spec. The text of the output does not decide the class.
- The class is `plan_defect` with its default action `amend`. The spec deltas of the change are part of the plan, which the stage job merged. A person shortens or fixes the spec text, then comments `implement: retry`. #3429 adds the OpenSpec validation to the implement plan gate, which can refuse such a plan before the groups run.
- Only exit status 1 gets the class. A timeout has no status, and a signal status keeps its class (`oom`, `timeout`).

## Rejected alternatives

- A text rule in `failure.py` for the message "The archive is applied", read before the rules of the checks: the class would follow the words of another process, and the rule order of `failure.py` would change while #4491 changes that file.
- Remove `\d+ failed\b` from the `test` rule: the summary line of pytest ("2 failed, 10 passed") is the sign of a failed test in the log of a check, and the archive site does not need the rule to change.
- The class `lint` with the action `repair`: no fix step runs after a failed project program, so the action would stay with no one to take it.
- The class `premise_false` with the action `return`: the premise of the item holds. Only the spec text of the plan is wrong.
