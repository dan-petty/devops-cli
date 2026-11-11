# Design

## Decisions
- `RepoRef` is a frozen dataclass with one field, `display`. `__post_init__` checks the form, and `__eq__` and `__hash__` use `key`. Thus `RepoRef("Owner/Repo") == RepoRef("owner/repo")`, and a set of `RepoRef` values holds one entry for each repository.
- `service.repos` stays `list[str]` in the GitHub spelling. A new validator parses each entry with `RepoRef` and refuses a second entry with the same `key`. Each consumer parses with `RepoRef` in the item that changes it, so this change does not touch the 7 reads of the setting in 6 modules (`git grep -n '\.service\.repos' -- 'src/*.py'`).
- `ServiceRow` is a `StrEnum` of the 7 rows. A unit name and a lock name take a `ServiceRow`, so the length budget of the name is known. An ad hoc name takes a word that must be a DNS label of 16 characters or fewer, because `devops k8s run-job` names its Jobs with words that are not rows.
- The unit name hashes `key`, the item and the input key with a NUL between them. `key` and the item hold no NUL, so the split of the hash input is unique.
- A Valkey kind and id must not be empty and must hold no `/` and no glob character. Then the repository part holds the only `/` of a key, and the two patterns of a repository find only its keys. The test proves this on the in-memory Valkey server, not with `fnmatch`, because Valkey has its own glob.
- The ADR takes number 0022. The record of the move (#4527) takes 0021, the next free number, in a pull request that is open at the same time. The pull request that merges second adds the link between the two records.

## Rejected alternatives
- A `list[RepoRef]` type for `service.repos`: rejected for this change. 7 reads in 6 modules use the strings, and the issue moves each consumer in its own item.
- `fnmatch` as the oracle of the pattern test: rejected. Its `[` and `\` rules are not those of Valkey, and the in-memory server of the tests implements the Valkey glob.
- A label value check from the Kubernetes client: `kubernetes==36.0.3` has no public function for it (the issue's search), so the regex comes from the Kubernetes documentation.
- Keep the entry check of the inbox command: rejected. The settings refuse a bad entry at load, so the check cannot run.
