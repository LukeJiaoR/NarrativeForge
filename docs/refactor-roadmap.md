# NarrativeForge Refactor Roadmap

## Problem statement

Media generation pipelines often look deterministic while hiding low-confidence guesses.
Two failures are especially costly:

1. A speech provider returns audio without word or sentence boundaries, so a renderer
   distributes subtitle duration by character count and presents the estimate as truth.
2. A stock-media provider receives ambiguous proper nouns as plain search strings, so a
   product, person, material, food, animal, or place is retrieved under the wrong meaning.

NarrativeForge will make uncertainty explicit and keep evidence for every decision.

## Target pipeline

```text
narrative
  -> beat plan
  -> shot intents
  -> retrieval queries
  -> candidate evidence
  -> selected assets
  -> speech
  -> aligned transcript
  -> timeline
  -> render
  -> post-render QA
```

Every arrow should produce a versioned artifact that can be inspected and resumed.

## 1. Structured visual intent

Replace `list[str]` search terms with a schema such as:

```json
{
  "beat_id": "beat-003",
  "narration": "A team validates a large migration with automated tests.",
  "visible_subjects": ["software engineers", "test dashboard"],
  "actions": ["reviewing failures", "running automated tests"],
  "environment": "engineering workspace",
  "mood": "focused",
  "queries": [
    "engineers reviewing test dashboard",
    "automated software testing team"
  ],
  "avoid": ["food", "animals", "rusted metal"]
}
```

The `avoid` values are generated from context, not from a domain-specific hard-coded list.
For example, an ambiguous word is disambiguated by its surrounding entity type and the
intended visible action.

## 2. Candidate retrieval and evidence

Retrieval should fan out across providers and retain:

- provider and asset identifier
- original query and normalized intent
- title, tags, creator, and source URL
- sampled frames or provider thumbnails
- lexical, embedding, and optional vision-language scores
- rejection reason and fallback decision

A candidate must not enter the timeline merely because it was returned first.

## 3. Subtitle timing contracts

Every TTS adapter should declare one of:

- `word_boundaries`
- `sentence_boundaries`
- `audio_only`

`audio_only` must trigger alignment from the final audio. Character-proportional timing
may be exposed only as an explicit low-quality preview mode and must never masquerade as
precise timing.

The alignment artifact should retain:

- original script
- raw ASR transcript
- corrected display text
- word and sentence timestamps
- model, language confidence, and timing confidence

## 4. Agent tool contracts

Each stage should be:

- idempotent for the same input hash
- resumable after interruption
- explicit about network, credentials, and paid-provider usage
- able to stop at an artifact boundary
- able to return warnings without silently degrading quality

Suggested tools:

- `plan_narrative`
- `plan_visuals`
- `retrieve_candidates`
- `review_candidates`
- `synthesize_speech`
- `align_transcript`
- `compose_timeline`
- `render_media`
- `verify_render`

## 5. Quality gates

Pre-render gates:

- missing or weak visual matches
- repeated footage
- unlicensed or untraceable assets
- subtitle overlap and out-of-range cues
- unsafe layout regions

Post-render gates:

- stream, codec, resolution, and duration checks
- black frames, frozen sections, and long silence
- rendered speech continuity
- subtitle readability
- visual/narrative spot checks

## Migration phases

### Phase A — Stabilize contracts

- Introduce structured artifacts alongside existing parameters.
- Add capability declarations to TTS adapters.
- Keep existing WebUI and API behavior through compatibility adapters.

### Phase B — Replace retrieval

- Add ambiguity-aware query planning.
- Store candidate metadata and rejection receipts.
- Add optional embedding and vision-language ranking.

### Phase C — Rebuild orchestration

- Move pipeline stages behind idempotent agent tools.
- Persist stage hashes, versions, warnings, and resumable state.
- Separate orchestration from provider implementations.

### Phase D — Harden rendering

- Add preflight, render manifests, and post-render QA.
- Make all silent quality fallbacks visible to agents and users.
