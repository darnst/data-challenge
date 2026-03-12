"""Data model for enriched stage output - unified model aligned with Airtable."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from data_pipeline.models.common.jurisdiction_slugs import JurisdictionSlug

LegalActType = Literal[
    "regulation",
    "directive",
    "decision",
    "law",
    "declaration",
    "recommendation",
    "treaty",
    "commission_proposal",
    "announcement",  # DE: Bekanntmachung
    "statute",  # DE: Satzung
    "administrative_regulation",  # DE: Verwaltungsvorschrift
    "other",
]

# ELI type (EUR-Lex) to LegalAct.type. Used when building from extraction or when
# type is missing but eliType is set (e.g. build_enriched_document from cache).
ELI_TYPE_TO_LEGAL_ACT_TYPE: dict[str, LegalActType] = {
    "reg": "regulation",
    "reg_impl": "regulation",
    "reg_del": "regulation",
    "dir": "directive",
    "dir_impl": "directive",
    "dir_del": "directive",
    "dec": "decision",
    "dec_impl": "decision",
    "dec_del": "decision",
    "joint_dec": "decision",
    "reco": "recommendation",
    "opin": "recommendation",
    "treaty": "treaty",
    "res": "other",
    "bdg": "other",
    "other": "other",
}


def type_from_eli_type(eli_type: Optional[str]) -> Optional[LegalActType]:
    """Derive LegalAct.type from eli_type (e.g. from EUR-Lex ELI URI). Returns None if eli_type empty."""
    if not eli_type or not isinstance(eli_type, str):
        return None
    key = eli_type.strip().lower()
    return ELI_TYPE_TO_LEGAL_ACT_TYPE.get(key, "other")


class LegalAct(BaseModel):
    """Legal act model aligned with Airtable legalAct table.
    
    This model contains only the fields that are actually loaded to Airtable.
    It unifies data from all jurisdictions (EU, DE, NL) into a common structure.
    
    Note: Text fields (url, title, title_short, summary, abbreviation) are stored
    in the legalActText table for multi-language support (3NF normalization).
    They are included here temporarily for extraction/enrichment pipeline but
    will be saved to legalActText during Airtable loading.
    """
    
    document_id: str = Field(
        description="Identifier of the legal act. For EU: CELEX Code (e.g., '32012L0019'). "
        "For DE: BJNR Code (e.g., 'BJNR158210009'). For NL: BWB ID (e.g., 'BWBR0032735')."
    )
    
    # Text fields - stored in legalActText table for multi-language support
    # Kept here for extraction pipeline, mapped to text table during Airtable save
    url: Optional[str] = Field(
        default=None,
        description="URL of the legal act"
    )

    canonical_source_url: Optional[str] = Field(
        default=None,
        description="Canonical machine-readable source URL (e.g., XML/JSON/API endpoint)"
    )

    fallback_text_url: Optional[str] = Field(
        default=None,
        description="Optional fallback text URL (typically alternate language from legalActText)."
    )

    fallback_text_url_secondary: Optional[str] = Field(
        default=None,
        description="Optional second fallback text URL from legalActText."
    )

    ris_stammfassung: Optional[str] = Field(
        default=None,
        description="AT-specific RIS Stammfassung reference (StF), e.g. 'BGBl. I Nr. 53/1997'."
    )
    
    title: Optional[str] = Field(
        default=None,
        description="Title of the legal act (full title)"
    )
    
    title_short: Optional[str] = Field(
        default=None,
        description="Short title of the legal act"
    )

    summary: Optional[str] = Field(
        default=None,
        description="Summary of the legal act with focus on what changes are introduced by the act for companies"
    )
    
    abbreviation: Optional[str] = Field(
        default=None,
        description="Abbreviation of the legal act"
    )
    
    # Language of the text fields (ISO 639-1 code)
    language: Optional[str] = Field(
        default=None,
        description="Language of the text fields (ISO 639-1 code, e.g., 'de', 'en')"
    )
    
    is_in_force: bool = Field(
        default=True,
        description="Whether the legal act is in force"
    )
    
    is_consolidated_act: bool = Field(
        default=False,
        description="Whether this act is a consolidated version (e.g., BJNR acts, EU sector-0 CELEX)"
    )
    
    type: Optional[LegalActType] = Field(
        default=None,
        description="Type of the legal act in English. Only predefined types are allowed."
    )
    
    jurisdiction: JurisdictionSlug = Field(
        description="Jurisdiction of the legal act"
    )
    
    enactment_date: Optional[str] = Field(
        default=None,
        description="Date of enactment of the legal act (ISO format: YYYY-MM-DD)"
    )
    
    entry_into_force_date: Optional[str] = Field(
        default=None,
        description="Date of entry into force of the legal act (ISO format: YYYY-MM-DD)"
    )
    
    last_amendment_date: Optional[str] = Field(
        default=None,
        description="Date of the last amendment of the legal act (ISO format: YYYY-MM-DD)"
    )
    
    validity_date: Optional[str] = Field(
        default=None,
        description="Date of the validity of the legal act (ISO format: YYYY-MM-DD)."
    )
    
    eurovoc: Optional[List[str]] = Field(
        default=None,
        description="EuroVoc descriptors as list of labels for Airtable Multiselect (EU only)"
    )
    
    eurlex_types: Optional[List[str]] = Field(
        default=None,
        description="All types from EUR-Lex API (from WORK/TYPE fields). Multiselect field in Airtable."
    )
    
    eli_type: Optional[str] = Field(
        default=None,
        description="ELI type from extraction (e.g., 'reg', 'reg_impl', 'dec_impl', 'dir_del'). Single-select field in Airtable."
    )
    
    publication_date: Optional[str] = Field(
        default=None,
        description="Date when the document was published in the Official Journal (ISO format: YYYY-MM-DD). "
        "This can differ significantly from the enactment/document date."
    )
    
    gii_slug: Optional[str] = Field(
        default=None,
        description="GII (Gesetze im Internet) slug for German legal acts (e.g., 'bimschg', 'elektrog_2015'). "
        "Used for BJNR ↔ Slug mapping. Only applicable for jurisdiction='de'."
    )

    entity_type: Optional[Literal["legal_act", "consolidated_act"]] = Field(
        default="legal_act",
        description="Distinguishes regular legal acts from consolidated versions. "
        "Set to 'consolidated_act' when saving a consolidated version of a legal act."
    )

    consolidated_date: Optional[str] = Field(
        default=None,
        description="Stand/version date for consolidated acts (ISO format: YYYY-MM-DD). "
        "Only relevant when entity_type='consolidated_act'."
    )

    consolidated_act_status: Optional[Literal["pending", "extracting", "extracted", "published"]] = Field(
        default=None,
        description="Processing status for consolidated acts. "
        "Only relevant when entity_type='consolidated_act'."
    )


class ConcernedSubdivision(BaseModel):
    """Represents a section affected by a legal act relation along with its comment."""
    
    subdivision_concerned: str = Field(
        description="The specific section affected in the target document. "
        "Examples: 'Article 16', 'Article 5 paragraph 2', 'Paragraph 12a', 'Annex III'"
    )
    
    comment: Optional[str] = Field(
        default=None,
        description="Comment describing the type of change for this section. "
        "Examples: 'Replacement', 'Addition', 'Deletion'"
    )


class LegalActRelation(BaseModel):
    """Legal act relation model aligned with Airtable legalActRelation table.
    
    Represents a relationship between two legal acts.
    """
    
    source_document_id: str = Field(
        description="Document ID of the act that is doing the amending/repealing/replacing. "
        "For EU: CELEX code (e.g., '32023L1234'). For DE: BJNR code (e.g., 'BJNR158210009'). "
        "For NL: BWB ID (e.g., 'BWBR0032735')."
    )
    
    target_document_id: str = Field(
        description="Document ID of the act being affected (typically the anchor act). "
        "For EU: CELEX code. For DE: BJNR code. For NL: BWB ID."
    )
    
    relation_type: str = Field(
        description="Type of relationship between the acts (raw from extraction). "
        "Examples: 'amends', 'amended_by', 'repeals', 'repealed_by', 'replaces', 'replaced_by', "
        "'implements', 'implemented_by', 'based_on', 'consolidated_based_on', 'corrects', etc."
    )
    
    concerned_sections: Optional[List[ConcernedSubdivision]] = Field(
        default=None,
        description="List of subdivisions affected in the target document, each with its comment. "
        "If None or empty, the entire document is affected."
    )


class EnrichedDocument(BaseModel):
    """Enriched document model containing legal act and its relations.
    
    This model represents the final enriched output that will be loaded to Airtable.
    It contains only the data that actually goes to Airtable (legalAct and legalActRelation tables).
    """
    
    legal_act: LegalAct = Field(
        description="The legal act data aligned with Airtable legalAct table"
    )
    
    legal_act_relations: Optional[List[LegalActRelation]] = Field(
        default=None,
        description="List of relationships this act has with other acts. "
        "Aligned with Airtable legalActRelation table."
    )
