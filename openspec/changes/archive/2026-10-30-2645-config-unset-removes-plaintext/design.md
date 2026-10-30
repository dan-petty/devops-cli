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

### 5. A copy that is not a YAML mapping stops the removal
- Decision: `_redact` raises `ConfigurationError` that names the copy and quotes no text, for a copy that is not UTF-8 text, is not YAML, or holds YAML that is not a mapping (a list, or a plain line such as `ai.api_key=<value>`). A copy that holds nothing, or only comments, stays as it is. `back_up` redacts the older copies first and makes the new copy after them, and it runs before the file is replaced. So a failure leaves the file as it was and makes no new copy.
- Rationale: Such a copy can hold the credential, and the command cannot find it by key. A silent skip would be a swallowed error. The person deletes or fixes the copy, and runs the command again. Copies that devops-cli made are valid YAML, because `round_trip.edit` refuses a file that is not.

### 6. A comment that holds the value loses its text
- Decision: `round_trip.edit` takes `scrub`, a list of texts. After the edit, each comment line that holds one of them, in the end-of-line comment of the key, in a comment above it or anywhere else in the copy, is emptied. `_redact` passes the lines of the replaced value. Other comments stay.
- Rationale: A note such as `# was <value>` is part of the copy. It walks the comment tokens that ruamel.yaml keeps, with no regular expression over the file.
- Limit: The live file keeps a comment above the removed key. That comment is not a copy, and the command removes only the key and its end-of-line comment.

### 7. A copy is read and written as bytes
- Decision: `_copy` reads and writes bytes and decodes only to parse. A copy with CRLF line ends is edited with LF line ends and written back with CRLF. A copy with nothing to redact keeps its bytes.
- Rationale: `read_text` and `write_text` turned CRLF into LF in every line of the copy.

### 8. Empty values and the placeholder stay as they are
- Decision: `_redact` writes nothing for a copy that holds no value at the key, an empty value, or the placeholder.
- Rationale: There is nothing to hide, and the copy keeps its bytes and its comments.

## Risks / Trade-offs

- [ruamel.yaml rewrites the inline comment spacing of a redacted line] -> The comment text stays. Only the spaces before it can change.
- [A comment that holds the value stays in the copy] -> `scrub` empties each comment line that holds a line of the value. A very short value, such as one character, also empties every comment that holds that character. A credential is not that short, and the copy loses only comment text.
- [A copy that mixes LF and CRLF] -> It gets CRLF in every line. A mixed copy is rare, and the content of each line stays.
- [Older copies change after the fact] -> They change only at the redacted keys, and only when a removal takes out the credential that they hold.
- [A person wants the old value back after a wrong removal] -> The value was in the keyring or in a place that the person has. The change states that the copy does not keep it, and the help says so.
