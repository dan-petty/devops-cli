# Design

## Decision

`mint_grafana_token` runs these steps in one HTTP client:

1. Find or create the service account.
2. List the IDs of its tokens. A refused list or an answer that is not a JSON array raises `StackCredentialError`, and nothing has changed.
3. Create the new token. A refused create raises, and nothing has changed.
4. Store the token in the keyring when `save_to_keyring` is true. A failed store raises, and the old tokens stay.
5. Revoke the IDs of step 2. A refused revoke logs a warning with its cause and the mint returns the new token.

## Rejected alternatives

- **Fail the mint on a refused revoke.** The new token is valid and stored. A failed result would make the sync report `failed` for a token that works, and `get_or_mint_grafana_auth` would lose that token and use the admin password. Rejected.
- **List the tokens after the create.** The list would hold the new token, so the revoke must filter it out. A list before the create needs no filter. Rejected.
