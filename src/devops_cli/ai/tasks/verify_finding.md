## Atomic Finding Verification Protocol

Validate reported findings against visible code and related file analysis metadata by testing their criteria:

1. **Test `verification_criteria`**:
   - Check if the observable conditions asserting the defect are factually true in the code.
   - List all confirmed criteria in `verified_criteria_matched`.

2. **Test `invalidation_criteria`**:
   - Check if any invalidating conditions (upstream mitigations, type safety, example file templates, proper helper configurations) are true in the code.
   - List all confirmed invalidations in `invalidated_criteria_matched`.

3. **Compute Decision & Confidence**:
   - If ANY `invalidation_criteria` are satisfied: mark `"verified": false, "mitigated": true|false, "status": "INVALIDATED"|"MITIGATED", "reportable": false`.
   - If `verification_criteria` are satisfied and zero invalidation criteria match: mark `"verified": true, "mitigated": false, "status": "VERIFIED", "reportable": true`.
   - Confidence score should reflect the proportion of satisfied verification criteria without invalidations.

## Output Format
Return ONLY a JSON array with one object per input finding:
```json
[
  {
    "verified": true,
    "mitigated": false,
    "status": "VERIFIED",
    "reportable": true,
    "severity": "HIGH",
    "location": "path/to/file.ext:12-18",
    "confidence_score": 0.95,
    "verified_criteria_matched": ["..."],
    "invalidated_criteria_matched": []
  }
]
```
