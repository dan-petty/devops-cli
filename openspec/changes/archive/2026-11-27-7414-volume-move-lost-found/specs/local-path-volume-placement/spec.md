## ADDED Requirements

### Requirement: The comparison of a volume move leaves out the top-level lost+found
The digest script of a volume move SHALL leave out the top-level `lost+found` of each side in each count and each digest. It SHALL count a directory with that name lower in the tree.

#### Scenario: A new ext4 volume
- **WHEN** a move copies a `local-path` claim to a new volume of the class `longhorn`, whose filesystem root holds an empty `lost+found`
- **THEN** the two sides have the same entries, files, bytes, metadata digest and content digest, and the move goes on
