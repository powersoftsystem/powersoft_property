"""
Check that what the app SHIPS matches what actually exists.

Written after the worst bug of the build. hooks.py exported Custom Fields with
["module", "=", "Powersoft Property"], but fields added through the desk UI keep
module = NULL. The filter matched 2 of 130. Sales Invoice shipped with ZERO
custom fields, so ps_lease_agreement did not exist on a customer's site, Create
Rent Invoice could not link an invoice to its lease, and the rent schedule never
moved off "Not Invoiced".

Nothing looked wrong. install-app returned 0. The desk loaded. Every record
count matched. It only surfaced when someone actually invoiced a lease.

Run this before every release:

    bench --site <demo-site> execute powersoft_property.fixture_audit.run

Any line marked MISSING means the fixture filter is dropping records that exist
on the source site. Investigate before shipping.
"""

import json
import os

import frappe

# fixture file -> (doctype, filter describing what SHOULD ship)
EXPECTED = {
    "custom_field.json": ("Custom Field", {
        "fieldname": ["in", ["property", "property_unit",
                             "ps_lease_agreement", "ps_schedule_row"]],
        "dt": ["not in", [
            "Loan", "Loan Demand", "Loan Disbursement", "Loan Interest Accrual",
            "Loan Refund", "Loan Repayment", "Leave Encashment", "Payroll Entry",
            "Expense Claim", "Expense Claim Detail", "Expense Taxes and Charges",
        ]],
    }),
    "doctype.json": ("DocType", {"module": "Powersoft Property"}),
    "report.json": ("Report", {"module": "Powersoft Property", "disabled": 0}),
    "print_format.json": ("Print Format", {"module": "Powersoft Property"}),
    "dashboard_chart.json": ("Dashboard Chart", {"module": "Powersoft Property"}),
}


def run():
    base = os.path.join(os.path.dirname(__file__), "fixtures")
    problems = 0

    for fname, (doctype, filters) in EXPECTED.items():
        path = os.path.join(base, fname)
        shipped = 0
        if os.path.exists(path):
            with open(path) as fh:
                try:
                    shipped = len(json.load(fh))
                except ValueError:
                    shipped = -1

        actual = frappe.db.count(doctype, filters)
        flag = "ok" if shipped >= actual else "MISSING {0}".format(actual - shipped)
        if shipped < actual:
            problems += 1
        print("{0:24} shipped {1:4}  on this site {2:4}  {3}".format(
            fname, shipped, actual, flag))

    # The specific field whose absence broke everything.
    critical = frappe.db.exists("Custom Field", {"dt": "Sales Invoice",
                                                 "fieldname": "ps_lease_agreement"})
    print("\nSales Invoice.ps_lease_agreement present: {0}".format(
        "yes" if critical else "NO - the rent chain cannot work"))

    print("\n{0}".format("AUDIT CLEAN" if not problems and critical
                         else "AUDIT FOUND PROBLEMS - do not release"))
