# Design

## Decisions

- **`select_items` switches the cap, with the keyword `first_pass_limit: int | None = None`.**: Only `select_items` knows the list `unchecked`, which it builds after the filters for eligibility and for the retry delay (`alternatives.py:515-524`). `plan_alternatives` would need a second pass over `store.items()` to learn the same fact. `None` is the case of `--limit`: an explicit limit replaces both settings, as `--limit` does today (`spec.md:161`).
- **A round with an unchecked item caps the whole list, unchecked items first and then the due ones, at `first_pass_limit`.**: The issue says the row checks `first_pass_limit` items "while items have no check" and returns to `limit` "when every open item has a check". A probe with 3 unchecked and 10 due items selected 13, which is under 20, so no round costs more than a full first-pass round, the cost the owner accepts.
- **The count of "no check" is the list `unchecked` of `select_items`.**: An item whose check failed less than `retry_days` ago is in neither list (`alternatives.py:516-517`). A probe with 2 such items and 8 due items selected 5, so an item that fails each round cannot keep the first-pass cap on.
- **The row passes no limit.**: `plan_alternatives` reads `config.limit` when it gets none (`alternatives.py:852`), and the row passed that same value explicitly (`run.py:613`). With one path, the row and `devops roadmap alternatives` follow one rule, the one that the requirement "The limit of a round is a setting" gives them.
- **The default constant is `DEFAULT_ROADMAP_ALTERNATIVES_FIRST_PASS_LIMIT = 20`, class `setting` in the table of limits.**: `tests/roadmap/test_roadmap_limit_classes.py` fails for a `DEFAULT_ROADMAP_*` number with no entry (scratch run: `test_every_numeric_limit_of_the_roadmap_jobs_has_a_class` failed), and a person tunes this number.
- **Both limits go in the example ConfigMap.**: The issue asks for the setting in `configmap.example.yaml`. The block `roadmap` of the file holds `stage` only (`configmap.example.yaml:59-64`), and `tests/config/test_k8s_devops_runtime.py:157` validates the whole file as `Settings`, so a wrong key fails a test.

## Rejected alternatives

- **Raise the default of `roadmap.alternatives.limit` to 20, with no second setting.**: A text edit makes an item due at once (`_is_due` compares the body hash, `alternatives.py:491-494`), so a mass edit would send 20 rechecks in a round for good. The acceptance criteria of the issue say the cap returns to 5 once every item has a check.
- **Check only the unchecked items in a first-pass round, and fill the rest up to `limit` with due items.**: It needs two caps in one list and a third rule for the mix. The scratch probe shows the one-cap rule already keeps a round under 20. The scenarios of the delta stay one number each.
- **Count the unchecked items in `plan_alternatives` and pass the larger `limit` to `select_items`.**: It reads `store.items()` twice and splits one rule across two functions. `select_items` already holds both lists.
- **Apply the first-pass limit to the row only, and keep `config.limit` for the command.**: `spec.md:161` says one setting caps "the row and `devops roadmap alternatives`". A person who runs the command by hand to catch up would get 5 items, and the row 20, for the same state.
- **A ramp that lowers the cap as items get a check.**: The issue does not ask for it, and a test needs a curve. The two-state switch has 4 test cases.
