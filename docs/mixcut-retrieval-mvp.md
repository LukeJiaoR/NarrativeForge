# Mixcut retrieval MVP

This feature-branch experiment improves ordered stock-footage retrieval without adding a new external model.

## Pipeline

1. Keep the LLM-generated/manual ordered visual intents.
2. Infer a shared scene context when multiple intents support the same location family.
3. Expand each intent into up to three stock-search queries:
   - context-anchored query
   - original visual intent
   - noun-focused fallback
4. Search each query through the existing provider/cache layer.
5. Reject only obvious scene conflicts when descriptive public source-page metadata is available.
6. Interleave candidates from the query variants so a broad provider result list cannot dominate.
7. Preserve `visual_intent`, `query_variant`, and `metadata_relevance_score` in downloaded-material trace records.

For the convenience-store test case, a broad intent such as `customer choosing hot food` becomes `convenience store hot food` while retaining the original and `hot food` as fallback queries.

This is intentionally a lexical retrieval baseline. If real-video evaluation still shows material drift, the next step is visual-semantic reranking (for example CLIP/Marengo) rather than adding more prompt heuristics.
