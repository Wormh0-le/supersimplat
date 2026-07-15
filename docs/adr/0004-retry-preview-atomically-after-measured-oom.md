# Retry a preview atomically after measured GPU out-of-memory

Only a real `torch.OutOfMemoryError` may lower the generated-view render resolution. The Companion discards all frames, contributor summaries, and mask work from the failed configuration, then retries the complete preview from the Anchor at 1008, 768, and finally 512 pixels under a new render-configuration version. Other failures, or OOM at 512, fail safely without publishing a partial Frame Set, Mask Set, Coverage Report, or Evidence Snapshot.
