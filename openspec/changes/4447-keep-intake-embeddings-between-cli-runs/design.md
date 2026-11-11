# Design

## Decisions

- **Order of the tiers: memory, Valkey, disk, model.** In the Service, Valkey stays the first shared tier. On a workstation, the Valkey tier fails soft behind its breaker, and the disk tier gives the hit. A disk hit goes into the memory tier and into Valkey, so the next replica or process gets it from Valkey.
- **One SQLite file under the data directory.** The path is `ai/embeddings.db` under `data.dir`, which resolves as the spend ledger resolves it, so all worktrees of one repository use one file. The table has the columns `model`, `text_sha256`, `vector` and `used_at`, with the primary key `(model, text_sha256)`. The file uses WAL, so a reader does not stop a writer of another process.
- **The vector is a blob of IEEE 754 doubles** (`array('d')`). A hit gives the same floats that the model sent, so a cosine score and a duplicate decision do not change. A vector of 1,024 dimensions takes 8 KiB, so one comparison set of 1,866 texts takes about 15 MiB.
- **Expiry by the time of last use.** A hit sets `used_at`. Each write removes the rows with a `used_at` older than 30 days. The comparison set of intake grows with each issue, so a bound on the count of rows would push out vectors that each run still uses. A bound on the idle time keeps each vector that a run asks for and removes old versions of edited texts.
- **The disk tier is opt-in.** Only `GatewayIntakeModel` gives the engine a disk cache. The embedding benchmark measures the latency of the model, and a disk hit would hide it. The RAG indexer embeds many chunks and keeps its own index cache of files.
- **A cache only.** A stored value that is not a nonempty array of doubles is a miss, and the fresh vector replaces it. A `sqlite3.Error` or an `OSError` turns the tier off for the life of the object, with one warning that names the file, and the run continues on the model.
- **Memory tier of 2,048 vectors.** It holds one comparison set of about 1,866 texts. At 1,024 floats a vector, the tier holds about 64 MiB at most, inside the 3Gi limit of the Service.

## Rejected alternatives

- **A Valkey in the devcontainer** (the design in the issue): the owner plans one central Valkey store (#4517), and a second instance in each container needs a package, a post-start task and a running process. A disk file needs none of these.
- **`diskcache`**: not in `uv.lock`, last release 5.6.3 on 2023-08-31, and the advisory GHSA-w8v5-vhqr-4h9v (CVE-2025-69872) for pickle by default.
- **A JSON file of all vectors**: each run reads and writes all of the file, and two runs at the same time lose writes. SQLite gives atomic transactions and a lookup by key.
- **Float32 blobs**: half the size, but a hit then differs from the reply of the model, and a duplicate score near its threshold can change.
- **A bound on the count of rows**: the comparison set grows with the repository, so a fixed bound pushes out vectors that each run uses (see Decisions).
- **The disk tier on for every caller**: the benchmark would measure the file and not the model, and a RAG index of a large repository would fill the file.
- **Only a larger memory tier**: a new process starts with an empty memory tier, so it does not keep vectors between runs.
