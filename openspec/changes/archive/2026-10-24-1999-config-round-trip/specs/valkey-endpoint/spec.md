# Spec Delta

## MODIFIED Requirements

### Requirement: valkey.url names the address and the database
The host, the port and the database of `valkey.url` SHALL be the endpoint that a Valkey client dials. The database SHALL come from the path or the query key `db`, and SHALL be 0 when neither names one. An unset or empty `valkey.url` SHALL be `valkey://localhost:6379/0`. No other setting, variable or option SHALL name a Valkey address. `DEVOPS_CLI_VALKEY_URL` SHALL replace `valkey.url`, and `--url` SHALL replace both.

#### Scenario: The path of the URL names the database
- **WHEN** `valkey.url` is `valkey://example.com:<port>/2`
- **THEN** `devops valkey ping` sends `SELECT 2` and then `PING`, and the command exits 0

#### Scenario: The query of the URL names the database
- **WHEN** `valkey.url` is `valkey://example.com:6379?db=4`
- **THEN** the endpoint is the host `example.com`, the port 6379 and the database 4

#### Scenario: An IPv6 address or a name that is not ASCII
- **WHEN** `valkey.url` is `valkey://[2001:db8::1]:6379/0` or `valkey://bücher.example:6379`
- **THEN** the host of the endpoint is `2001:db8::1` or `bücher.example`, as the resolver receives it

#### Scenario: An environment URL replaces the URL of the file
- **WHEN** `valkey.url` is `valkey://example.com:6379/1` and `DEVOPS_CLI_VALKEY_URL` is `valkeys://example.org:6381/2`
- **THEN** the endpoint is `valkeys`, the host `example.org`, the port 6381 and the database 2

#### Scenario: The url option replaces the saved URL
- **WHEN** `valkey.url` is `tcp://example.com:6379`, and `devops valkey ping` gets `--url valkey://127.0.0.1:<port>/3`
- **THEN** the server receives `SELECT 3` and then `PING`, and the command exits 0

#### Scenario: A file with the removed host, port and db keys
- **WHEN** the configuration file holds `valkey.host`, `valkey.port`, `valkey.db` and `valkey.url: valkey://example.com:6380/1`
- **THEN** the endpoint is the host `example.com`, the port 6380 and the database 1, and a save that changes another key keeps the four `valkey` keys as the file holds them

#### Scenario: No other setting names the address
- **WHEN** the configuration options, the environment variables and the options of the nine `devops valkey` commands are listed
- **THEN** only `valkey.url`, `DEVOPS_CLI_VALKEY_URL` and `--url` name a Valkey address, and `devops config get valkey.host` exits 1
