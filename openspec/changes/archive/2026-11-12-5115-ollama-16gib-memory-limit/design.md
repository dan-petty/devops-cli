# Design

## Decisions

- The limit is `8Gi`, equal to the request. A limit equal to the request lets the container use no memory above what the scheduler set aside for it, so the tier cannot overcommit the node. The value holds one model load: `ollama-64gib` uses 6.4 GiB with its 27B model loaded, and the GPU of this tier holds the weights of a smaller model.
- The tier sets no `LLAMA_ARG_CACHE_RAM`. By default `llama-server` keeps up to 8,192 MiB of prompt cache in host memory, so a long session straight to the tier can reach the limit, and the kernel then stops the container. The tier serves nothing, so a restart of its container is the wanted result, and the node keeps its memory.
- The CPU request stays `3000m` and the tier gets no CPU limit, as the other tiers have none. CPU is compressible, and the issue is about memory.
- The test reads the container by its name `ollama`, not by its index, because the pod also has the initContainer `own-model-directory`.

## Rejected alternatives

- A limit of `12Gi`, as on `ollama-64gib`. The pods of the node would then have limits of about 14 GiB, above the 13 GiB of allocatable memory after the system reservation. The tier serves nothing, so it needs no room for a second model or a large prompt cache.
- No limit, and a reliance on the system reservation of the node alone. The reservation lowers allocatable and lets the kubelet evict pods at 500Mi of free memory, but it does not stop one container from taking the memory of the other pods of the node.
- Removing the DaemonSet. The specification "The gateway sends the 16 GiB tier nothing" keeps the DaemonSet and its Services, so that a revert brings the tier back.
