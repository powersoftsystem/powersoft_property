"""
Two pieces of demo residue that would follow the app to every customer.

1. The Powersoft Property workspace carries a "United Kingdom" header and two
   number cards, "Units (secondary)" and "Vacant Units (secondary)". Those exist
   because the demo runs a second UK company. A customer in Accra or Lagos gets
   a section headed United Kingdom reading zero.

2. The Assets workspace carries a "Hotel PMS" shortcut next to the Powersoft
   Property one. On a property-only site that is a dead link.

Blocks are removed by id, and the matching child-table rows are removed too -
the workspace renderer reads the content JSON, but a stale shortcut or card row
left in the child table still shows in the sidebar.
"""

import json

import frappe

# Blocks to drop from the Powersoft Property workspace content.
UK_BLOCK_IDS = ["ppHdrUK", "ppNc5", "ppNc6"]
UK_CARD_NAMES = ["Units (secondary)", "Vacant Units (secondary)"]

# Block to drop from the Assets workspace content.
HOTEL_BLOCK_IDS = ["phLnkS"]
HOTEL_SHORTCUT_LABELS = ["Hotel PMS"]


def run():
    changed = []
    changed += _strip("Powersoft Property", UK_BLOCK_IDS,
                      card_names=UK_CARD_NAMES)
    changed += _strip("Assets", HOTEL_BLOCK_IDS,
                      shortcut_labels=HOTEL_SHORTCUT_LABELS)

    frappe.db.commit()
    frappe.clear_cache()

    if changed:
        print("CHANGED: " + "; ".join(changed))
    else:
        print("CHANGED: nothing (already clean)")


def _strip(ws_name, block_ids, card_names=None, shortcut_labels=None):
    if not frappe.db.exists("Workspace", ws_name):
        return ["{0}: not on this site".format(ws_name)]

    ws = frappe.get_doc("Workspace", ws_name)
    notes = []

    try:
        blocks = json.loads(ws.content or "[]")
    except ValueError:
        return ["{0}: content is not valid JSON, left alone".format(ws_name)]

    kept = [b for b in blocks if b.get("id") not in block_ids]
    removed = len(blocks) - len(kept)
    if removed:
        ws.content = json.dumps(kept)
        notes.append("{0}: {1} block(s)".format(ws_name, removed))

    if card_names:
        before = len(ws.number_cards)
        ws.number_cards = [
            r for r in ws.number_cards if r.number_card_name not in card_names
        ]
        if len(ws.number_cards) != before:
            notes.append("{0}: {1} card row(s)".format(
                ws_name, before - len(ws.number_cards)))

    if shortcut_labels:
        before = len(ws.shortcuts)
        ws.shortcuts = [
            r for r in ws.shortcuts if r.label not in shortcut_labels
        ]
        if len(ws.shortcuts) != before:
            notes.append("{0}: {1} shortcut row(s)".format(
                ws_name, before - len(ws.shortcuts)))

    if notes:
        ws.flags.ignore_permissions = True
        ws.save()

    return notes


# ---------------------------------------------------------------------------
# Dead links
#
# Saving the Assets workspace on the test site failed with
#
#     LinkValidationError: Could not find Row #29: Link To: Rent Roll
#     (list view), Row #30: Link To: Tenant Arrears (list view)
#
# Those two are DISABLED reports. The fixture filter is
# [["module","=","Powersoft Property"],["disabled","=",0]], so they never ship -
# but a workspace linking to them does. On the demo the link validates because
# the report exists there, disabled or not. On a customer site it does not
# exist at all, and the workspace cannot be saved.
#
# This drops link rows whose target is genuinely missing, and reports them.
# ---------------------------------------------------------------------------

PROPERTY_WORKSPACES = [
    "Powersoft Property", "Property Setup", "Property Leasing",
    "Property Sales", "Property Billing", "Property Facilities", "Assets",
]


def prune_dead_links():
    total = 0
    for ws_name in PROPERTY_WORKSPACES:
        if not frappe.db.exists("Workspace", ws_name):
            continue

        ws = frappe.get_doc("Workspace", ws_name)
        keep, dropped = [], []

        for row in ws.links:
            target, dt = row.link_to, row.link_type
            if not target or not dt:
                keep.append(row)
                continue
            if frappe.db.exists(dt, target):
                keep.append(row)
            else:
                dropped.append("{0} -> {1} ({2})".format(ws_name, target, dt))

        if dropped:
            ws.links = keep
            ws.flags.ignore_permissions = True
            ws.flags.ignore_links = True
            ws.save()
            total += len(dropped)
            for line in dropped:
                print("  dropped: " + line)

    frappe.db.commit()
    frappe.clear_cache()
    print("DEAD LINKS DROPPED: {0}".format(total))


def prune_unshipped_report_links():
    """
    Drop workspace links pointing at reports the app does not ship.

    The Report fixture filter excludes disabled reports. On the demo those
    reports still exist, so the links validate and the problem is invisible.
    On a customer site the target is absent and you get seven broken links,
    plus a workspace that refuses to save. Fix it where the fixtures are
    exported from, not just on the site where it was noticed.
    """
    excluded = frappe.get_all(
        "Report", filters={"disabled": 1}, pluck="name"
    )
    print("Reports not shipped (disabled): {0}".format(", ".join(excluded) or "none"))

    total = 0
    for ws_name in PROPERTY_WORKSPACES:
        if not frappe.db.exists("Workspace", ws_name):
            continue

        ws = frappe.get_doc("Workspace", ws_name)
        keep, dropped = [], []

        for row in ws.links:
            if row.link_type == "Report" and row.link_to in excluded:
                dropped.append("{0} -> {1}".format(ws_name, row.link_to))
            else:
                keep.append(row)

        if dropped:
            ws.links = keep
            ws.flags.ignore_permissions = True
            ws.flags.ignore_links = True
            ws.save()
            total += len(dropped)
            for line in dropped:
                print("  dropped: " + line)

    frappe.db.commit()
    frappe.clear_cache()
    print("UNSHIPPED REPORT LINKS DROPPED: {0}".format(total))
