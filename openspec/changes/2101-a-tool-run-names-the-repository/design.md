# Design

## Decisions

- **Use git remote get-url origin through the existing _git helper to read the repository URI**: It is the standard git command for this, and the _git helper already handles subprocess execution and error reporting
- **Strip the userinfo from the URL before storing it**: The issue requires no credential in the URI, and a SARIF consumer must not see a token
- **Write versionControlProvenance only when the commit is clean and repository_uri is set**: SARIF 2.1.0 section 3.23.4 says revisionId must identify the revision of the scanned files, and a -dirty commit does not; the schema requires repositoryUri in versionControlDetails
- **Write no versionControlProvenance when repository_uri is None**: The SARIF schema requires repositoryUri in versionControlDetails, so a missing URI means the object cannot be written

## Rejected alternatives

- **Read the repository URI from an environment variable or config file**: The issue says read from git, and the existing _git helper is the established pattern for reading checkout metadata
- **Write versionControlProvenance for dirty commits with a note field**: SARIF 2.1.0 section 3.23.4 says revisionId must uniquely and permanently identify the revision of the scanned files; a -dirty commit does not, and the schema has no note field for this
