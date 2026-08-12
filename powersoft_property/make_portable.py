"""Strip the last country-specific things out of the module, on the demo site.

A fixture sweep found three things that would follow the app to a customer:
  1. a Select field holding Ghana's regions, hardcoded into the DocType
  2. portal pages naming the demo company and city, and falling back to 'GHS'
  3. workspace shortcuts pinning company to PS Realty Ghana Ltd

Safe to run twice.
"""

import json

import frappe

WORKSPACES = [
    "Powersoft Property", "Property Setup", "Property Leasing",
    "Property Sales", "Property Billing", "Property Facilities",
]

PORTAL_ROUTES = ["properties", "my-tenancy", "my-invoices", "my-requests"]

TEXT_SWAPS = [
    ("across Greater Accra &mdash; managed and let by PS Realty Ghana Ltd.",
     "&mdash; managed and let by our team."),
    ("Managed by <b>PS Realty Ghana Ltd</b>, Accra.", "Managed by the letting office."),
    ("Managed by <b>PS Realty Ghana Ltd</b>, Accra", "Managed by the letting office"),
    ("PS Realty Ghana Ltd", "the letting office"),
    ("Greater Accra", ""),
]

CURRENCY_FALLBACKS = [
    ("lease.currency or 'GHS'", "lease.currency or _dcur"),
    ("cur='GHS'", "cur=_dcur"),
    ("cur = 'GHS'", "cur = _dcur"),
    ("or 'GHS'", "or _dcur"),
]

PREAMBLE = (
    "{%- set _co = frappe.get_all('Company', fields=['default_currency'], limit_page_length=1) -%}\n"
    "{%- set _dcur = _co[0].default_currency if _co else '' -%}\n"
)


def run():
    f = _regions()
    p = _pages()
    s = _shortcuts()
    frappe.db.commit()
    frappe.clear_cache()
    print("\nRegion fields converted: %s" % f)
    print("Portal pages cleaned:    %s" % p)
    print("Shortcuts cleaned:       %s" % s)
    _report()


def _regions():
    n = 0
    for dt in frappe.get_all("DocType", filters={"module": "Powersoft Property"}, pluck="name"):
        doc = frappe.get_doc("DocType", dt)
        hit = False
        for fld in doc.fields:
            if fld.fieldtype == "Select" and fld.options and "Greater Accra" in fld.options:
                fld.fieldtype = "Data"
                fld.options = ""
                hit = True
                n += 1
                print("%s.%s: Select (Ghana regions) -> Data" % (dt, fld.fieldname))
        if hit:
            doc.flags.ignore_permissions = True
            doc.save()
    return n


def _pages():
    n = 0
    for name in frappe.get_all("Web Page", filters={"route": ["in", PORTAL_ROUTES]}, pluck="name"):
        pg = frappe.get_doc("Web Page", name)
        before = pg.main_section_html or ""
        after = before
        for old, new in TEXT_SWAPS:
            after = after.replace(old, new)
        need = False
        for old, new in CURRENCY_FALLBACKS:
            if old in after:
                after = after.replace(old, new)
                need = True
        if need and "_dcur =" not in after:
            after = PREAMBLE + after
        if after != before:
            pg.main_section_html = after
            pg.flags.ignore_permissions = True
            pg.save()
            n += 1
            print("Portal page cleaned: %s (/%s)" % (name, pg.route))
    return n


def _shortcuts():
    n = 0
    for ws_name in frappe.get_all("Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"):
        ws = frappe.get_doc("Workspace", ws_name)
        hit = False
        for row in ws.shortcuts:
            if not row.stats_filter:
                continue
            try:
                parsed = json.loads(row.stats_filter)
            except ValueError:
                continue
            if not isinstance(parsed, dict) or "company" not in parsed:
                continue
            parsed.pop("company")
            row.stats_filter = json.dumps(parsed)
            hit = True
            n += 1
            print("%s: company removed from '%s'" % (ws_name, row.label))
        if hit:
            ws.flags.ignore_permissions = True
            ws.save()
    return n


