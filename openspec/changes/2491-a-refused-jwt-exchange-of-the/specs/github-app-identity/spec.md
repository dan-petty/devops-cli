## MODIFIED Requirements

### Requirement: A failed exchange names the App and the reason
A refused exchange, or a key that cannot sign a JWT, SHALL raise `GitHubUnauthenticatedError` that names the App's bot login and the reason. For a refused exchange with HTTP 401, the reason SHALL include GitHub's message from the response body and SHALL NOT include `gh auth login` or `GH_TOKEN`. The error SHALL never hold the key.

#### Scenario: GitHub refuses the exchange
- **WHEN** GitHub answers the exchange with HTTP 401 and body `{"message": "A JSON web token could not be decoded"}`
- **THEN** the token lookup raises `GitHubUnauthenticatedError` whose message holds `devops-roadmap[bot]`, `POST /app/installations/42/access_tokens`, `401`, `A JSON web token could not be decoded`, and `Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and does not hold `gh auth login` or `GH_TOKEN`

#### Scenario: The key is no RSA key
- **WHEN** the environment holds `not-a-pem-key` as the key
- **THEN** the token lookup raises `GitHubUnauthenticatedError` that says the key is not an RSA private key in PEM form, does not quote the key, and sends no request
