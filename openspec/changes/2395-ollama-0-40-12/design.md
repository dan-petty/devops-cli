# Design

## Where the release lives

`k8s/llm/profiles/ollama-profiles.yaml` holds the nine Ollama tiers. Each tier names the image twice: in the `ollama` container and in the `own-model-directory` init container, which runs `chown` from the same image. The kustomization of the directory overrides no image. All 18 places move to `ollama/ollama:0.40.12`.

## Why the test checks one image and a floor

- **One image.** A node runs the tier that its VRAM selects, and every tier keeps its models in the node's `/var/lib/ollama`. A node that moves to another tier, for example after a GPU change, reads the same store with the release of the other tier. 0.40 writes new manifests to `manifests-v2`, which 0.34 does not read. One image for every tier keeps one reader of the store. The init container uses the same image, so a node pulls one image.
- **The floor.** 0.40.4 is the first release that runs a multimodal embedding model through `llama-server`. A later bump only has to stay at or above it, so the test does not force every future bump to edit it.

## Rejected alternatives

- **Pin 0.40.4, the first release that runs the model on Linux.** Rejected: 0.40.12 is the newest release. The releases after 0.40.4 add models, MLX work and fixes of the OpenAI-compatible Responses API. Their notes list no change of a setting that the tiers use.
- **Set `OLLAMA_NOPRUNE` for the first start.** Not needed: 0.40.12 reads every existing manifest, so the prune finds no blob of an existing model. `/api/tags` of the test pods listed every model of the live tier.
- **Set one KV cache type on every tier that embeds.** Rejected for this change: `ollama-16gib` embeds with a `q4_0` KV cache, which changes its vectors. That is a defect of its own (#2396), and its fix changes the KV memory of that tier's chat model.
- **Pin the image by digest.** Rejected: this repository pins the image of every manifest by tag, and a change of that convention is not part of this issue.

## Test

The test is an invariant test of a committed file, and it reads no network. It fails on the pins of 0.34.4 and passes on those of 0.40.12.
