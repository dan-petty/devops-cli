## REMOVED Requirements

### Requirement: The README lists both rows
**Reason**: The requirement restates two rows of the secret table of the source code in a document, and only a test that reads the document can check it (#6083).
**Migration**: The requirement "One keyring value feeds both Secrets" holds both keys, and a test of the source code checks the table.
