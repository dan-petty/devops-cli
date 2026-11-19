## Purpose
The labelled gold set of questions about tool, library and project facts, its stale marking against the checked-in sources, the offline scorer that reports hit rate and stale share, and the benchmark document corpus and domain vocabulary that come from the docs directory.

## ADDED Requirements

### Requirement: Gold set loads and validates
The gold-set loader SHALL load every entry of the checked-in gold set file and SHALL reject an entry that lacks a question, an expected source, an expected answer, or a fact type.

#### Scenario: Incomplete entry is rejected
- **WHEN** an entry omits its expected source
- **THEN** the loader raises a validation error that names the entry and the missing field.

#### Scenario: Every entry is loaded
- **WHEN** the loader reads the checked-in gold set
- **THEN** it returns each entry with its question, its expected source, its expected answer and its fact type.

### Requirement: Gold set covers three fact types
The checked-in gold set MUST hold at least one entry for each of the tool, library and project fact types.

#### Scenario: All three fact types are present
- **WHEN** the loader reads the checked-in gold set
- **THEN** the set holds at least one entry for each of the three fact types.

### Requirement: Stale entries are marked
The loader MUST mark an entry as stale, with a reason, when its expected source is a checked-in path that is absent or no longer holds the expected answer text.

#### Scenario: Expected answer is gone
- **WHEN** an entry's checked-in expected source no longer holds its expected answer
- **THEN** the loader returns the entry marked stale with a reason that names the source path.

#### Scenario: Expected source is absent
- **WHEN** an entry's checked-in expected source is not in the folder
- **THEN** the loader returns the entry marked stale with a reason that names the absent path.

### Requirement: Version drift marks an entry stale
The loader MUST mark an entry as stale when its expected source is a knowledge base article that the manual matcher reports as drift against the tool versions that the caller passes.

#### Scenario: Mismatched version marks an entry stale
- **WHEN** the expected source's front matter names a version other than the one the caller passes
- **THEN** the entry is stale and its reason is the drift reason of that article.

### Requirement: Scorer reports hit rate and stale share
The scorer SHALL report hit rate at k=5, the share of entries whose expected source is among the five best-ranked documents of the source, and stale share, the count of stale entries divided by the count of all entries.

#### Scenario: One hit of two entries is half
- **WHEN** the scorer scores a gold set of two entries and one expected source is ranked in the top five
- **THEN** it reports a hit rate at k=5 of 0.5, a stale share of 0.5 and the counts 1 of 2.

#### Scenario: A missing expected source is no hit
- **WHEN** no document of the source is the expected source of an entry
- **THEN** the entry counts as a miss and the hit rate falls.

### Requirement: Scorer runs offline
The scorer MUST take the Qdrant client and the embedder that it uses as arguments and MUST make no network call of its own.

#### Scenario: Offline scoring uses the fakes
- **WHEN** a test scores a retrieval source with the fake Qdrant client and the fake embedder installed
- **THEN** the scorer reads the fake answers and the hermetic floor records no network access.

### Requirement: Score block for both sources
The scorer SHALL emit a Markdown score block with one row for the checked-in knowledge base folder and one row for the generated project digest, each with its hit rate at k=5 and its stale share.

#### Scenario: Both sources produce a score row
- **WHEN** the scorer runs with both built-in source adapters
- **THEN** the block holds a knowledge base row and a project digest row, each giving a hit rate and a stale share.

### Requirement: Benchmark corpus from docs and index
The benchmark document corpus builder MUST take its files from the docs directory, which holds the generated knowledge base index, from the top-level project documents and from the task prompts, and MUST NOT read any file under the knowledge base folder.

#### Scenario: Corpus survives folder removal
- **WHEN** the knowledge base folder is absent from a test fixture that holds the docs directory and the generated index
- **THEN** the builder returns the same corpus entries as with the folder present and raises no error.

### Requirement: Benchmark domain vocabulary from docs
The benchmark MUST take the domain vocabulary that labels its evaluation tasks from the docs pages that its checked-in domain map names under the repository root that the caller passes, and MUST NOT read the knowledge base folder for it.

#### Scenario: Eval task categories come from the docs
- **WHEN** the benchmark samples evaluation tasks from a root whose docs pages hold the domain terms and whose knowledge base folder holds a marker article
- **THEN** each task's category comes from the docs vocabulary of that root and the marker article changes no category.
