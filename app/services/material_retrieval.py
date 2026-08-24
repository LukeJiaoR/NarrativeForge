"""Lightweight, dependency-free retrieval planning for mixcut stock footage.

The stock providers are lexical search engines, not script-understanding systems. A
narration beat such as ``customer choosing hot food`` is often too broad when the
whole video is about a convenience store. This module infers a shared scene anchor
from the ordered visual intents and expands each intent into a few concrete search
queries while keeping the transformation deterministic and auditable.

This is deliberately a first-stage retrieval planner, not a vision model. Provider
results can still be imperfect; the metadata scoring helpers only reject obvious
scene conflicts when the public source-page slug contains enough information.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from loguru import logger

# People/roles usually help narration but often make stock search unnecessarily
# narrow. They are removed only from fallback variants; the original intent is
# always preserved as one query.
_ACTOR_WORDS = {
    "customer",
    "shopper",
    "commuter",
    "traveler",
    "traveller",
    "tourist",
    "tourists",
    "person",
    "people",
    "man",
    "woman",
    "guest",
}

# Common action words are useful in the original query, but removing them creates a
# noun-focused fallback that stock providers often match more reliably.
_ACTION_WORDS = {
    "entering",
    "browsing",
    "choosing",
    "grabbing",
    "comparing",
    "leaving",
    "walking",
    "buying",
    "shopping",
    "looking",
    "checking",
    "holding",
    "taking",
    "picking",
    "selecting",
    "discovering",
    "finding",
}

_FILLER_WORDS = {"a", "an", "the", "at", "in", "on", "with", "for", "from", "of"}

# More specific phrases come first. We only select a phrase as a shared context when
# its head/location family is supported by multiple intents, preventing a one-off
# location mention from contaminating a multi-location story.
_CONTEXT_PHRASES = (
    "convenience store",
    "grocery store",
    "coffee shop",
    "shopping mall",
    "train station",
    "subway station",
    "airport terminal",
    "hotel room",
    "office building",
    "supermarket",
    "restaurant",
    "cafe",
    "office",
    "school",
    "airport",
    "hotel",
    "store",
    "shop",
    "market",
    "street",
    "beach",
    "factory",
    "farm",
    "gym",
}

_LOCATION_FAMILIES = {
    "store": {"store", "shop", "market", "supermarket", "grocery", "retail", "mall"},
    "restaurant": {"restaurant", "cafe", "dining", "kitchen", "eatery"},
    "office": {"office", "workplace", "workspace"},
    "hotel": {"hotel", "resort", "lobby", "room"},
    "street": {"street", "road", "sidewalk", "outdoor"},
    "beach": {"beach", "ocean", "seaside", "coast"},
    "farm": {"farm", "field", "agriculture", "rural"},
    "gym": {"gym", "fitness", "workout"},
}

_MAX_CANDIDATES_PER_INTENT = 8


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = " ".join(_words(value))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _family_for_text(text: str) -> str | None:
    tokens = set(_words(text))
    for family, family_tokens in _LOCATION_FAMILIES.items():
        if tokens & family_tokens:
            return family
    return None


def infer_shared_context(search_terms: list[str]) -> str:
    """Infer one shared scene anchor supported by multiple ordered intents.

    Example: several terms mention store/shelf/aisle and one explicitly says
    ``convenience store``. The returned anchor is ``convenience store`` so broader
    beats can be searched as ``convenience store hot food`` instead of ``hot food``.
    """
    normalized_terms = [
        " ".join(_words(term)) for term in search_terms if str(term).strip()
    ]
    if len(normalized_terms) < 2:
        return ""

    family_counts: dict[str, int] = {}
    for term in normalized_terms:
        family = _family_for_text(term)
        if family:
            family_counts[family] = family_counts.get(family, 0) + 1

    minimum_support = max(2, len(normalized_terms) // 4)
    supported_families = {
        family for family, count in family_counts.items() if count >= minimum_support
    }
    if not supported_families:
        return ""

    for phrase in _CONTEXT_PHRASES:
        family = _family_for_text(phrase)
        if family not in supported_families:
            continue
        if any(phrase in term for term in normalized_terms):
            return phrase
    return ""


def simplify_visual_intent(search_term: str) -> str:
    """Create a noun-focused fallback query while preserving concrete objects."""
    tokens = [
        token
        for token in _words(search_term)
        if token not in _ACTOR_WORDS
        and token not in _ACTION_WORDS
        and token not in _FILLER_WORDS
    ]
    return " ".join(tokens[:6])


def build_search_variants(search_term: str, shared_context: str = "") -> list[str]:
    """Return up to three ordered queries for one visual intent.

    Priority is: context-anchored query, original query, noun-focused fallback.
    The anchored query is intentionally first because preserving the scene is more
    important for mixcut quality than matching a generic action perfectly.
    """
    original = " ".join(_words(search_term))
    if not original:
        return []

    simplified = simplify_visual_intent(original)
    context = " ".join(_words(shared_context))
    variants: list[str] = []

    if context:
        if context in original:
            anchored = original
        else:
            # Remove generic location-family words before attaching the more specific
            # shared context, avoiding queries such as "convenience store store shelf".
            context_family = _family_for_text(context)
            family_tokens = _LOCATION_FAMILIES.get(context_family or "", set())
            content_tokens = [
                token
                for token in _words(simplified or original)
                if token not in family_tokens and token not in _FILLER_WORDS
            ]
            anchored = " ".join((context.split() + content_tokens)[:6])
        variants.append(anchored)

    variants.append(original)
    if simplified:
        variants.append(simplified)
    return _dedupe(variants)[:3]


def source_page_tokens(source_page: str | None) -> set[str]:
    """Extract descriptive tokens from a provider's public source-page slug."""
    if not source_page:
        return set()
    try:
        path = urlsplit(str(source_page)).path
    except ValueError:
        return set()
    return set(_words(path))


