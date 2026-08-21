1. Add `concurrency` block keyed by workflow and branch/ref:
   `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }`.
2. Add top-level `permissions` block enforcing least privilege (e.g. `contents: read`, `id-token: write`).
3. Action version pinning or secure SHA references.
4. Explicit error handling and timeout bounds (`timeout-minutes`).
