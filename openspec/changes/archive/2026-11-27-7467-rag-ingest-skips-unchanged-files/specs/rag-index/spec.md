## ADDED Requirements

### Requirement: Each point holds the hash and the chunk count of its file
The indexer SHALL write in the payload of each point the key `file_hash`, the content hash of the whole file of the chunk, and the key `file_chunks`, the count of the chunks of that version of the file across the code and docs collections.

#### Scenario: A file of two chunks
- **WHEN** a run embeds a file whose text gives two chunks
- **THEN** each of the two points holds the content hash of the file as `file_hash` and `2` as `file_chunks`

### Requirement: A cache miss reads the file state of the project from the store
When the cache file does not hold the content hash of a file, the run SHALL read the file state of its project from the store once, with one paged scroll of `file_path`, `file_hash` and `file_chunks` for each collection. A run whose cache file holds the hash of each file SHALL read nothing from the store. A failed read SHALL stop the run before it embeds a chunk.

#### Scenario: The cache file holds every file
- **WHEN** a second run with the same cache folder indexes a workspace with no change
- **THEN** the run makes no scroll of the file state and embeds no chunk

#### Scenario: The store read fails
- **WHEN** the scroll of the file state raises `QdrantClientError` in a run with a new cache folder
- **THEN** the run raises that error and embeds no chunk

### Requirement: A run skips a file that the store holds whole
The run SHALL skip a file whose points all hold its current content hash as `file_hash` and whose count of points equals `file_chunks`, with no embed and no upsert.

#### Scenario: The store holds every file
- **WHEN** a run with a new cache folder indexes a workspace whose code file and document the store already holds with their current hashes
- **THEN** the run embeds no chunk, upserts no point, and returns `skipped_files` 2 and `total_chunks` 0

### Requirement: A run embeds again a file that the store does not hold whole
The run SHALL embed a file whose points hold no `file_hash`, another hash, or fewer points than `file_chunks`, and SHALL delete its old points first. It SHALL delete the points of a stored file that the workspace no longer holds.

#### Scenario: One file changed
- **WHEN** a run with a new cache folder indexes a workspace of two files, one of them edited since the store got it
- **THEN** the run embeds only the chunks of the edited file, and the store holds only the new points of that file

#### Scenario: Points with no file hash
- **WHEN** a run with a new cache folder indexes a workspace whose points hold no `file_hash`, and then a second run with a new cache folder indexes it again
- **THEN** the first run embeds each file once, and the second embeds no chunk

#### Scenario: A file that a skipped batch left incomplete
- **WHEN** a run skipped a batch inside `big.py`, and a run with a new cache folder resumes
- **THEN** the resume embeds every chunk of `big.py` and no chunk of the other file

#### Scenario: A file deleted from the workspace
- **WHEN** a run with a new cache folder indexes a workspace that no longer holds a file whose points the store holds
- **THEN** the run deletes the points of that file and returns `removed_files` 1

### Requirement: The client reads payload keys page by page
`QdrantClient.scroll_payloads` SHALL read the points of a collection that match a payload filter in pages of `page_size` points, with only the payload keys that the caller names and no vector, and SHALL start each request at the offset that the page before returned. A collection that does not exist SHALL give no payload. A failed request SHALL raise `QdrantClientError` that names the server and holds no URL.

#### Scenario: Five points over pages of two
- **WHEN** a collection holds five points of project `app` and five of another project, and the caller reads `file_path` and `file_hash` of project `app` with `page_size` 2
- **THEN** the read gives the five payloads of project `app`, each with only those two keys where the point holds them
