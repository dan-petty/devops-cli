# Design

## Decisions

1. **The store tells what is indexed.** The skip state of a file outlives the pod because Qdrant keeps it in the payload of each point of the file. The run adds no stateful volume.
2. **Two keys show a whole file.** `file_hash` is the content hash of the file that the scan computes (`_scan_single_file_for_indexing`). `file_chunks` is the count of the chunks of the file in that run, across both collections (`Counter` of the chunks in `_upsert_partitioned_chunks`). A file is whole when all its points hold one pair and the count of its points equals `file_chunks`. A skipped batch (#1296) or a run that stops leaves fewer points than `file_chunks`, so the next run embeds the file again.
3. **One read for each project, only on a cache miss.** `_StoredFiles.of` reads a project at its first file whose hash the cache does not hold, and keeps the result for the run. A workstation whose cache file holds every file reads nothing. A new pod misses at its first file, reads once and skips each unchanged file.
4. **The store fills the cache in memory.** At a miss, the stored value of the file takes the place of its cache entry. After the scan, each stored file that the cache lacks goes into the cache (`setdefault`), so `_purge_obsolete_points` deletes the old points of an edited file and `_purge_deleted_vectors` deletes the points of a deleted file. A cache entry that holds the current hash of a file stays.
5. **The read is bounded.** Each request reads at most 1000 points (`_STORED_STATE_PAGE_SIZE`), with three short payload keys and no vector, and waits at most `qdrant.timeout`. `scroll_payloads` is a generator, so the run holds one page and the state of each file, not every payload of the project. The code and docs collections can have one name, so the read takes each distinct collection once.
6. **A failed read stops the run.** `scroll_payloads` raises `QdrantClientError`, and the run raises it before any embed. A run that went on would embed every file, which is the defect.
7. **Telemetry.** Span `ai.rag.read_stored_files` holds `rag.project` and `rag.stored_files`, so a trace shows the read of each project.

## Rejected alternatives

- **Keep the cache file on a PersistentVolumeClaim.** The decision on #7467 refuses a new stateful volume. A claim adds a resource with its own life, and the cache file can still disagree with the store: `_check_project_points_intact` exists because a cleared collection leaves a cache file that says each file is indexed.
- **Read the chunk key `content_hash`.** It is the hash of the text of one chunk (`content_hash=self._hash_content(content)` in `SemanticChunker._make_code_chunk`), not of the file, so it cannot show that the stored version of a file is current.
- **Compare the stored point ids with the ids of a new chunking.** The ids are deterministic (`SemanticChunker._generate_id`), but the run would chunk every file on each run, the unchanged files too. The count key needs only the read.
- **Write `file_hash` with `set_payload` after the last chunk of a file.** That is one more request for each embedded file, so the first run after the release would send one for each file of each repository. The count key needs no request.
- **Read the store on each run, also when the cache file holds every file.** That adds one paged read of each project to each workstation run that the cache file can answer, and the decision on #7467 keeps the cache file as the local speed-up.
- **Return a list from `scroll_payloads`.** A list holds every payload of a project in memory at once. The generator holds one page.
