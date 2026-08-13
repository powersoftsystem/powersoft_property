import frappe

CHECKS = [
    ("DocType", "doctype.json"),
    ("Client Script", "client_script.json"),
    ("Print Format", "print_format.json"),
    ("Report", "report.json"),
    ("Number Card", "number_card.json"),
    ("Dashboard Chart", "dashboard_chart.json"),
    ("Dashboard", "dashboard.json"),
]

def run():
    for dt, _f in CHECKS:
        if not frappe.db.has_column(dt, "module"):
            print("{0}: no module column".format(dt)); continue
        total = frappe.db.count(dt)
        ours = frappe.db.count(dt, {"module": "Powersoft Property"})
        blank = frappe.db.sql(
            "select count(*) from `tab{0}` where ifnull(module,'')=''".format(dt))[0][0]
        print("{0}: module=PowersoftProperty {1} | module BLANK {2} | total {3}".format(
            dt, ours, blank, total))
