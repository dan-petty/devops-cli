## ADDED Requirements

### Requirement: A wait records only the paths that the tree holds
A round SHALL record in `refine.wait_refs` only the paths that the tree of the commit it reads holds, as a file or as a directory that holds a tracked path.

#### Scenario: A decimal, a version, a dotted setting and a domain before two real files
- **WHEN** a wait text names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before two files that the tree holds, and `text_paths` reads the text with that tree
- **THEN** the round records the two files in `refine.wait_refs` and none of the four other values

### Requirement: The five-path cap counts only the paths that the tree holds
`text_paths` SHALL apply `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after it drops the candidates that the tree does not hold, so the first five real paths take the slots.

#### Scenario: Six real files
- **WHEN** a wait text names six files that the tree holds, and `text_paths` reads it with that tree
- **THEN** the round records the first five files and drops the sixth

### Requirement: A path that a period or a comma follows is kept
The cited-path pattern SHALL accept a period or a comma after a path, so `text_paths` finds a file that ends a sentence.

#### Scenario: A sentence ends on a path
- **WHEN** a wait text names a file that the tree holds and a period or a comma follows the path, and `text_paths` reads it with that tree
- **THEN** the round records that file

### Requirement: A value that the tree does not hold costs no commits read
The wait check MUST read no commits for a candidate that the tree does not hold, because the round drops it before it writes `refine.wait_refs`.

#### Scenario: A decimal beside a real file
- **WHEN** a wait text names a decimal and a file that the tree holds, and `path_changed_at` reads each recorded path
- **THEN** the store reads the commits of the file and records no read of the decimal

### Requirement: A directory that the tree holds is a watched path
`text_paths` SHALL keep a directory of the tree as a watched path, because a commit changes the files under it.

#### Scenario: A directory that holds a file
- **WHEN** a wait text names a directory and the tree holds a file under that directory, and `text_paths` reads it with that tree
- **THEN** the round records the directory

### Requirement: The explain verdict reads the same tree as a round
`refine_left_out` SHALL read the wait paths with the tree that its caller gives, so `devops roadmap explain` gives the verdict that a round gives (#3483).

#### Scenario: A person asks why an item waits
- **WHEN** a person runs `devops roadmap explain` on an item whose wait text names a real path and a decimal
- **THEN** the verdict reads the real path alone, through `refine_left_out`
