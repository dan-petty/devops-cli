# Design

## Context

The compile runs once per job to spare each worker a compile during collection (#1735). A test job runs several workers that import most of the suite, so the compile runs again in each worker.

## Goals

- Remove the sync compile from the test jobs.
- Keep it in the jobs that run one process, such as Static Analysis.

## Decisions

- **An input with a true default.** Jobs opt out, and the other jobs keep the compile.
- **The four test jobs.** They import most modules in several processes.
- **No tooling-cache change.** `.pytest_cache` is used by pytest, and the Service Image Tests restore none already.

## Risks

- The first worker compile adds CPU time at the start. The measured saving is 9 to 11 s per job.

## Tests

- The action holds the input with a true default.
- The four test jobs pass false.
