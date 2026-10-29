## ADDED Requirements

### Requirement: A derived entry is built from other values of the same push
A cluster Secret table entry MAY have a derived source: a template whose fields are keyring, setting or literal sources. The push SHALL resolve every entry that is not derived first. It SHALL then fill each field with the value of its source, quoted with `urllib.parse.quote(value, safe="")`, and SHALL compare the result with the live value as for any other entry. The push SHALL NOT adopt, generate or store a derived value in the keyring.

#### Scenario: A connection string from a literal user and a generated password
- **WHEN** a row has a `password` entry from an empty keyring key with a generator, and after it in the table a derived `DSN` entry `postgres://{user}:{password}@db.example.com:5432/app` with the literal user `app/user` and the same keyring key as `password`, and no live Secret exists
- **THEN** the push writes `password` with the generated value, stores that value in the keyring, and writes `DSN` so that `urllib.parse.urlsplit` gives back the user `app/user`, the generated password, the host `db.example.com` and the path `/app`, and the keyring holds no value for `DSN`

#### Scenario: A derived entry before its input in the table
- **WHEN** the derived `DSN` entry comes before the `password` entry that adopts the live password, and the live `DSN` was built from that password
- **THEN** the plan shows `DSN` as `unchanged`

#### Scenario: A missing input
- **WHEN** an optional derived entry reads a managed keyring option that has no value
- **THEN** the push leaves the entry out, and its warning names the input and `devops config set <option>`

#### Scenario: The plan and the dry run show a derived entry with no value
- **WHEN** `--plan` or `--dry-run` runs for a row with a derived entry
- **THEN** the output names the entry's source as `derived from` and its input sources, the dry run shows a placeholder in the Secret's data and lists no keyring write for the entry, and no output holds a value

#### Scenario: A differing derived value needs rotate
- **WHEN** the live value of a derived entry differs from the value the push builds, and `--rotate` is not given
- **THEN** the push writes nothing and names the entry as differing

### Requirement: A row names its Secret type
A cluster Secret table row MAY name its Secret type, and the default SHALL be `Opaque`. The manifest that the push applies and the manifest that the dry run shows SHALL carry the type of the row.

#### Scenario: A basic-auth row
- **WHEN** the push writes a row of type `kubernetes.io/basic-auth` and a row with no type
- **THEN** the applied manifest of the first has `type: kubernetes.io/basic-auth` and the second has `type: Opaque`, and the dry run's manifest shows the same types
