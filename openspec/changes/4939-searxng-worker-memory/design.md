# Design

## Decisions

- **Replace the worker, do not only raise the limit.** A higher limit alone moves the OOM kill from 5 days to about 18 days. Granian's worker replacement ends the growth with no container restart.
- **512 MiB for the worker.** It is four times the measured peak of 10 queries at once (122 MiB), so a burst of searches does not start a replacement.
- **1 Gi for the container.** It holds the main process (about 35 MiB), the resource tracker (about 15 MiB), the old worker at 512 MiB and the new worker (about 115 MiB at start) while Granian replaces the old one.
