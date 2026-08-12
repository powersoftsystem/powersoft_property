"""
A print format printed "TIN / Ghana Card No:" next to the customer's tax id.

That is a document the customer sends to THEIR customers. A landlord in Lagos
or Manchester does not have a Ghana Card. The field itself is fine - it is
Customer.tax_id, which every country uses - only the label was local.
"""

import frappe

SWAPS = [
    ("TIN / Ghana Card No:", "Tax ID:"),
    ("TIN / Ghana Card No.", "Tax ID"),
    ("TIN / Ghana Card No", "Tax ID"),
    ("Ghana Card No:", "ID No:"),
    ("Ghana Card No", "ID No"),
]


def run():
    changed = []
    for name in frappe.get_all(
        "Print Format", filters={"module": "Powersoft Property"}, pluck="name"
    ):
        doc = frappe.get_doc("Print Format", name)
        before = doc.html or ""
        after = before
        for old, new in SWAPS:
            after = after.replace(old, new)

        if after != before:
            doc.html = after
            doc.flags.ignore_permissions = True
            doc.save()
            changed.append(name)

    frappe.db.commit()
    frappe.clear_cache()
    print("PRINT FORMATS CHANGED: {0}".format(", ".join(changed) or "none"))