def _report():
    bad = []
    for name in frappe.get_all("Web Page", filters={"route": ["in", PORTAL_ROUTES]}, pluck="name"):
        blob = frappe.db.get_value("Web Page", name, "main_section_html") or ""
        hits = [t for t in ("PS Realty", "Accra", "'GHS'") if t in blob]
        if hits:
            bad.append("Web Page %s: %s" % (name, ", ".join(hits)))
    for ws_name in frappe.get_all("Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"):
        for row in frappe.get_doc("Workspace", ws_name).shortcuts:
            if row.stats_filter and "PS Realty" in row.stats_filter:
                bad.append("Shortcut %s/%s" % (ws_name, row.label))
    if bad:
        print("\nStill company-specific:")
        for b in bad:
            print("  " + b)
    else:
        print("\nClean. Portal pages and shortcuts carry no company, city or currency.")


# ---------------------------------------------------------------------------
# Second pass, found by grepping the exported fixtures.
# ---------------------------------------------------------------------------

DEFAULT_TOKENS = ("Accra", "Greater Accra", "Ghana")


def run2():
    d = _clear_field_defaults()
    s = _drop_company_depends_on()
    frappe.db.commit()
    frappe.clear_cache()
    print("\nField defaults cleared:   %s" % d)
    print("Property Setters removed: %s" % s)


def _clear_field_defaults():
    """A field defaulting to 'Accra' or 'Greater Accra' pre-fills a Ghanaian
    city on every record a customer creates, anywhere in the world."""
    n = 0
    for dt in frappe.get_all("DocType", filters={"module": "Powersoft Property"}, pluck="name"):
        doc = frappe.get_doc("DocType", dt)
        hit = False
        for fld in doc.fields:
            if fld.default and fld.default in DEFAULT_TOKENS:
                print("%s.%s: default '%s' cleared" % (dt, fld.fieldname, fld.default))
                fld.default = ""
                hit = True
                n += 1
        if hit:
            doc.flags.ignore_permissions = True
            doc.save()
    return n


def _drop_company_depends_on():
    """These hide the property fields on Sales Invoice for companies outside a
    hardcoded list of three. The intent is fine; the list is not portable. With
    the setter gone the fields simply show, which is right on a customer site."""
    n = 0
    rows = frappe.get_all(
        "Property Setter",
        filters={"doc_type": "Sales Invoice", "property": "depends_on"},
        fields=["name", "field_name", "value"],
    )
    for row in rows:
        if not row.value or "PS Realty" not in row.value:
            continue
        frappe.delete_doc("Property Setter", row.name, force=True, ignore_permissions=True)
        print("Removed depends_on setter: Sales Invoice.%s" % row.field_name)
        n += 1
    return n


# ---------------------------------------------------------------------------
# Repair. run2() deleted more than it should have: its filter matched every
# depends_on setter on Sales Invoice mentioning the three companies, which
# included ten belonging to the healthcare and lending apps. Only the two
# property ones were meant to go. This puts the other ten back exactly as they
# were. They never shipped anyway - hooks.py exports Sales Invoice setters by
# field name, and none of these are in that list.
# ---------------------------------------------------------------------------

NOT_OURS = [
    "patient_payable_amount", "total_insurance_coverage_amount", "service_unit",
    "ref_practitioner", "patient_name", "patient", "value_date",
    "loan_repayment", "loan_disbursement", "loan",
]

DEPENDS_ON_VALUE = (
    'eval:["PS Realty Ghana Ltd","PS Realty UK Ltd","PS Realty Group"]'
    '.indexOf(doc.company) === -1'
)


def restore():
    n = 0
    for fieldname in NOT_OURS:
        exists = frappe.db.exists("Property Setter", {
            "doc_type": "Sales Invoice",
            "field_name": fieldname,
            "property": "depends_on",
        })
        if exists:
            print("Already present: Sales Invoice.%s" % fieldname)
            continue
        doc = frappe.new_doc("Property Setter")
        doc.doctype_or_field = "DocField"
        doc.doc_type = "Sales Invoice"
        doc.field_name = fieldname
        doc.property = "depends_on"
        doc.property_type = "Text"
        doc.value = DEPENDS_ON_VALUE
        doc.flags.ignore_permissions = True
        doc.insert()
        print("Restored: Sales Invoice.%s" % fieldname)
        n += 1
    frappe.db.commit()
    frappe.clear_cache()
    print("\nRestored %s setter(s) belonging to other apps." % n)
    print("Sales Invoice.property and .property_unit stay removed - those were ours.")
