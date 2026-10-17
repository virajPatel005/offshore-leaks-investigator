"""Soft (possible-match) relationship types.

Soft edges link records that look like the same person/company/address but are
not a confirmed identity (D6). Every tool traverses them by default, so any
result whose path or neighbour edges include one must say so: the envelope
carries includes_possible_match + the distinct soft rel_types.
"""
SOFT_REL_TYPES = frozenset({
    "similar", "same_as", "underlying",
    "same_name_as", "same_id_as", "same_company_as", "probably_same_officer_as",
})


def possible_matches(edges):
    """Sorted soft rel_types found in an iterable of edge dicts."""
    kinds = {e.get("rel_type") for e in edges if e.get("rel_type") in SOFT_REL_TYPES}
    return sorted(kinds)
