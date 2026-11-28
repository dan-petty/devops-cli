# Design

## Decisions

- **Fix the two parse points, not the caller.** The cause is in `_held_item` and `_watermark_of` (`src/devops_cli/roadmap/brain_index.py`) and in `ValkeyClient.hscan` (`src/devops_cli/valkey/client.py`). A catch around `read_digest` would also hide an error of the code, and the listing snapshot, the other caller of `hscan`, would keep the decode error.
- **An issue number is at most 10 ASCII digits.** `_number` takes a word only when `isascii`, `isdecimal` and a length of at most 10 hold, so `int` never gets a text over its limit of 4,300 digits. `isdecimal` alone takes other scripts, such as Arabic-Indic digits, which no writer of the index gives. The near field and the watermark use the same helper, so one rule reads each number of the index.
- **A field name decodes as a value decodes.** `hscan` gives `str` names and `bytes` values. `BrainIndex._fields` already decodes the values with `errors="replace"`, so the names get the same rule. The listing snapshot compares each record with its field name and with the digest of its records, so a name with a replacement character gives a miss there, as a changed snapshot does.
- **The cut renders the digest as the request holds it.** `json.dumps` writes a value by its level only, so the cut renders `{DIGEST_KEY: values}` with `REQUEST_INDENT` and takes the text of the value. `alternatives_request` writes the document with the same `REQUEST_INDENT` and the same `DIGEST_KEY`, so a change of either one changes both.
- **The near items leave out the item and repeated numbers before the cap.** `dict.fromkeys` keeps the first place of each number, so the order of the field, the newest check first, stays.

## Rejected alternatives

- **A `try` around `read_digest` in `_verdict_check`.** Rejected: the round would go on, but the listing snapshot also calls `hscan` (`src/devops_cli/roadmap/stores/listing_shared.py:379`) and would keep the error, and the catch would hide a defect of the digest code.
- **Catch `ValueError` around `int` in `_held_item`.** Rejected: a bound on the length stops the word before `int`, so no error is raised. A test that sees a raise and a catch would also accept a slow parse of a long word.
- **Count the digest with the whole request.** Rejected: the cut of the digest then depends on the body, the replies and the ADRs of the item, which have caps of their own. The value of `brain` at its level is the text that the bound names, and a test counts the slice of the real request text at the boundary of 2,000 tokens.
- **Decode the names in strict mode and skip a step that fails.** Rejected: the step holds the other fields of the hash too, so a skip would lose them, and the values already use `errors="replace"`.