def metadata_relevance_score(
    source_page: str | None,
    visual_intent: str,
    shared_context: str = "",
) -> float | None:
    """Score public-page metadata and penalize obvious scene conflicts.

    ``None`` means the provider did not expose enough descriptive metadata, in which
    case callers should keep the candidate rather than pretending we inspected the
    video pixels. Negative scores indicate an explicit location-family conflict.
    """
    metadata = source_page_tokens(source_page)
    if not metadata:
        return None

    desired_tokens = {
        token
        for token in _words(f"{visual_intent} {shared_context}")
        if token not in _ACTOR_WORDS
        and token not in _ACTION_WORDS
        and token not in _FILLER_WORDS
    }
    overlap = len(metadata & desired_tokens)
    score = float(overlap) / max(1, len(desired_tokens))

    desired_family = _family_for_text(shared_context or visual_intent)
    observed_families = {
        family
        for family, family_tokens in _LOCATION_FAMILIES.items()
        if metadata & family_tokens
    }
    if desired_family and observed_families and desired_family not in observed_families:
        score -= 0.75
    elif desired_family and desired_family in observed_families:
        score += 0.35
    return score


def is_obvious_metadata_mismatch(
    source_page: str | None,
    visual_intent: str,
    shared_context: str = "",
) -> bool:
    """Reject only strong metadata conflicts; ambiguous candidates are preserved."""
    score = metadata_relevance_score(source_page, visual_intent, shared_context)
    return score is not None and score < -0.25


def _round_robin_candidates(
    candidate_lists: list[list],
    *,
    global_urls: set[str],
    limit: int = _MAX_CANDIDATES_PER_INTENT,
) -> list:
    """Interleave provider-ranked results so one query variant cannot dominate."""
    result = []
    local_urls: set[str] = set()
    candidate_index = 0
    while len(result) < limit:
        added = False
        for candidates in candidate_lists:
            if candidate_index >= len(candidates):
                continue
            item = candidates[candidate_index]
            if item.url in local_urls or item.url in global_urls:
                continue
            local_urls.add(item.url)
            result.append(item)
            added = True
            if len(result) >= limit:
                break
        if not added and all(candidate_index >= len(items) - 1 for items in candidate_lists):
            break
        candidate_index += 1
    global_urls.update(local_urls)
    return result


