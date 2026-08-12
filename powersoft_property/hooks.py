from . import __version__ as app_version

app_name = "powersoft_property"
app_title = "Powersoft Property"
app_publisher = "Powersoft Systems"
app_description = "Property management for ERPNext"
app_email = "info@powersoftsystem.com"
app_license = "GPL-3.0"
required_apps = ["erpnext"]

after_install = "powersoft_property.install.after_install"

# ---------------------------------------------------------------------------
# FIXTURES
#
# Export:  bench --site <demo-site> export-fixtures --app powersoft_property
# Import:  bench --site <customer-site> migrate
#
# ORDER MATTERS. DocType must come first. If migrate fails on a link error, run
# migrate a second time; the first pass creates what the second needs.
#
# NOTHING IN HERE MAY BE COMPANY-SPECIFIC. Every filter was checked against the
# exported JSON to make sure it does not carry a company, currency or property
# name into a customer's database.
# ---------------------------------------------------------------------------

fixtures = [

    {"dt": "DocType", "filters": [["module", "=", "Powersoft Property"]]},

    {"dt": "Custom Field", "filters": [["module", "=", "Powersoft Property"]]},

    # Property Setters.
    #
    # NOTE ON Sales Invoice. Matching that doctype wholesale swept in setters
    # belonging to the healthcare app - depends_on rules on
    # total_insurance_coverage_amount and patient_payable_amount reading
    #
    #   eval:["PS Realty Ghana Ltd","PS Realty UK Ltd","PS Realty Group"]
    #        .indexOf(doc.company) === -1
    #
    # Three demo company names, applied to a customer's Sales Invoice, from an
    # app with nothing to do with property. So invoices are matched by field.
    {
        "dt": "Property Setter",
        "filters": [["doc_type", "in", [
            "PS Lease Agreement", "PS Rent Schedule Item", "PS Lease Charge Item",
            "Property Unit", "PS Property", "Property Sale Contract",
            "Sale Instalment Item", "Asset", "Customer", "Supplier",
        ]]],
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["doc_type", "in", ["Sales Invoice", "Purchase Invoice"]],
            ["field_name", "in", [
                "property", "property_unit", "ps_lease_agreement", "ps_schedule_row",
            ]],
        ],
    },

    # Masters.
    #
    # Property Region is deliberately NOT shipped. On the demo it holds Ghana's
    # regions - records that mean nothing to a customer in Lagos or Manchester
    # and would have to be deleted by hand. The field is a plain Link, so an
    # empty table is the right starting point.
    {"dt": "Property Type"},
    {"dt": "Unit Type"},
    {"dt": "Land Tenure Type"},
    {"dt": "Title Document Type"},
    {"dt": "Identification Type"},

    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Property Manager", "Property Accountant", "Leasing Agent",
            "Facilities Manager", "Maintenance Manager",
        ]]],
    },

    {"dt": "Client Script", "filters": [["module", "=", "Powersoft Property"]]},

    # The rent schedule write-back. "PS One Off Data Repair" is excluded on
    # purpose - a scratch script that must never reach a customer site.
    {
        "dt": "Server Script",
        "filters": [["name", "in", [
            "PS Rent Schedule Writeback",
            "PS Rent Schedule Payment Sync",
            "PS Rent Schedule Release On Cancel",
            "PS Rent Payment Sync On Payment",
            "PS Rent Payment Sync On Payment Cancel",
        ]]],
    },

    {"dt": "Print Format", "filters": [["module", "=", "Powersoft Property"]]},

    {
        "dt": "Report",
        "filters": [
            ["module", "=", "Powersoft Property"],
            ["disabled", "=", 0],
        ],
    },

    {"dt": "Number Card", "filters": [["module", "=", "Powersoft Property"]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "Powersoft Property"]]},
    {"dt": "Dashboard", "filters": [["module", "=", "Powersoft Property"]]},
    {"dt": "Custom HTML Block", "filters": [["name", "in", ["Property Hero"]]]},

    # WATCH THIS ONE. The six property workspaces were built through the desk
    # UI, which leaves module blank - filtering on module exports NOTHING and
    # the customer gets an app with no navigation at all. Filter by name.
    {
        "dt": "Workspace",
        "filters": [["name", "in", [
            "Powersoft Property",
            "Property Setup",
            "Property Leasing",
            "Property Sales",
            "Property Billing",
            "Property Facilities",
        ]]],
    },

    {
        "dt": "Workflow State",
        "filters": [["name", "in", ["Draft", "Pending Approval", "Approved", "Rejected"]]],
    },
    {
        "dt": "Workflow Action Master",
        "filters": [["name", "in", ["Submit for Approval", "Approve", "Reject"]]],
    },
    {
        "dt": "Workflow",
        "filters": [["document_type", "in", ["Property Sale Contract", "Maintenance Job Card"]]],
    },

    # Tenant portal and public listings.
    #
    # WARNING: these templates reference /files/*.svg images that will not exist
    # on a fresh site. Ship the images in public/ or the panels render empty.
    {
        "dt": "Web Page",
        "filters": [["route", "in", ["properties", "my-tenancy", "my-invoices", "my-requests"]]],
    },
    {"dt": "Web Form", "filters": [["route", "in", ["report-a-problem"]]]},
]
