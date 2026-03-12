"""Jurisdiction slugs for legal acts and frameworks. Single source of truth for allowed values.

Values are lowercase ISO-style codes (e.g. gb for Great Britain, not uk).

Also defines the central mapping: jurisdiction → content language (ISO code) for framework/
version text. All flows and the framework version generator must use jurisdiction_to_content_language()
so content language is consistent and extensible (e.g. add NL→nl later).
"""

from typing import List, Literal, TypedDict, Union


class JurisdictionLanguagePolicy(TypedDict):
    source_text_language: str
    generation_language: str
    default_translation_target: str

# -----------------------------------------------------------------------------
# Jurisdiction → language policy (single source of truth)
# -----------------------------------------------------------------------------
# Current policy:
# - de/at/ch/be/ie/nl/norms/other => generated in de, translated to en
# - eu and all remaining jurisdictions => generated in en, translated to de
# -----------------------------------------------------------------------------
JURISDICTION_LANGUAGE_POLICY: dict[str, JurisdictionLanguagePolicy] = {
    "de": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "at": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "ch": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "be": {
        "source_text_language": "fr",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "ie": {
        "source_text_language": "en",
        "generation_language": "en",
        "default_translation_target": "de",
    },
    "nl": {
        "source_text_language": "nl",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "norms": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_norms": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "other": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_bw": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_by": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_be": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_bb": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_hb": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_hh": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_he": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_mv": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_ni": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_nw": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_rp": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_sl": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_sn": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_st": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_sh": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "de_th": {
        "source_text_language": "de",
        "generation_language": "de",
        "default_translation_target": "en",
    },
    "eu": {
        "source_text_language": "en",
        "generation_language": "en",
        "default_translation_target": "de",
    },
    "it": {
        "source_text_language": "it",
        "generation_language": "en",
        "default_translation_target": "de",
    },
    "es": {
        "source_text_language": "es",
        "generation_language": "en",
        "default_translation_target": "de",
    },
    "gb": {
        "source_text_language": "en",
        "generation_language": "en",
        "default_translation_target": "de",
    },
    "us": {
        "source_text_language": "en",
        "generation_language": "en",
        "default_translation_target": "de",
    },
}

DEFAULT_LANGUAGE_POLICY: JurisdictionLanguagePolicy = {
    "source_text_language": "en",
    "generation_language": "en",
    "default_translation_target": "de",
}

# Backward-compatible alias for existing callers.
JURISDICTION_TO_CONTENT_LANGUAGE: dict[str, str] = {
    key: policy["generation_language"]
    for key, policy in JURISDICTION_LANGUAGE_POLICY.items()
}


def _normalize_jurisdiction(jurisdiction: Union[str, List[str], None]) -> str:
    if jurisdiction is None:
        return ""
    primary = (
        jurisdiction[0] if isinstance(jurisdiction, list) and jurisdiction else jurisdiction
    )
    if not primary:
        return ""
    return str(primary).strip().lower()


def _policy_for_jurisdiction(
    jurisdiction: Union[str, List[str], None],
) -> JurisdictionLanguagePolicy:
    key = _normalize_jurisdiction(jurisdiction)
    return JURISDICTION_LANGUAGE_POLICY.get(key, DEFAULT_LANGUAGE_POLICY)


def jurisdiction_to_content_language(jurisdiction: Union[str, List[str], None]) -> str:
    """Return the ISO content language code for framework/version text for this jurisdiction.

    Single source of truth: all flows and generate_framework_version must use this.
    - DE, AT, CH, other → "de"
    - Everything else → "en"

    Extend JURISDICTION_TO_CONTENT_LANGUAGE to add more jurisdictions or languages (e.g. "nl" → "nl").

    Args:
        jurisdiction: Jurisdiction slug or list of slugs (e.g. from legal_framework.jurisdiction).
                     If list, the first element is used.

    Returns:
        ISO language code, e.g. "de" or "en".
    """
    return _policy_for_jurisdiction(jurisdiction)["generation_language"]


def jurisdiction_to_source_text_language(jurisdiction: Union[str, List[str], None]) -> str:
    """Return the source text language for enrichment/import by jurisdiction."""
    return _policy_for_jurisdiction(jurisdiction)["source_text_language"]


def jurisdiction_to_generation_language(jurisdiction: Union[str, List[str], None]) -> str:
    """Return the initial generation language for LLM output by jurisdiction."""
    return _policy_for_jurisdiction(jurisdiction)["generation_language"]


def jurisdiction_to_default_translation_target(
    jurisdiction: Union[str, List[str], None],
) -> str:
    """Return the default target language used for post-generation translation."""
    return _policy_for_jurisdiction(jurisdiction)["default_translation_target"]


def translation_pair_for_jurisdiction(
    jurisdiction: Union[str, List[str], None],
) -> tuple[str, str]:
    """Return `(source_language, target_language)` for translation by jurisdiction."""
    policy = _policy_for_jurisdiction(jurisdiction)
    return policy["generation_language"], policy["default_translation_target"]


def translation_pair_for_content_language(content_language: str) -> tuple[str, str]:
    """Return translation pair from known content language (de<->en default)."""
    src = (content_language or "").strip().lower()
    if src == "de":
        return "de", "en"
    return "en", "de"

# Allowed jurisdiction values. Pipeline and NocoDB/API use these only.
JURISDICTION_SLUGS = (
    "de",
    "fr",
    "it",
    "es",
    "nl",
    "be",
    "at",
    "pl",
    "cz",
    "hu",
    "ro",
    "se",
    "dk",
    "ie",
    "gb",
    "ch",
    "no",
    "tr",
    "us",
    "ca",
    "mx",
    "br",
    "cn",
    "in",
    "jp",
    "kr",
    "vn",
    "eu",
    "de_norms",
    "de_bw",
    "de_by",
    "de_be",
    "de_bb",
    "de_hb",
    "de_hh",
    "de_he",
    "de_mv",
    "de_ni",
    "de_nw",
    "de_rp",
    "de_sl",
    "de_sn",
    "de_st",
    "de_sh",
    "de_th",
    "other",
)

JurisdictionSlug = Literal[
    "de",
    "fr",
    "it",
    "es",
    "nl",
    "be",
    "at",
    "pl",
    "cz",
    "hu",
    "ro",
    "se",
    "dk",
    "ie",
    "gb",
    "ch",
    "no",
    "tr",
    "us",
    "ca",
    "mx",
    "br",
    "cn",
    "in",
    "jp",
    "kr",
    "vn",
    "eu",
    "de_norms",
    "de_bw",
    "de_by",
    "de_be",
    "de_bb",
    "de_hb",
    "de_hh",
    "de_he",
    "de_mv",
    "de_ni",
    "de_nw",
    "de_rp",
    "de_sl",
    "de_sn",
    "de_st",
    "de_sh",
    "de_th",
    "other",
]