def install(material_module) -> None:
    """Install the ordered-retrieval MVP into ``app.services.material``.

    The integration is intentionally isolated on the mixcut feature branch. It wraps
    the existing private ordered downloader instead of replacing provider/cache code,
    so normal random/sequential retrieval stays untouched. Once validated against
    real videos this wrapper can be folded into ``material.py`` directly.
    """
    if getattr(material_module, "_mixcut_retrieval_installed", False):
        return

    original_ordered_download = material_module._download_videos_by_script_order
    original_source_record = material_module._material_source_record

    def source_record_with_retrieval_trace(item, local_path: str):
        record = original_source_record(item, local_path)
        source = item.source_info if isinstance(item.source_info, dict) else {}
        visual_intent = source.get("visual_intent")
        query_variant = source.get("query_variant")
        relevance_score = source.get("metadata_relevance_score")
        if visual_intent:
            record["visual_intent"] = str(visual_intent)
        if query_variant:
            record["query_variant"] = str(query_variant)
        if relevance_score is not None:
            record["metadata_relevance_score"] = float(relevance_score)
        return record

    def enhanced_ordered_download(
        task_id: str,
        search_terms: list[str],
        search_videos,
        video_aspect,
        audio_duration: float,
        max_clip_duration: int,
        material_directory: str,
    ) -> list[str]:
        shared_context = infer_shared_context(search_terms)
        if not shared_context:
            logger.info(
                "mixcut retrieval planner found no stable shared scene context; "
                "using baseline ordered retrieval"
            )
            return original_ordered_download(
                task_id=task_id,
                search_terms=search_terms,
                search_videos=search_videos,
                video_aspect=video_aspect,
                audio_duration=audio_duration,
                max_clip_duration=max_clip_duration,
                material_directory=material_directory,
            )

        logger.info(
            "mixcut retrieval planner enabled: "
            f"shared_context={shared_context!r}, intents={len(search_terms)}"
        )
        candidate_groups = []
        valid_video_urls: set[str] = set()
        found_duration = 0.0

        for visual_intent in search_terms:
            query_variants = build_search_variants(visual_intent, shared_context)
            logger.info(
                f"visual intent {visual_intent!r} expanded to queries: {query_variants}"
            )
            variant_candidates: list[list] = []

            for query_rank, query_variant in enumerate(query_variants):
                video_items = search_videos(
                    search_term=query_variant,
                    minimum_duration=max_clip_duration,
                    video_aspect=video_aspect,
                )
                logger.info(
                    f"found {len(video_items)} videos for expanded query {query_variant!r}"
                )
                accepted = []
                for result_rank, item in enumerate(video_items):
                    source = item.source_info if isinstance(item.source_info, dict) else {}
                    source_page = source.get("source_page")
                    relevance_score = metadata_relevance_score(
                        source_page,
                        visual_intent,
                        shared_context,
                    )
                    if is_obvious_metadata_mismatch(
                        source_page,
                        visual_intent,
                        shared_context,
                    ):
                        logger.info(
                            "rejecting obvious stock scene mismatch: "
                            f"intent={visual_intent!r}, query={query_variant!r}, "
                            f"asset_id={source.get('asset_id') or 'unknown'}, "
                            f"score={relevance_score}"
                        )
                        continue

                    source = dict(source)
                    source["visual_intent"] = visual_intent
                    source["query_variant"] = query_variant
                    source["query_rank"] = query_rank
                    source["provider_result_rank"] = result_rank
                    if relevance_score is not None:
                        source["metadata_relevance_score"] = relevance_score
                    item.source_info = source
                    accepted.append(item)
                variant_candidates.append(accepted)

            intent_items = _round_robin_candidates(
                variant_candidates,
                global_urls=valid_video_urls,
            )
            if intent_items:
                candidate_groups.append((visual_intent, intent_items))
                found_duration += sum(item.duration for item in intent_items)

        if not candidate_groups:
            logger.warning(
                "mixcut retrieval planner produced no usable candidates; "
                "falling back to baseline ordered retrieval"
            )
            return original_ordered_download(
                task_id=task_id,
                search_terms=search_terms,
                search_videos=search_videos,
                video_aspect=video_aspect,
                audio_duration=audio_duration,
                max_clip_duration=max_clip_duration,
                material_directory=material_directory,
            )

        logger.info(
            "mixcut retrieval candidate pool ready: "
            f"candidates={sum(len(items) for _, items in candidate_groups)}, "
            f"required_duration={audio_duration}, found_duration={found_duration}"
        )

        video_paths = []
        material_sources = []
        total_duration = 0.0
        candidate_index = 0
        while candidate_groups and total_duration <= audio_duration:
            has_candidate = False
            for visual_intent, term_items in candidate_groups:
                if candidate_index >= len(term_items):
                    continue

                has_candidate = True
                item = term_items[candidate_index]
                try:
                    source = item.source_info if isinstance(item.source_info, dict) else {}
                    logger.info(
                        "downloading reranked ordered stock video: "
                        f"intent={visual_intent!r}, query={source.get('query_variant')!r}, "
                        f"provider={item.provider}, "
                        f"asset_id={source.get('asset_id') or 'unknown'}"
                    )
                    saved_video_path = material_module.save_video(
                        video_url=item.url,
                        save_dir=material_directory,
                    )
                    if saved_video_path:
                        video_paths.append(saved_video_path)
                        try:
                            material_sources.append(
                                source_record_with_retrieval_trace(item, saved_video_path)
                            )
                        except Exception as source_error:
                            logger.warning(
                                "failed to prepare mixcut material source record: "
                                f"provider={item.provider}, "
                                f"error={type(source_error).__name__}, "
                                f"detail={source_error}"
                            )
                        total_duration += min(max_clip_duration, item.duration)
                        if total_duration > audio_duration:
                            break
                except Exception as exc:
                    logger.error(
                        "failed to download mixcut material video: "
                        f"provider={item.provider}, error={type(exc).__name__}, "
                        f"detail={material_module._redact_request_error(exc, item.url)}"
                    )

            if not has_candidate:
                break
            candidate_index += 1

        logger.success(f"downloaded {len(video_paths)} mixcut ordered videos")
        material_module._persist_material_sources(task_id, material_sources)
        return video_paths

    material_module._material_source_record = source_record_with_retrieval_trace
    material_module._download_videos_by_script_order = enhanced_ordered_download
    material_module._mixcut_retrieval_installed = True
