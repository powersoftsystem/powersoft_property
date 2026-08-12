"""
Desktop Icons left behind by apps that are no longer installed.

The tiles on /desk do not come only from Workspaces. Frappe also ships a legacy
`Desktop Icon` table, and the desk home merges it in via frappe.boot.desktop_icons.

Deleting the orphan Workspaces removed the hotel pages but NOT these, which is
why "Company Switch", "Mining Support" and "Powersoft Suite" survived a full
uninstall and reinstall - they were never part of any app being installed.

An icon whose `app` is blank belongs to nothing. Every legitimate icon on a
site carries frappe, erpnext or the app that created it.
"""

import json

import frappe


def run():
    rows = frappe.db.sql(
        """
        select name, label, ifnull(app, '') as app
        from `tabDesktop Icon`
        where ifnull(app, '') = ''
        order by name
        """,
        as_dict=True,
    )

    if not rows:
        print("Nothing to do - every desktop icon belongs to an installed app.")
        return

    path = frappe.get_site_path("private", "files", "orphan_desktop_icons_backup.json")
    with open(path, "w") as fh:
        json.dump(
            [frappe.get_doc("Desktop Icon", r.name).as_dict() for r in rows],
            fh, indent=2, default=str,
        )
    print("Backed up {0} icon(s) to {1}".format(len(rows), path))

    deleted = []
    for r in rows:
        try:
            frappe.delete_doc("Desktop Icon", r.name, force=True,
                              ignore_permissions=True, ignore_missing=True)
            deleted.append(r.label or r.name)
        except Exception:
            print("  [skipped] {0}".format(r.name))

    frappe.db.commit()
    frappe.clear_cache()

    print("DELETED {0}: {1}".format(len(deleted), ", ".join(deleted)))
