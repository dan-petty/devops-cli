# Design

## Decisions

- **Name the database files as the ruleset files of osv-scanner.**: The request already has this seam (`ruleset_files`), the record already turns it into `ruleset_digest`, and Trivy uses it for its database metadata. The database of osv-scanner is the file `all.zip` in one directory for each ecosystem (`osv-scalibr/PyPI/all.zip`), so the hook returns `sorted(read.glob("*/all.zip"))` of the `ToolDataDir` that `data_dirs()` gives. The digest covers the content and not the paths, so it is the same for the same database in another cache directory.
- **Digest a ruleset file below a read-only bind as a stream, with no size limit.**: The npm database is 210 MB, over the 50 MiB limit, and the sandbox executor refuses a file over the limit. A file below a bind is data that devops-cli or the user put in the cache of the tool. It is not a file of the reviewed tree. A stream needs no memory, so the limit has no reason there.
- **Keep the limit for every other file.**: A config file or a ruleset file of the reviewed tree is not trusted. `ARCHITECTURE.md` asks for a size check before a read, and the contract test pins the refusal. Only the ruleset files below a bind of the request skip the limit. A config file never does.
- **Make `file_digest` read as a stream.**: It is the one function that digests a file for the record and for the benchmarks. `hashlib.file_digest` gives the same SHA-256, so every digest stays the same.
- **No change to the Ruff scanner.**: The Ruff digest already follows the config files that Ruff finds. The one gap, a base file named by `extend`, is written into `docs/SELF_IMPROVEMENT.md`.

## Rejected alternatives

- **The modified time of the database with a digest of its index.**: The scratch download of osv-scanner 2.6.0 wrote one file, `osv-scalibr/PyPI/all.zip`, and no index or metadata file. The modified time changes when the same content is fetched again, so the digest would change with no change of the database. A digest of the zip directory entries would need a new reader of the zip format in devops-cli. A stream of the file is simpler and exact.
- **Lift the limit for all files of a record.**: A config file or a ruleset file of a reviewed tree comes from the code under review. A limit on it is a threshold that only the owner may lower, and the contract test pins it.
- **A new field on `ToolRun` (`database_digest`, `config_digest: str | None`).**: `ToolRun` already has `config_digest: str` and `ruleset_digest: str`, and the Tool Runs table and the SARIF export show them. A second field would duplicate them.
- **The digest of `ruff check --show-settings`.**: The output is plain text, it holds absolute paths of the checkout, and `--isolated` ignores the config file (see Feasibility). Stripping the paths would be a new hand-written parser of a text format that Ruff does not promise to keep.
- **`get_or_compute_snapshot_digest` for the record.**: It reads `data.cache_dir/osv_db`, which the scan does not read, and it uses modified times.
