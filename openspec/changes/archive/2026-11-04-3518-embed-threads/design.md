## Decisions

### The thread count is an environment variable of the tier

`LLAMA_ARG_THREADS` is in the DaemonSet of the tier. Rejected: `num_thread` in `litellm_params` of the gateway deployments. Ollama reloads the model when a request sends another value, which took 4.3 s, so a caller that sends no option would reload the model after each gateway call.

### Only an embedding-only tier sets it

A chat tier can have layers on the CPU, where threads do work. The per-GPU threshold alone does not set the variable.

### The CPU request stays at 2

With one thread, an instance uses 1.2 cores under load, so the request of 2 CPUs now fits.

### Embeddings keep simple-shuffle

`least-busy` sent each batch to the first deployment, so it is rejected by measure. `simple-shuffle` gives 77% to 98% of the throughput of ideal client-side balancing (1.10 batches a second), because two batches can land on one GPU.
