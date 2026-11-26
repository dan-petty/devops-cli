## ADDED Requirements

### Requirement: The guard reads the host of a word in each form of the word
The guard SHALL read the host of a word in each of these forms, and SHALL give the result of the bare host for each: a host with a port or a path, a URL with a scheme, a scheme-relative URL, a URL inside a longer word, and a URL in the path or the query of another URL, percent-encoded one time or not. Upper-case letters and a dot at the end of a host SHALL NOT change the result.

#### Scenario: A URL word is read by its host
- **WHEN** the query holds `https://storage.internal/api`, `http://192.168.49.2:8080/api`, `//storage.internal/api`, `[text](https://storage.internal/api)`, `url=https://storage.internal/api`, `https://example.com/?u=http%3A%2F%2Fstorage.internal%2Fapi` or `HTTPS://STORAGE.INTERNAL./api`
- **THEN** `SearchQueryRefused` is raised with the message of the bare host, and no request is sent

#### Scenario: A URL word of a public host
- **WHEN** the query holds `https://docs.python.org/3/library/ipaddress.html` or `https://example.com/docs/settings.local`
- **THEN** the query reaches the provider

### Requirement: A text that the URL parser refuses raises no error out of the guard
The guard SHALL raise no error other than `SearchQueryRefused` for a text that the URL parser refuses. The guard SHALL read each part of such a text between a slash and a bracket as a host, in the NFKC form of the text.

#### Scenario: A refused text with no host of a refused kind
- **WHEN** the query holds `https://[name]:6443/healthz`
- **THEN** no error is raised and the query reaches the provider

#### Scenario: A refused text that names a host
- **WHEN** the query holds `https://[storage.internal]:6443/healthz`
- **THEN** `SearchQueryRefused` is raised with the message of an internal host name, and no request is sent
