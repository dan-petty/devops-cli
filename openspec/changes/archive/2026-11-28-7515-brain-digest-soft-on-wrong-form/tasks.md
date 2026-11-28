# Tasks

## 1. Read a store value of a wrong form softly

Kind: behavior. Reads: `src/devops_cli/valkey/cache.py`, `src/devops_cli/roadmap/stores/listing_shared.py`. Changes: `src/devops_cli/roadmap/brain_index.py`, `src/devops_cli/valkey/client.py`, `tests/roadmap/test_brain_digest.py`, `tests/roadmap/test_brain_index.py`, `tests/valkey/test_valkey_cache_tier.py`.

- [x] 1.1 Add the cases of a near word of 5,000 digits, a field name that is not UTF-8 on the entry of the item and on a near entry to `tests/roadmap/test_brain_digest.py`, the cases of a watermark number of 5,000 digits and of the read of an entry to `tests/roadmap/test_brain_index.py`, and the case of a field name that is not UTF-8 to `tests/valkey/test_valkey_cache_tier.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_brain_index.py tests/valkey/test_valkey_cache_tier.py` fails on the base
- [x] 1.2 Add `_number` to `src/devops_cli/roadmap/brain_index.py` for the near field and the watermark, and decode the field names of `ValkeyClient.hscan` with `errors="replace"`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_brain_index.py tests/valkey/test_valkey_cache_tier.py tests/roadmap/stores` passes

## 2. Count the digest as the request holds it, with no repeated near item

Kind: behavior. Reads: `src/devops_cli/roadmap/adr.py`. Changes: `src/devops_cli/roadmap/brain_digest.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_brain_digest.py`.

- [x] 2.1 Add the cases of the boundary of 2,000 tokens in the request text and of the near field `1 1 2 2` to `tests/roadmap/test_brain_digest.py`, and make the cases of the cut and of the empty area read state their rules
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py` fails on the base
- [x] 2.2 Render the digest under `DIGEST_KEY` with `REQUEST_INDENT` for the cut and for `alternatives_request`, and leave the item itself and repeated numbers out of the near items in `src/devops_cli/roadmap/brain_digest.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_brain_digest.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_brain_sync.py` passes

## 3. Document the near items and the bound

Kind: other. Changes: `docs/roadmap/alternatives.md`.

- [x] 3.1 Say in the bullets "The near items" and "The bound" of `docs/roadmap/alternatives.md` that the item itself, a repeated number and a number of a wrong form are left out, and that the bound counts the digest as the request holds it
  - Verification: `$ uv run devops ci --check --only docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
