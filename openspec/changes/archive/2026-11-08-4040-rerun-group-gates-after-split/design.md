# Design

## Decisions

- **Call `check_proposal` on the split proposal.**: It is the one call that the first pass uses, so one rule set judges both replies, and a new gate in `check_gates` reaches the split with no second edit.
- **Pass the arguments of the first pass.**: The tree is `self._tree.with_files(files)` of the files that `_fit` built for the split, the search evidence is recorded for the new groups, and the other arguments are the values the first pass used.
- **Keep the gates that read no group.**: `citation`, `dependencies` and `constants` give the same answer on the same input, and they cost only local reads and no request.
- **Test one gate for each case.**: A case whose `check_gates` result has problems under one gate name only proves that gate, and a failure names the gate that stopped working.

## Rejected alternatives

- **Add the four missing gates to the hand-made list.**: The list would drift again with the next gate. `check_proposal` is the single entry point, and `ProposalGate` says in its docstring that a new gate adds a line to `check_gates` only.
- **Run `check_proposal` only when the first pass had a problem.**: The first pass has no problem in the case of the issue, and the split brings the fault.
- **Judge the split in `_fit`.**: `_fit` measures and splits. `_settle` is where the first reply is judged, and a second place would repeat the arguments.
