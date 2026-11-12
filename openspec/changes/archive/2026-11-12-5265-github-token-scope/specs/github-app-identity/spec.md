## MODIFIED Requirements

### Requirement: The App mints an installation token and renews it before it expires
A process that acts as the App SHALL sign a JWT whose issuer is the App ID with the private key, and SHALL exchange it at `POST /app/installations/<installation_id>/access_tokens` for an installation token. It SHALL keep the token until less than `DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS` are left before GitHub's `expires_at`, and SHALL then mint a new one on the next call. Each gh child, and each git child that reaches a remote, SHALL get the current token.

#### Scenario: A token near its expiry is renewed for the next gh child
- **WHEN** the first exchange gives `ghs_first`, which expires in 5 minutes, the second gives `ghs_second`, which expires in one hour, and three gh children start one after another
- **THEN** the children get `ghs_first`, `ghs_second` and `ghs_second`, GitHub receives two exchanges, and the first exchange carries a bearer JWT whose `iss` is `1001`
