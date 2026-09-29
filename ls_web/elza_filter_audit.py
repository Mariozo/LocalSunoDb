"""Bounded read-only Filter UX Audit snapshot for LS Elza.

The snapshot exposes only the known filter contract and UI/filter relationships.
It does not execute arbitrary source reads and never changes files or data.
"""

FILTER_UX_AUDIT_VERSION = 1


def run_filter_ux_audit():
    return {
        "audit_version": FILTER_UX_AUDIT_VERSION,
        "read_only": True,
        "scope": "LocalSunoDb filter system",
        "current_visible_controls": [
            {
                "id": "workspace",
                "label": "Workspace",
                "kind": "multi",
                "semantics": "Filter by one or more Workspace names.",
            },
            {
                "id": "local_family_filter",
                "label": "Local family",
                "kind": "multi",
                "semantics": "Confirmed Track ID -> Local Family assignments only.",
            },
            {
                "id": "category_filter",
                "label": "Category",
                "kind": "multi",
                "semantics": "Song / Instrumental and other canonical categories.",
            },
            {
                "id": "local_audio_filter",
                "label": "Audio",
                "kind": "single",
                "semantics": (
                    "Presence/absence of linked local main audio; "
                    "not Suno WAV availability."
                ),
            },
            {
                "id": "kind_filter",
                "label": "Type",
                "kind": "single",
                "semantics": (
                    "One LS type/filter dimension. Some special states such as "
                    "Liked or Has Stems are represented in this dimension, so "
                    "they cannot all be combined through the ordinary Type selector."
                ),
            },
            {
                "id": "sort",
                "label": "Sort",
                "kind": "sort",
                "semantics": "Title / Created / Duration sorting; not a filter.",
            },
        ],
        "query_dimensions": [
            {
                "id": "q",
                "label": "Search text",
                "fields": ["name", "lyrics", "prompt"],
                "note": (
                    "Field toggles determine which searchable text columns "
                    "participate."
                ),
            },
            {
                "id": "style_q",
                "label": "Style search",
                "fields": ["style_tags"],
            },
            {
                "id": "search_fields",
                "label": "Search field toggles",
                "values": ["name", "lyrics", "prompt", "marks", "tags"],
            },
            {
                "id": "flags",
                "label": "Flags 1-5",
                "semantics": (
                    "Five independent user flags. Selecting several numbered "
                    "Flags means all selected flags are required."
                ),
            },
            {
                "id": "tags",
                "label": "Tags",
                "semantics": (
                    "User tag filter; distinct from free-text tag searching."
                ),
            },
            {
                "id": "track_ids",
                "label": "Exact Track IDs",
                "semantics": (
                    "Exact result-set representation used by Elza for "
                    "combinations the normal Library controls cannot express directly."
                ),
            },
        ],
        "elza_semantic_dimensions": [
            {
                "id": "wav_scope",
                "states": ["all", "local"],
                "semantics": {
                    "all": "WAV available from Suno OR already present locally.",
                    "local": "Already linked local WAV only.",
                },
            },
            {
                "id": "ui_type",
                "semantics": (
                    "Positive or negative visible Type badge matching, "
                    "e.g. Upload / bez Upload."
                ),
            },
            {
                "id": "minimum_flag_count",
                "semantics": (
                    "At least N of the five independent Flags; "
                    "not the same as numbered Flag N."
                ),
            },
            {
                "id": "exact_flags",
                "semantics": "Exactly the requested active Flag set.",
            },
            {
                "id": "local_family_assigned",
                "states": ["assigned", "not_assigned"],
                "semantics": (
                    "LocF assignment state, distinct from the Latvian word "
                    "'vietējais'."
                ),
            },
            {
                "id": "text_fields",
                "values": ["name", "track_id", "lyrics", "prompt", "tags"],
                "semantics": (
                    "Exact text-field targeting, including Anywhere = all five fields."
                ),
            },
        ],
        "known_interaction_constraints": [
            (
                "Unqualified WAV and Local WAV are different: WAV means "
                "Suno + Local; Local WAV means linked local WAV only."
            ),
            (
                "Upload is a Type identity derived from canonical source/type data; "
                "it is not the same dimension as Song/Instrumental category."
            ),
            (
                "Flag 3 means the specific third Flag; 'vismaz 3 ✶' means any three "
                "or more active Flags."
            ),
            (
                "The ordinary Type selector is single-valued, while Elza can create "
                "exact Track ID views for combinations that exceed that UI dimension."
            ),
            (
                "Saved Views can persist reusable ordinary filters and exact "
                "track_ids views."
            ),
            "LocF and local audio are different concepts and must not be merged.",
        ],
        "audit_requirements": [
            "Inventory every user-facing filter dimension.",
            "Separate filters from sort and search-field controls.",
            "Identify duplicate or overlapping controls.",
            "Identify dimensions whose UI labels hide materially different semantics.",
            "Identify combinations that the normal UI cannot express but Elza can.",
            "Propose Quick filters, More filters, and Elza-only advanced selections.",
            (
                "Preserve existing selection capability; do not recommend removing "
                "a capability without a replacement."
            ),
            "Give 10-20 representative selection examples and the intended semantics.",
            "List migration/regression risks. Do not modify code or data.",
        ],
    }


__all__ = ["FILTER_UX_AUDIT_VERSION", "run_filter_ux_audit"]
