# Design

## Context

One slow read of the pull request raises `GitHubOperationError` and leaves the loop.

## Goals

- Ride out one slow read.
- Stop on a run of failures with the last error.

## Decisions

- **Three in a row.** One failed poll is noise; three name a real outage, and the monitor stops with the last error.
- **The same interval.** The retry waits the poll interval, and the monitor's own timeout still bounds the watch.
- **A warning each time.** The line says which failure of the limit it is.

## Risks

- A watch whose deadline passes during failed reads raises the error instead of returning a timeout result. The error is the cause, and the caller sees it.

## Tests

- Two failures then a terminal status return success and print the warning.
- Three failures in a row raise the last error.
