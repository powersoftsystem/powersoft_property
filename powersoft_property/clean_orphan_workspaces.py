import json

import frappe

KEEP = [
    "Powersoft Property", "Property Setup", "Property Leasing",
    "Property Sales", "Property Billing", "Property Facilities",
]


def run():
    names = frappe.get_all(
        "Workspace",
        filters={"module": "Custom", "name": ["not in", KEEP]},
        pluck="name",
    )
    if not names:
        print("Nothing to do.")
        return

    backup = [frappe.get_doc("Workspace", n).as_dict() for n in names]
    path = frappe.get_site_path("private", "files", "orphan_workspaces_backup.json")
    with open(path, "w") as fh:
        json.dump(backup, fh, indent=2, default=str)
    print("Backed up {0} to {1}".format(len(backup), path))

    done = []
    for n in names:
        try:
            frappe.delete_doc("Workspace", n, force=True, ignore_permissions=True)
            done.append(n)
        except Exception:
            print("  [skipped] {0}".format(n))
    frappe.db.commit()
    frappe.clear_cache()
    print("DELETED {0}: {1}".format(len(done), ", ".join(done)))
