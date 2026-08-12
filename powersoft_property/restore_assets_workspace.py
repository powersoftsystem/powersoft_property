"""
Put the Assets workspace back to stock ERPNext.

Property navigation was bolted onto Assets before the module had a home-screen
tile of its own. Now that it does, the extra header, shortcut and two cards are
duplicate navigation competing with the real thing.

This is a SITE cleanup, not a package change: workspace.json ships only the six
property workspaces, so no customer ever received these blocks.

Connections on the Asset record are untouched on purpose. They show which
project and property an asset became, on the document you are already looking
at - that is context, not navigation.
"""

import json

import frappe

BLOCK_IDS = ["ppLnkH", "ppLnkS", "phLnkS", "ppCardMgmt", "ppCardRep"]
SHORTCUT_LABELS = ["Powersoft Property", "Hotel PMS", "Property Management"]
CARD_LABELS = ["Property Management", "Property Reports"]


def run():
    if not frappe.db.exists("Workspace", "Assets"):
        print("No Assets workspace on this site.")
        return

    ws = frappe.get_doc("Workspace", "Assets")
    notes = []

    blocks = json.loads(ws.content or "[]")
    kept = [b for b in blocks if b.get("id") not in BLOCK_IDS]
    if len(kept) != len(blocks):
        ws.content = json.dumps(kept)
        notes.append("{0} block(s)".format(len(blocks) - len(kept)))

    before = len(ws.shortcuts)
    ws.shortcuts = [r for r in ws.shortcuts if r.label not in SHORTCUT_LABELS]
    if len(ws.shortcuts) != before:
        notes.append("{0} shortcut(s)".format(before - len(ws.shortcuts)))

    # A card is a "Card Break" row plus every link row that follows it until
    # the next Card Break. Dropping only the break would orphan its links.
    kept_links, dropping, dropped = [], False, 0
    for row in ws.links:
        if row.type == "Card Break":
            dropping = row.label in CARD_LABELS
            if dropping:
                dropped += 1
                continue
        elif dropping:
            dropped += 1
            continue
        kept_links.append(row)

    if dropped:
        ws.links = kept_links
        notes.append("{0} link row(s)".format(dropped))

    if not notes:
        print("Assets is already stock.")
        return

    ws.flags.ignore_permissions = True
    ws.flags.ignore_links = True
    ws.save()
    frappe.db.commit()
    frappe.clear_cache()
    print("ASSETS CLEANED: " + ", ".join(notes))
