# Design

## Overview

The `plan-check` job copies the two committed encoding files into a cache directory before the command runs. Both steps name the directory through `TIKTOKEN_CACHE_DIR`. The code that counts tokens is not changed.

## Decisions

- The step is a shell loop of the workflow. Tiktoken names a cache file by the SHA-1 of its blob URL, and `sha1sum` gives it. The job installs no package and needs no network.
- The directory is `${{ runner.temp }}/tiktoken-cache`. A `runner` context is not available at job level, so both steps set the variable.
- An invariant test reads the workflow and asserts the order and the shared directory. It runs offline in the normal suite, so a removal of the step fails the pull request before it merges.

## Rejected Alternatives

- **`actions/cache`**: a clean runner has no entry to restore. The first run, and every run after an eviction, would fail as before.
- **Download the files from the OpenAI blob store**: the job gets a network dependency and an unpinned input.
- **A character estimate when the cache is missing**: the stage and the implement job use one exact measure (`count_tokens`). A second measure could give a different count for the same text.
