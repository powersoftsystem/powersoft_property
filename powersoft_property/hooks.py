from . import __version__ as app_version

app_name = "powersoft_property"
# The product name. Deliberately NOT the same as the desk tile label below,
# which stays short so it does not wrap to three lines beside Accounting
# and Selling. Also NOT the same as the Module Def, which every DocType,
# report and card is bound to - renaming that would rewrite the module
# reference on all of them for a cosmetic gain.
app_title = "Powersoft Property Management"
app_publisher = "Powersoft Systems"
app_description = "Property management for ERPNext"
app_email = "info@powersoftsystem.com"
app_license = "GPL-3.0"
required_apps = ["erpnext"]

after_install = "powersoft_property.install.after_install"
after_migrate = "powersoft_property.install.after_migrate"

# Last line of defence. See ensure_cards_scoped for why login is the only
# moment that is guaranteed to run without a worker and without a command.
on_session_creation = "powersoft_property.install.ensure_cards_scoped"

# The dashboard cards carry a company filter that cannot be expressed as a
# fixture. These events are the moments that answer changes, so the app keeps
# itself correct instead of asking the installer to remember a command.
doc_events = {
    "Company": {
        "after_insert": "powersoft_property.install.refresh_card_scope",
    },
    "PS Property": {
        "after_insert": "powersoft_property.install.refresh_card_scope",
        "on_trash": "powersoft_property.install.refresh_card_scope",
    },
}

# ---------------------------------------------------------------------------
# DESK HOME SCREEN
#
# Without this the module is reachable only by searching for its workspace,
# which is how a customer concludes the app "is not really there". This puts
# Powersoft Property on the apps screen as its own tile, alongside Accounting
# and Selling, pointing straight at the landing workspace.
#
# The logo lives in powersoft_property/public/images/ and is only served after
# `bench build`. A broken image on the tile means that step was skipped.
# ---------------------------------------------------------------------------

add_to_apps_screen = [
    {
        "name": "powersoft_property",
        "title": "Property Management",
        "logo": "/assets/powersoft_property/images/powersoft-property-logo.svg",
        "route": "/app/powersoft-property",
    }
]


# ---------------------------------------------------------------------------
# FIXTURES
#
# Export:  bench --site <demo-site> export-fixtures --app powersoft_property
# Import:  bench --site <customer-site> migrate
#
# ORDER MATTERS. DocType must come first. If migrate fails on a link error, run
# migrate a second time; the first pass creates what the second needs.
#
# NOTHING IN HERE MAY BE COUNTRY OR COMPANY SPECIFIC. Every filter was checked
# by grepping the exported JSON for PS Realty, PRG, PRUK, Accra, GHS, GBP, the
# demo property names, the office phone number and the Powersoft email address.
# ---------------------------------------------------------------------------

fixtures = [

    {"dt": "DocType", "filters": [["module", "=", "Powersoft Property"]]},

    {
        # DO NOT filter these by module. Custom Fields added through the desk UI
        # keep module = NULL, so ["module","=","Powersoft Property"] matched 2 of
        # 130 and the app shipped almost none of its own fields. Sales Invoice got
        # ZERO - no ps_lease_agreement, no ps_schedule_row - so Create Rent Invoice
        # could not link an invoice to its lease and the rent schedule never
        # updated. The install looked perfectly healthy. Same trap as the
        # Workspace export.
        #
        # Filter by fieldname instead. Only four belong to this app, and they are
        # specific enough not to collide.
        #
        # The dt exclusions matter just as much: `property` also sits on Loan and
        # on HR doctypes belonging to other apps on the build bench. Shipping a
        # Custom Field whose target DocType does not exist on the customer's site
        # fails the import outright.
        "dt": "Custom Field",
        "filters": [
            ["fieldname", "in", [
                "property", "property_unit",
                "ps_lease_agreement", "ps_schedule_row",
            ]],
            ["dt", "not in", [
                "Loan", "Loan Demand", "Loan Disbursement",
                "Loan Interest Accrual", "Loan Refund", "Loan Repayment",
                "Leave Encashment", "Payroll Entry",
                "Expense Claim", "Expense Claim Detail",
                "Expense Taxes and Charges",
            ]],
        ],
    },

    # Property Setters.
    #
    # NOTE ON Sales Invoice. Matching that doctype wholesale swept in setters
    # belonging to the healthcare and lending apps - depends_on rules on
    # patient, ref_practitioner, loan, loan_repayment and others, each reading
    #
    #   eval:["PS Realty Ghana Ltd","PS Realty UK Ltd","PS Realty Group"]
    #        .indexOf(doc.company) === -1
    #
    # Three demo company names, applied to a customer's Sales Invoice, from
    # apps with nothing to do with property. So invoices are matched by field.
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

    # Land Tenure Type and Title Document Type ship whole. Their entries are
    # common-law terms used across many jurisdictions - Leasehold, Freehold,
    # Crown Land, Commonhold, Customary Tenure, Deed of Assignment - so a
    # customer anywhere finds what fits and ignores the rest.
    {"dt": "Land Tenure Type"},
    {"dt": "Title Document Type"},

    # "Ghana Card" is the one genuinely country-specific master. It stays on the
    # demo, where it is correct and in use on real tenant records, but it does
    # not ship. "National Identity Number" covers the same idea for everyone.
    {
        "dt": "Identification Type",
        "filters": [["name", "not in", ["Ghana Card"]]],
    },

    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Property Manager", "Property Accountant", "Leasing Agent",
            "Facilities Manager", "Maintenance Manager",
        ]]],
    },

    {
        # By name, not by module. Only "Create Rent Invoice" happened to have a
        # module set; the two Currency Cascade scripts were created through the
        # desk UI and left it blank, so they never shipped.
        #
        # The "Company Filter" and "Company Currency Price List" scripts are
        # deliberately NOT here. They are demo-bench conveniences for showing two
        # companies side by side, and mean nothing on a customer site.
        "dt": "Client Script",
        "filters": [["name", "in", [
            "PS Lease Agreement - Create Rent Invoice",
            "PS Lease Agreement - Currency Cascade",
            "Property Sale Contract - Currency Cascade",
        ]]],
    },

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

    # "Units (secondary)" and "Vacant Units (secondary)" count the demo's SECOND
    # company, which exists only so the demo can show two currencies side by
    # side. On a customer site they read zero under a heading that means
    # nothing. They stay on the demo; they just do not ship.
    {"dt": "Number Card", "filters": [
        ["module", "=", "Powersoft Property"],
        ["name", "not in", ["Units (secondary)", "Vacant Units (secondary)"]],
    ]},
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
