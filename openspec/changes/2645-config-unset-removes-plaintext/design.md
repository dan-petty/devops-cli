# Design

## Context

See proposal.md for the background. `remove_config_key` finds the key path in the text of the file (`round_trip.find`), edits the text (`round_trip.edit`) and calls `_write_content`. `_write_content` calls `write_history.back_up`, which copies the file before `os.replace` writes the new content.

## Goals / Non-Goals

**Goals:**
- After `devops config unset` removes a credential, no copy of the file that the command keeps holds the value.
- Keep the other content of each copy, so a person can undo the removal of another key.

**Non-Goals:**
- The audit does not scan the copies. The change makes the copies safe instead of scanning them.
- A write that is not a removal does not redact. Its copy repeats a value that the file held before.
- A credential under a key with more than two levels is #2511.
- A key that a YAML merge key gives is #2656.
- The mode of the config file (0644 when a person creates it with the default umask) is not changed here.

## Decisions

### 1. Redact the value, keep the key
- Decision: A copy shows a removed credential as `***REDACTED***` and keeps the key.
- Rationale: The placeholder is not a valid credential, and it shows that a value was there. The key name is not a secret.
- Alternative considered: Make no copy when the removal takes out a credential.
  - Rejected: A person who removes the wrong key cannot undo it.
- Alternative considered: Make the copy, and delete it after the write.
  - Rejected: The same loss of the undo. A crash between the two steps leaves the credential on disk.
- Alternative considered: An empty string or YAML `null` as the placeholder.
  - Rejected: An empty string reads as "was empty", and `null` changes the type of the value.

### 2. The redaction is a parameter of `back_up`
- Decision: `back_up(path, redact)` writes the new copy already redacted. The caller names the key paths.
- Rationale: The function owns the copy and the retention. The new copy never holds the credential, also not for a moment. `_copy` writes a temporary file and calls `os.replace`, so no half-written copy is visible.
- Alternative considered: Redact in `remove_config_key` after `back_up` returns.
  - Rejected: The copy then holds the credential until the second step ends, and the caller must know the layout of the copies.

### 3. The redaction covers the retained older copies
- Decision: After the new copy, `back_up` redacts the same key paths in each older retained copy.
- Rationale: A write of any other key copies the whole file, with the credential in it. Up to 9 such copies exist. A redaction of the new copy alone leaves the credential on disk, and the audit does not find it.
- Alternative considered: Redact the new copy only (the plan of the issue).
  - Rejected: The probe in the Feasibility section shows the older copies hold the value.

### 4. A credential is a dotted key of `secret_keys()`
- Decision: `credential_paths` lists the leaves of the file at or below the removed key path whose dotted name is in `secret_keys()`.
- Rationale: It is the set that the settings already use for the keyring and the audit. A removal of a section redacts each credential in it. A key that is not a credential keeps its value in the copy, as before.
- Alternative considered: Redact only when the removed key itself is a credential.
  - Rejected: `devops config unset ai` removes `ai.api_key` as well, and its copy would hold the value.

### 5. A copy that is not YAML stops the removal
- Decision: `_redact` raises `ConfigurationError` that names the copy and quotes no text. `back_up` runs before the file is replaced.
- Rationale: Such a copy can hold the credential, and the command cannot find it by key. A silent skip would be a swallowed error. The person deletes or fixes the copy, and runs the command again. Copies that devops-cli made are valid YAML, because `round_trip.edit` refuses a file that is not.

### 6. Empty values and the placeholder stay as they are
- Decision: `_redact` writes nothing for a copy that holds no value at the key, an empty value, or the placeholder.
- Rationale: There is nothing to hide, and the copy keeps its bytes and its comments.

## Risks / Trade-offs

- [ruamel.yaml rewrites the inline comment spacing of a redacted line] -> The comment text stays. Only the spaces before it can change.
- [Older copies change after the fact] -> They change only at the redacted keys, and only when a removal takes out the credential that they hold.
- [A person wants the old value back after a wrong removal] -> The value was in the keyring or in a place that the person has. The change states that the copy does not keep it, and the help says so.
