# Design

## Decisions

- **Raise ConfigurationError instead of removing the value from the anchor mapping.**: The anchor may be shared by multiple merge targets. Removing from the anchor would silently affect keys the user did not ask to remove. A clear error names the file and tells the user to remove the key from the anchor mapping directly.
- **Pass name into _find so the error message can name the file.**: The existing error pattern in the module names the file, for example 'Cannot read {name}: it is not valid YAML'. The new error follows the same pattern.
- **Check node.lc.key(dotted) for None before indexing.**: ruamel.yaml gives no position for a merged key, so lc.key returns None. Indexing None[0] raises TypeError. The None check is the minimal fix at the point of failure.

## Rejected alternatives

- **Remove the value from the anchor mapping when the user unsets a merge-derived key.**: The anchor may be shared by other merge targets. Removing from it would silently change keys the user did not request. The user asked to remove ai.api_key, not a.b.api_key.
- **Print a generic 'key not found' message.**: The key is found in the merged mapping. A 'not found' message is misleading and does not tell the user what to do.
