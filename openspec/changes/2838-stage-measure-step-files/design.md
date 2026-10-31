# Design

## Decisions

- **Measure what the step reads.** The step packs each named file to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens and opens the rest with its tools. The stage measure must count the same text. One function, `packed_file(path)`, makes that text for both jobs, so the two cannot drift apart again.
- **A new small module.** `roadmap/step_files.py` holds `packed_file`. `stage_change.py` must not import `implement_step.py`: that module loads pydantic-ai and the harness, and the stage job needs none of it.
- **The cap is a constant, not an argument.** `measure_groups` and `_packed_tokens` lose `limit`. The one value is `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`, read inside `packed_file`.
- **The number of split asks stays one.** After the fix no group of the four items needs a split, and a group over the budget is a group that names many files. One ask already lists the measured tokens of each group.

## Rejected alternatives

- **A second and third split ask (the title of #2838).** Evidence: after the first split, every new group that named `constants.py` measured 41598 to 42242, because that one file counts 38159 tokens. A split moves files between groups and cannot shrink a file. A new ask costs one model call for each stopped item and fixes none of the four. The cause is the measure.
- **Count the shared part once.** The shared part is 3000 to 3900 tokens, 8% to 10% of the budget. Counting it once would lower every group by that amount, and the groups would still be 38000 to 45000. The step does pay it in each step, so the count is honest.
- **Shrink the refine block of the item body.** The whole item text is 1161 to 1952 tokens. The block is a part of that. It cannot bring a group of 41000 tokens under 40000, and the step reads the body.
- **Raise the budget of 40000.** It is an owner decision, and the numbers do not call for it.
- **Keep the stage packer and lower its limit.** It would be a second packing rule next to the one of the step. Two rules drift apart, which is how this defect began.
