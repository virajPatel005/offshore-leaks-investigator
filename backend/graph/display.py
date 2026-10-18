"""Display helper: a hub with no name still needs a readable label.

Checked against the live graphs: degree-heavy Address rows can have no name,
and "None" must never leak into hub lists, notes or the UI. One shared format
keeps tools, notes and the UI consistent: 'unnamed <label> (id, degree N)'.
"""


def display_name(name, labels, node_id, degree_core=None):
    """The name, or the documented placeholder for a nameless node."""
    if name:
        return name
    label = "+".join(labels or []) or "node"
    deg = f", degree {degree_core}" if degree_core is not None else ""
    return f"unnamed {label} ({node_id}{deg})"
