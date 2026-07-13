# SAM promptable-mask contract: verified facts

Research date: 2026-07-12. Sources are limited to Meta's official SAM 3 repository, Meta's official announcement, and Meta's official Hugging Face repositories. Source-code references are pinned to official commit [`5dd401d`](https://github.com/facebookresearch/sam3/tree/5dd401d1c5c1d5c3eedff06d41b77af824517619) (2026-06-15), the current `main` inspected for this note.

## Terminology correction

**Verified:** Meta officially released **SAM 3.1** on 2026-03-27. It is described as a drop-in update to SAM 3 that adds Object Multiplex for joint multi-object video tracking. The release notes and checkpoint repository call the release and checkpoint “SAM 3.1”; they do not name a separate product or model **“SAM 3.1 Tracker.”** The code does use tracker-related classes and describes its visual-prompt task as tracking, so “SAM 3.1 tracker” is understandable shorthand for SAM 3.1's promptable visual segmentation/video-tracking path, but it should not be used as an exact model identifier. [Meta announcement](https://ai.meta.com/blog/segment-anything-model-3/), [official release notes](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/RELEASE_SAM3p1.md), [official checkpoint card](https://huggingface.co/facebook/sam3.1)

The exact public checkpoint identifier is `facebook/sam3.1`, and the released file is `sam3.1_multiplex.pt` (3.5 GB as listed by Hugging Face). The previous checkpoint is `facebook/sam3` / `sam3.pt`. The official builder defaults to version `"sam3.1"`. [checkpoint files](https://huggingface.co/facebook/sam3.1/tree/main), [builder source](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model_builder.py#L658-L673)

## Official inference surfaces

### Reusable video state and request protocol

**Verified:** The recommended SAM 3.1 entry point is:

```python
predictor = build_sam3_predictor(version="sam3.1", ...)
```

It returns a stateful predictor with `handle_request()` and `handle_stream_request()`. The common request types are `start_session`, `add_prompt`, `propagate_in_video`, `remove_object`, `reset_session`, `cancel_propagation`, and `close_session`. `start_session` accepts a JPEG directory or video path as `resource_path` and returns a UUID-like `session_id`; the predictor retains the heavy inference state in its process until reset/close. [unified builder and example](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model_builder.py#L1243-L1321), [request dispatcher and state lifecycle](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_base_predictor.py#L35-L149)

The exact visual-prompt request accepted by the public dispatcher is:

```python
{
  "type": "add_prompt",
  "session_id": str,
  "frame_index": int,
  "text": str | None,
  "points": [[x, y], ...] | Tensor | None,
  "point_labels": [int, ...] | Tensor | None,
  "clear_old_points": bool,       # default True
  "bounding_boxes": [[x, y, w, h], ...] | Tensor | None,
  "bounding_box_labels": [int, ...] | Tensor | None,
  "clear_old_boxes": bool,        # default True
  "output_prob_thresh": float,    # default 0.5
  "obj_id": int | None,
  "rel_coordinates": bool,        # default True
}
```

The returned envelope is `{"frame_index": ..., "outputs": ...}`. Output dictionaries include object IDs, XYWH boxes and binary masks (`out_obj_ids`, `out_boxes_xywh`, `out_binary_masks`). [dispatcher/add-prompt implementation](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_base_predictor.py#L50-L208), [output conversion](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_base_predictor.py#L209-L245)

**Verified:** `point_labels` uses `1` for a positive/include point and `0` for a negative/exclude point. Multiple mixed positive and negative points may be sent in one request for one `obj_id`; the official notebook demonstrates a single four-point refinement with labels `[1, 0, 0, 1]`. Coordinates are relative by default, and the notebook normalizes `(x, y)` by image width and height. Setting `clear_old_points=False` accumulates rather than replaces prior clicks. [official SAM 3.1 notebook](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/examples/sam3.1_video_predictor_example.ipynb), [tracker point-label contract](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_tracker_base.py#L225-L280)

**Important limitation:** this is a batch of clicks for one object, not a documented service-level batch of unrelated prompt jobs. Multi-object interaction is expressed with object IDs/repeated prompt calls; SAM 3.1 internally multiplexes tracked objects. A Supersplat service may define its own batch RPC, but that would be an adapter contract, not an official SAM request primitive.

Propagation is streamed:

```python
{
  "type": "propagate_in_video",
  "session_id": str,
  "propagation_direction": "both" | "forward" | "backward", # default both
  "start_frame_index": int | None,
  "max_frame_num_to_track": int | None,
  "output_prob_thresh": float,
}
```

Each yielded response contains `frame_index` and `outputs`. [stream dispatcher](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_base_predictor.py#L100-L115), [propagation implementation](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_base_predictor.py#L256-L305)

### Reusable image state

**Verified:** The concept-segmentation image API builds `build_sam3_image_model()`, wraps it in `Sam3Processor`, calls `state = processor.set_image(image)`, then reuses that state with `set_text_prompt(state=state, prompt=...)`. `set_image_batch(images)` is also public. This image processor is primarily the text/exemplar PCS surface. [README example](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/README.md#L121-L137), [processor source](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam3_image_processor.py#L25-L97)

**Verified:** For SAM-1-style interactive point/box segmentation on still images, the official repository builds the image model with `enable_inst_interactivity=True`, uses `Sam3InteractiveImagePredictor`, calls `set_image()` once, then `predict(point_coords=..., point_labels=..., box=..., mask_input=..., multimask_output=...)`. Its `predict_batch` accepts lists per image. This is a distinct API from `Sam3Processor.set_text_prompt`. [official SAM-1 task notebook](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/examples/sam3_for_sam1_task_example.ipynb), [image predictor API](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model/sam1_task_predictor.py#L70-L280)

**Inference for the Supersplat contract:** generated views are naturally representable as a short ordered frame sequence, so the official video session API gives reusable per-frame embeddings plus later cross-view propagation/refinement. Treating every generated view as an unrelated image would instead require application-owned state and association. Meta does not document generated 3D viewpoints as equivalent to temporal video; that equivalence must be benchmarked rather than assumed.

## Model/config choice and 24 GB VRAM

**Verified:** Meta publishes one SAM 3.1 multiplex checkpoint, not an official small/base/large family. Public knobs relevant to resource use are `max_num_objects` (default 16), `multiplex_count` (default 16), `compile`, `use_fa3`, `async_loading_frames`, and session options `offload_video_to_cpu` / `offload_state_to_cpu`. The official requirements are Python 3.12+, PyTorch 2.7+, CUDA 12.6+; Flash Attention 3 is optional. [builder signature](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/sam3/model_builder.py#L1243-L1277), [installation requirements](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/README.md#L70-L110)

**Not verified:** Meta provides no official claim in these sources that SAM 3.1 fits or meets a latency target on an RTX 4090D with 24 GB VRAM. Published efficiency numbers use H100 GPUs, including about 7× at 128 objects and 16-to-32 FPS for medium object counts. Those figures cannot be transferred to a 4090D. [release notes](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/RELEASE_SAM3p1.md), [Meta announcement](https://ai.meta.com/blog/segment-anything-model-3/)

**Conservative inference:** SAM 3.1 is the only official current checkpoint to prototype, with object count constrained to the use case and CPU offload available as a fallback. Whether 24 GB is sufficient for the chosen generated-view count/resolution and retained state is an empirical acceptance test, not a fact that can be placed in the service contract.

## License and access constraints

**Verified:** Code, weights, documentation, inference code and fine-tuning code are collectively “SAM Materials” under Meta's bespoke **SAM License**, not Apache/MIT and not OSI-labelled on Hugging Face (`License: other`). Access to both official checkpoint repositories is gated: a user must request access, agree to share contact information, and authenticate with Hugging Face. [SAM License](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/LICENSE), [SAM 3.1 gate](https://huggingface.co/facebook/sam3.1), [repository access instructions](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/README.md#L111-L119)

The license grants a non-exclusive, worldwide, non-transferable, royalty-free **limited** right to use, reproduce, distribute, copy, modify and create derivatives. Redistribution of SAM Materials or derivatives must remain under the same agreement and include it. Publications using the materials must acknowledge them. Use must comply with law, privacy/data protection and trade controls. It prohibits use involving or encouraging reverse engineering/decompilation/discovery of underlying components, and prohibits ITAR-controlled and specified military/warfare, nuclear, espionage, gun and illegal-weapon end uses. It includes no support/warranty, a patent/IP-litigation termination clause, and requires deletion/cessation after termination. Meta may modify the agreement, with continued use constituting acceptance. [full official license](https://github.com/facebookresearch/sam3/blob/5dd401d1c5c1d5c3eedff06d41b77af824517619/LICENSE)

**Inference, not legal advice:** downloading weights during installation or redistributing them inside a Supersplat package creates operational and licensing obligations. The lowest-risk PoC packaging is to keep the adapter code separate, require the operator to obtain gated access and download the checkpoint themselves, record the accepted license/version, and avoid redistributing the checkpoint until counsel/project owners approve that distribution path.

## Contract consequences supported by the evidence

1. Name the dependency `SAM 3.1` and pin checkpoint `facebook/sam3.1/sam3.1_multiplex.pt`; use “tracker” only for the visual-prompt capability or adapter component.
2. Put a stable application-level contract in front of Meta's mutable Python dictionaries. Preserve session, frame, object ID, mixed point labels, coordinate convention, replacement/accumulation flags, threshold, streaming propagation, cancellation, reset and close semantics.
3. Keep model state server-side and opaque. Do not serialize Meta internals into the editor protocol.
4. Define application batching separately: one correction may contain many positive/negative clicks for one target; do not claim the official API atomically batches independent objects/jobs.
5. Treat 4090D/24 GB fit, view resolution/count and latency as benchmark unknowns. The official sources do not settle them.
6. Make checkpoint acquisition and SAM License acceptance explicit deployment prerequisites; do not silently bundle gated weights.
