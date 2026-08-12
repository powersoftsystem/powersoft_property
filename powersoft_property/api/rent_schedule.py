"""
Rent schedule write-back.

Keeps the rent schedule on a PS Lease Agreement in step with the Sales Invoices
and Payment Entries raised against it:

    invoice submitted  -> row marked Invoiced, invoice linked
    payment received   -> row marked Paid (or Partly Paid), amount and date set
    payment cancelled  -> row reverts to Invoiced / Overdue
    invoice cancelled  -> row released so the period can be re-invoiced

CURRENTLY INACTIVE. The live logic is still the five Server Script records,
which ship as fixtures. To switch over: uncomment doc_events in hooks.py and
delete those five Server Script records — otherwise the logic runs twice.

Why this exists rather than staying as Server Scripts
-----------------------------------------------------
Server Scripts run in Frappe's restricted sandbox, where `import`, `frappe.call`,
`flt`, `getdate` and even `abs` are unavailable, and function definitions cannot
see injected globals. That forced some ugly workarounds. None of those limits
apply here.

One non-obvious thing worth keeping in mind
-------------------------------------------
ERPNext updates `Sales Invoice.outstanding_amount` with a direct database write
when a Payment Entry is submitted. It does NOT re-save the invoice. So hooking
Sales Invoice save events will never see a payment land. The payment must be
caught on the Payment Entry itself. That is why `on_payment_submit` exists.
"""

import frappe
from frappe.utils import flt, getdate, nowdate

BILLED_STATES = ("Invoiced", "Partly Paid", "Paid", "Overdue")
STOPPED_STATES = ("Paid", "Waived")


# ---------------------------------------------------------------------------
# Sales Invoice
# ---------------------------------------------------------------------------

def on_invoice_submit(doc, method=None):
    """Mark the matching rent schedule row as Invoiced and link the invoice."""
    lease_name = doc.get("ps_lease_agreement")
    if not lease_name:
        return

    lease = frappe.get_doc("PS Lease Agreement", lease_name)
    row = _find_target_row(lease, doc)

    if row:
        row.db_set("sales_invoice", doc.name, update_modified=False)
        row.db_set("invoice_status", "Invoiced", update_modified=False)

    _recompute_lease_totals(lease_name)


def on_invoice_cancel(doc, method=None):
    """Release the period so it can be invoiced again."""
    lease_name = doc.get("ps_lease_agreement")
    if not lease_name:
        return

    lease = frappe.get_doc("PS Lease Agreement", lease_name)

    for row in lease.rent_schedule:
        if row.sales_invoice != doc.name:
            continue

        status = "Not Invoiced"
        if row.due_date and getdate(row.due_date) < getdate(nowdate()):
            status = "Overdue"

        row.db_set("sales_invoice", None, update_modified=False)
        row.db_set("invoice_status", status, update_modified=False)
        row.db_set("amount_paid", 0, update_modified=False)
        row.db_set("balance", flt(row.total_due), update_modified=False)
        row.db_set("paid_on", None, update_modified=False)
        break

    _recompute_lease_totals(lease_name)


# ---------------------------------------------------------------------------
# Payment Entry
# ---------------------------------------------------------------------------

def on_payment_submit(doc, method=None):
    _sync_from_payment(doc)


def on_payment_cancel(doc, method=None):
    # Same logic: re-read each invoice's outstanding and restate the row.
    # On cancel the outstanding has gone back up, so the row correctly
    # reverts to Invoiced or Overdue.
    _sync_from_payment(doc)


def _sync_from_payment(payment):
    """Restate every rent schedule row touched by this payment."""
    touched = set()

    for ref in payment.references:
        if ref.reference_doctype != "Sales Invoice" or not ref.reference_name:
            continue

        invoice = frappe.get_doc("Sales Invoice", ref.reference_name)
        lease_name = invoice.get("ps_lease_agreement")
        if not lease_name:
            continue

        _restate_row(lease_name, invoice, payment.posting_date)
        touched.add(lease_name)

    for lease_name in touched:
        _recompute_lease_totals(lease_name)


def _restate_row(lease_name, invoice, paid_on):
    total = flt(invoice.grand_total)
    outstanding = flt(invoice.outstanding_amount)
    settled = max(total - outstanding, 0.0)

    if outstanding <= 0.005:
        status = "Paid"
    elif settled > 0.005:
        status = "Partly Paid"
    else:
        status = "Invoiced"
        if invoice.due_date and getdate(invoice.due_date) < getdate(nowdate()):
            status = "Overdue"

    lease = frappe.get_doc("PS Lease Agreement", lease_name)

    for row in lease.rent_schedule:
        if row.sales_invoice != invoice.name:
            continue

        row.db_set("invoice_status", status, update_modified=False)
        row.db_set("amount_paid", settled, update_modified=False)
        row.db_set("balance", flt(row.total_due) - settled, update_modified=False)

        if status == "Paid":
            if not row.paid_on:
                row.db_set("paid_on", paid_on or nowdate(), update_modified=False)
        else:
            row.db_set("paid_on", None, update_modified=False)
        break


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_target_row(lease, invoice):
    """
    Work out which schedule row this invoice settles.

    Three passes, most specific first. The client script stamps
    `ps_schedule_row` when it builds the invoice, so pass one almost always
    wins. The fallbacks exist for invoices raised by hand.
    """
    row_name = invoice.get("ps_schedule_row")

    if row_name:
        for row in lease.rent_schedule:
            if row.name == row_name:
                return row

    # Unbilled row whose total matches the invoice exactly.
    for row in lease.rent_schedule:
        if not row.sales_invoice and abs(flt(row.total_due) - flt(invoice.grand_total)) < 0.01:
            return row

    # Oldest unbilled row. Arrears first — a row that is past due is marked
    # Overdue, not "Not Invoiced", so both must be considered here.
    candidates = [
        r for r in lease.rent_schedule
        if not r.sales_invoice and r.invoice_status in ("Not Invoiced", "Overdue")
    ]
    candidates.sort(key=lambda r: r.due_date or "9999-12-31")

    return candidates[0] if candidates else None


def _recompute_lease_totals(lease_name):
    """
    Restate total_invoiced / total_paid / outstanding_balance from the schedule.

    A row counts as invoiced if it carries an invoice OR its status says it was
    billed. That second condition matters on migrated data, where rows may be
    marked Paid without an invoice ever having existed. Without it the header
    understates and the outstanding balance goes negative.
    """
    lease = frappe.get_doc("PS Lease Agreement", lease_name)

    invoiced = 0.0
    paid = 0.0

    for row in lease.rent_schedule:
        if row.sales_invoice or row.invoice_status in BILLED_STATES:
            invoiced += flt(row.total_due)
        paid += flt(row.amount_paid)

    balance = max(invoiced - paid, 0.0)

    frappe.db.set_value(
        "PS Lease Agreement",
        lease_name,
        {
            "total_invoiced": invoiced,
            "total_paid": paid,
            "outstanding_balance": balance,
        },
        update_modified=False,
    )
