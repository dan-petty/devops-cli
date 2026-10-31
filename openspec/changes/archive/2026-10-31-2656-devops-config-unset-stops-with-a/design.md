# Design

## Decisions

- **Raise a ConfigurationError instead of removing the value from the anchor mapping**: The anchor may be shared by multiple merge targets. Removing from the anchor would silently affect keys the user did not ask to remove. A clear error names the file and tells the user to remove the key from the anchor mapping directly.
- **Pass name into _find rather than catching TypeError in find**: The error message must name the file. Passing name into _find keeps the error at the point of detection and follows the existing pattern where find raises ConfigurationError with name.

## Rejected alternatives

- **Remove the value from the anchor mapping**: The anchor may be shared by other merge targets. Removing from it would silently change keys the user did not request. The user asked to remove ai.api_key, not a.b.api_key.
- **Print a generic 'key not found' message**: The key is found in the merged mapping. A 'not found' message is misleading and does not tell the user what to do.
