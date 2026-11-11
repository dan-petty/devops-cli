# Design

## Decisions

- **Normalize the boolean in the shared mode type in `src/devops_cli/config/defaults.py`.**: One `BeforeValidator` covers a typed file, the ConfigMap and the file that `devops config set` writes, and `JevMode` and `DecisionMode` share it.
- **Keep `yaml.safe_load` as the reader of the config files.**: A YAML 1.2 loader would change the value that every other key loads, which is wider than this defect.
- **Leave `round_trip.edit` and its quoting unchanged.**: The reader rule already makes a written mode load, and quoting in the writer changes every string that YAML 1.1 reads as another type.
- **Replace the test that asserts that a bool is refused, and keep its `ValidationError` assertion for an unknown string.**: A bool is now the mode it names, so the old assertion states the behavior that this change removes, and the unknown value still needs a test.

## Rejected alternatives

- **Quote the mode values in `round_trip.edit`.**: Quotes cover only the text that the writer produces; a file that a person types stays bare, and the reproduction steps of the issue show that case.
- **Load the config files with a YAML 1.2 parser.**: The reader is one call in `src/devops_cli/config/settings.py:def _read_config_file`, `lambda: yaml.safe_load(path.read_text(encoding="utf-8")) or {},`, and a new loader changes the value of every other key.
- **Accept a bool in each of the two model fields.**: It duplicates the rule in two places and misses a caller that validates the mode type directly, such as the `TypeAdapter(DecisionMode)` call of the new test.
