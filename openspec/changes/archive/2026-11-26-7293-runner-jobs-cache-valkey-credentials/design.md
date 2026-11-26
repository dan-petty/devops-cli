# Design

## Decisions

- **Only a container that holds the App key reads the password of the cache.** Those containers read GitHub as the App, and the shared tier answers the same reads. The private key of the App reads more than the cache does, so the new key adds no reach to them. The container `agent`, in which a model runs commands, keeps one key (#6518, ADR 0030).
- **One constant holds the key set.** `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` gets the third key, and the gate checks read the constant, so the templates, the policy and the checks cannot differ.
- **The policy changes in its key list only.** The existing rule for the three containers already binds each key other than the key of the gateway to the containers that are not `agent`.
- **The default user for now.** The Jobs send no `valkey.username`, as the Service. #6600 owns the move of each client to a role user, and the findings on #6600 show that no role user fits a whole process yet.
- **The order of the merges.** This change merges after #7292, which keeps private repositories out of the shared issue cache.

## Rejected alternatives

- **The password in each container of the runner Job:** rejected. The container `agent` runs a model with a shell, and each key in its environment is one command away from it (#6518).
- **A role user of the cache for the Jobs now:** rejected. The role `agent` reads only the fact keys, and the role `sweep` cannot write the embedding keys (comment on #6600). A Job with one of these users loses a store.
- **A new Secret for the Jobs:** rejected. It needs a step of a person before the merge, and the key of today serves.
