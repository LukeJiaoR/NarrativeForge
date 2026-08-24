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
    normalized_terms = [" ".join(_words(term)) for term in search_terms if str(term).strip()]
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
