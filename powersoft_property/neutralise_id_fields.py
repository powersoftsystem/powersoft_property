"""
Two Ghana-specific things baked into the DocTypes themselves.

1. A field labelled "TIN / Ghana Card No". The field holds a tax or national
   identity number - a universal idea. Only the label was local.

2. A Select listing "Ghana Card" as its first identity-document option. A
   customer outside Ghana cannot pick their own, and cannot edit a Select that
   ships in the app without customising the DocType.

Both become neutral. Existing records keep their values: renaming a label does
not touch data, and "Ghana Card" is replaced by "National ID" in the option
list rather than the list being rebuilt, so anything already saved as
"Ghana Card" is migrated by the caller if needed.
"""

import frappe

LABEL_SWAPS = [
    ("TIN / Ghana Card No", "Tax ID / National ID"),
    ("TIN / Ghana Card", "Tax ID / National ID"),
    ("Ghana Card No", "National ID No"),
    ("Ghana Card", "National ID"),
]


def run():
    touched = []

    for dt_name in frappe.get_all(
        "DocType", filters={"module": "Powersoft Property"}, pluck="name"
    ):
        doc = frappe.get_doc("DocType", dt_name)
        changed = False

        for field in doc.fields:
            if field.label:
                new_label = field.label
                for old, new in LABEL_SWAPS:
                    new_label = new_label.replace(old, new)
                if new_label != field.label:
                    touched.append("{0}.{1} label -> {2}".format(
                        dt_name, field.fieldname, new_label))
                    field.label = new_label
                    changed = True

            if field.fieldtype == "Select" and field.options and "Ghana Card" in field.options:
                lines = field.options.split("\n")
                lines = ["National ID" if l.strip() == "Ghana Card" else l for l in lines]
                # Do not leave a duplicate if National ID was already an option.
                seen, deduped = set(), []
                for l in lines:
                    key = l.strip()
                    if key and key in seen:
                        continue
                    seen.add(key)
                    deduped.append(l)
                field.options = "\n".join(deduped)
                touched.append("{0}.{1} options -> Ghana Card replaced".format(
                    dt_name, field.fieldname))
                changed = True

        if changed:
            doc.flags.ignore_permissions = True
            doc.save()

    frappe.db.commit()
    frappe.clear_cache()

    print("ID FIELDS CHANGED: {0}".format(len(touched)))
    for line in touched:
        print("  " + line)
