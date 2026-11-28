# Proposal: #7515

## Why

The brain digest of #4682 is not fail-soft for a store value of a wrong form (#7515). A word of more than 4,300 digits in the `near` field of an entry makes `int` raise `ValueError` in `_held_item`, and a hash field name that is not UTF-8 makes `ValkeyClient.hscan` raise `UnicodeDecodeError`. The error goes out of `read_digest` and fails the whole alternatives round: no item gets a verdict or a failure mark, and `sync_alternatives_round` does not run. The bad field stays until the TTL of 45 days, so each round fails until then. The review of #7496 also found that the cap of 2,000 tokens counts the digest as a JSON document of its own, not as the request holds it, and that an item in its own near list or a repeated near number repeats an entry.

## What Changes

- A number in a field of the brain index is an issue number only when it is ASCII digits, at most 10 of them. A near number of another form is left out, and a watermark number of another form gives the empty watermark.
- `ValkeyClient.hscan` reads a field name that is not UTF-8 with the replacement character, as a reader decodes a value. A hash that another writer changed then raises no decode error in the brain index or in the shared listing snapshot, its other caller.
- The cut of the digest counts the digest as the request holds it: the value of `brain`, one level down in the JSON of the request. `alternatives_request` and the cut take the key and the indent from the same two constants of `brain_digest`.
- The near items of the digest leave out the item itself and a repeated number, before the cap of 5.
- The tests of the cut and of the empty area read state the rule that they name.
- The change fits one pull request.
- The change carries no spec delta and sets `skip_specs: true`. Each change makes the code meet a requirement of `project-brain/digest` that it broke: "No brain gives an empty digest" and "A near item ... of a wrong form SHALL give no digest entry", "The digest stays at or below 2,000 tokens", and "at most 5 near items". No requirement changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The requirements of `project-brain/digest` stay as they are, and the code now meets them.

## Impact

- Code: `src/devops_cli/roadmap/brain_index.py`, `src/devops_cli/roadmap/brain_digest.py`, `src/devops_cli/roadmap/alternatives.py` and `src/devops_cli/valkey/client.py`.
- Tests: `tests/roadmap/test_brain_digest.py`, `tests/roadmap/test_brain_index.py` and `tests/valkey/test_valkey_cache_tier.py`.
- Documents: the bullets "The near items" and "The bound" of `docs/roadmap/alternatives.md`.
- A digest at the bound can hold one entry less than before, because the request holds about 10 more tokens of indent than the old count saw.
- No setting, no store, no ACL rule and no egress rule changes.

## Feasibility

- The two errors happen on main at 0a47a6d6a. `uv run devops ci fail-to-pass` replays the new tests on the tree of the merged #7496 (04e34ce0e, the same tree as main): the round over a near word of 5,000 digits raised `ValueError: Exceeds the limit (4300 digits) for integer string conversion`, and the round over a field name that is not UTF-8, on the entry of the item and on a near entry, raised `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`.
- `ValkeyCacheTier._send` (`src/devops_cli/valkey/cache.py`) catches only `ValkeyError` and the open breaker, and `ValkeyClient.hscan` decoded the names after `_call`, so no layer caught the decode error.
- The count of the bound: one near item whose tool name holds 1,940 words gave 2,000 tokens as a JSON document of its own and 2,002 tokens as the value of `brain` in the request (`count_tokens` of the slice of the request text).
- The near field `1 1 2 2` of item 1 gave a digest with item 1 two times and item 2 two times on main.

## Existing Tool Considered

- Python's own parse and codec rules cover the need: `str.isascii`, `str.isdecimal` and a bound on the length before `int`, and `bytes.decode("utf-8", "replace")`, which the brain index already uses for values. `json.dumps` renders the digest at the level of the request. The change adds no dependency.
- The project code is a helper of 6 lines, one changed decode, the shared render of the digest and the tests: about 30,000 tokens and 1 hour to build.
- The change deletes the second parse of the watermark number, which the helper replaces.
