# valkey-endpoint Specification

## Purpose
The endpoint that the Valkey clients of devops-cli dial: the one validated URL that names the address and the database, when the connection uses TLS with a certificate check against the host name, and the URL that `devops k8s configure-urls` saves.

## Requirements

### Requirement: The valkeys scheme connects over TLS
When `valkey.url` has the scheme `valkeys`, each Valkey client that reads the `valkey` settings SHALL connect over TLS, send the host of the URL as the server name, and check the certificate against that host with the platform CA store. When `valkey.url` has the scheme `valkey`, the client SHALL connect in plaintext.

#### Scenario: A valkeys URL connects over TLS
- **WHEN** `valkey.url` is `valkeys://example.com:<port>`, and the server shows a certificate for `example.com` from a trusted CA
- **THEN** `devops valkey ping` connects over TLS, the server receives `PING`, and the command exits 0

#### Scenario: A certificate for another name is refused
- **WHEN** `valkey.url` is `valkeys://example.com:<port>`, and the server shows a certificate for `example.org` from a trusted CA
- **THEN** `devops valkey ping` exits 1, its output contains `certificate is not valid for 'example.com'`, and the server receives no command

#### Scenario: A valkey URL connects in plaintext
- **WHEN** `valkey.url` is `valkey://example.com:<port>`, and the server does not use TLS
- **THEN** `devops valkey ping` connects in plaintext, the server receives `PING`, and the command exits 0

#### Scenario: The dashboard panel connects over TLS
- **WHEN** `valkey.url` is `valkeys://example.com:<port>`, and the server shows a certificate for `example.com` from a trusted CA
- **THEN** the Valkey panel of the dashboard shows the server as connected, with the version, the uptime and the key count that the server sends

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

### Requirement: A Valkey URL that is not valid is refused
`valkey.url`, `runs.index_url` and `--url` SHALL refuse a URL with no scheme, a scheme other than `valkey` or `valkeys`, no host, a bad port, port 0, an IPv6 address with no brackets, a user name or a password, a fragment, a query key other than `db`, or a database that is not an integer of 0 or more. The message SHALL start with the name of the setting and SHALL NOT quote the URL. A refused URL SHALL NOT stop the settings from loading.

#### Scenario: Each setting refuses each case
- **WHEN** `valkey.url`, `runs.index_url` and `--url` each hold a refused URL, such as `tcp://:<masked-password>@example.com:6379`
- **THEN** each message starts with the name of its setting, quotes the scheme `'tcp'`, and does not contain the password

#### Scenario: A command ends with the message and no traceback
- **WHEN** `valkey.url` is `tcp://:<masked-password>@example.com`, or `devops valkey ping` gets that URL as `--url`
- **THEN** `devops valkey ping` exits 1, its output names `valkey.url` or `--url` and holds no traceback and no password

#### Scenario: A saved setting names the command that writes it
- **WHEN** `valkey.url` and `runs.index_url` are `tcp://` URLs
- **THEN** `devops valkey ping` names `devops k8s configure-urls`, and `devops ai runs reindex` names `devops ai runs connect`

#### Scenario: The settings still load
- **WHEN** `valkey.url` is `tcp://example.com:6379`
- **THEN** the settings load, and the endpoint of `valkey.url` fails with a configuration error that names `valkey.url`, the exit code 1 and the error code `CONFIGURATION_ERROR`

#### Scenario: A refused run index keeps the run local
- **WHEN** `runs.index_url` is `tcp://example.com:6379` and a benchmark records a run
- **THEN** the run is kept in the data directory and not shared, its detail starts with `runs.index_url has the scheme 'tcp'`, and no connection opens

### Requirement: configure-urls saves valkey.url as a valkey URL
`devops k8s configure-urls` SHALL save the detected cache Valkey as `valkey://<host>:<port>`, with an IPv6 host in brackets. It SHALL keep a saved non-loopback URL when detection finds a loopback URL, and keep a saved loopback URL on a port other than 6379. It SHALL replace a saved URL that is not a valid Valkey URL. The NodePort preview and the port-forward preview SHALL show `valkey://`.

#### Scenario: A detected address is saved as a valkey URL
- **WHEN** detection finds the cache Valkey at `http://192.0.2.7:30637` or `http://[2001:db8::5]:30637`
- **THEN** `valkey.url` is `valkey://192.0.2.7:30637` or `valkey://[2001:db8::5]:30637`

#### Scenario: A saved non-loopback URL survives a loopback detection
- **WHEN** `valkey.url` is `valkey://[2001:db8::5]:6379`, `valkey://[::ffff:192.0.2.5]:6379` or `valkey://example.com:6379`, and detection finds only a loopback URL
- **THEN** `valkey.url` keeps its value

#### Scenario: A saved loopback URL
- **WHEN** `valkey.url` is `valkey://localhost:6379` or `valkey://localhost:6380`, and detection finds `valkey://localhost:30637`
- **THEN** `valkey.url` becomes `valkey://localhost:30637` for the first, and keeps `valkey://localhost:6380` for the second

#### Scenario: A saved URL that is not valid is replaced
- **WHEN** `valkey.url` is `tcp://localhost:6379` or `http://192.0.2.7:30637`, and detection finds `valkey://localhost:30637`
- **THEN** `valkey.url` becomes `valkey://localhost:30637`

#### Scenario: The previews show a valkey URL
- **WHEN** a person previews the NodePort addresses or the port-forward addresses of the `llm` stack
- **THEN** `valkey.url` starts with `valkey://`
