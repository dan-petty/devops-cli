## ADDED Requirements

### Requirement: A private host name is masked
`mask_private_hosts` SHALL replace each match of `PRIVATE_HOST_PATTERNS` in a text with `<masked-host>`: a name that ends in `.internal`, `.local`, `.lan`, `.corp` or `.home.arpa`, a private or loopback address, and `localhost`. It SHALL leave the rest of the text as it is.

#### Scenario: A host name and an address
- **WHEN** a text holds `https://db.corp.internal/x`, `127.0.0.1` and `localhost`
- **THEN** the result holds `https://<masked-host>/x`, `<masked-host>` and `<masked-host>`, and no other change

#### Scenario: A public host and a code name
- **WHEN** a text holds `example.com`, `198.51.100.7` and `config.local_value`
- **THEN** the result is the text as it was
