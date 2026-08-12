from . import __version__ as app_version

app_name = "powersoft_property"
app_title = "Powersoft Property"
app_publisher = "Powersoft Systems"
app_description = "Property management for ERPNext — land, construction, letting, facilities and portals"
app_email = "info@powersoftsystem.com"
app_license = "GPL-3.0"
required_apps = ["erpnext"]

after_install = "powersoft_property.install.after_install"

# ---------------------------------------------------------------------------
# FIXTURES
#
# Everything built on the demo site is data, and fixtures are how Frappe ships
# data. Export with:
#
#     bench --site <demo-site> export-fixtures --app powersoft_property
#
# Import happens automatically on:
#
#     bench --site <customer-site> migrate
#
# ORDER MATTERS. Frappe imports fixtures in the order listed below. DocType must
# come first — everything else references it. If migrate fails on a link error,
# run migrate a second time; the first pass creates what the second needs.
#
# NOTHING IN HERE MAY BE COMPANY-SPECIFIC. Every filter below was checked
# against the demo site to make sure it does not carry "PS Realty Ghana Ltd",
# a GHS currency filter, or a hardcoded list of property names into a
# customer's database.
# ---------------------------------------------------------------------------

fixtures = [

    # 1. The custom DocTypes. This is the big one.
    {
        "dt": "DocType",
        "filters": [["module", "=", "Powersoft Property"]],
    },

    # 2. Fields added to standard doctypes — property / property_unit on Sales
    #    Invoice, Purchase Invoice, Journal Entry, Payment Entry, Asset, and the
    #    ps_lease_agreement / ps_schedule_row pair that drives the write-back.
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Powersoft Property"]],
    },

    # 3. Tweaks to existing fields — allow_on_submit on the rent schedule,
    #    currency options on child tables, ignore_user_permissions.
    {
        "dt": "Property Setter",
        "filters": [["doc_type", "in", [
            "PS Lease Agreement", "PS Rent Schedule Item", "PS Lease Charge Item",
            "Property Unit", "PS Property", "Property Sale Contract",
            "Sale Instalment Item", "Sales Invoice", "Purchase Invoice",
            "Asset", "Customer", "Supplier",
        ]]],
    },

    # 4. Masters the module needs to function at all.
    {"dt": "Property Type"},
    {"dt": "Unit Type"},
    {"dt": "Land Tenure Type"},
    {"dt": "Title Document Type"},
    {"dt": "Identification Type"},
    {
        "dt": "Property Region",
        "filters": [["name", "!=", "REPAIR TRIGGER"]],
    },

    # 5. Roles.
    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Property Manager", "Property Accountant", "Leasing Agent",
            "Facilities Manager", "Maintenance Manager",
        ]]],
    },

    # 6. The Create Rent Invoice button. Reads income account and cost centre
    #    from Item Defaults, falling back to the Company record — no account
    #    names are hardcoded.
    {
        "dt": "Client Script",
        "filters": [["module", "=", "Powersoft Property"]],
    },

    # 7. The rent schedule write-back. All five scripts work purely off
    #    document links and frappe.utils — no account or company names.
    #
    #    NOTE: "PS One Off Data Repair" is excluded on purpose. It was a scratch
    #    script for fixing demo data and must never reach a customer site.
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

    # 8. Documents the client actually receives.
    {
        "dt": "Print Format",
        "filters": [["module", "=", "Powersoft Property"]],
    },

    # 9. Reports. Excludes the two disabled list views.
    #
    #    Every Query Report takes Company as a mandatory filter with NO default,
    #    and scopes its rows through that filter. Property Unit reports reach
    #    company by joining `tabPS Property`, not by matching currency.
    {
        "dt": "Report",
        "filters": [
            ["module", "=", "Powersoft Property"],
            ["disabled", "=", 0],
        ],
    },

    # 10. Dashboard, cards, charts and the workspace tree.
    {
        "dt": "Number Card",
        "filters": [["module", "=", "Powersoft Property"]],
    },
    {
        "dt": "Dashboard Chart",
        "filters": [["module", "=", "Powersoft Property"]],
    },
    {
        "dt": "Dashboard",
        "filters": [["module", "=", "Powersoft Property"]],
    },
    {
        "dt": "Custom HTML Block",
        "filters": [["name", "in", ["Property Hero"]]],
    },

    # WATCH THIS ONE. The six property workspaces were built through the desk
    # UI, which leaves `module` blank — filtering on module exports NOTHING and
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

    # 11. Approval workflows.
    {
        "dt": "Workflow State",
        "filters": [["name", "in", [
            "Draft", "Pending Approval", "Approved", "Rejected",
        ]]],
    },
    {
        "dt": "Workflow Action Master",
        "filters": [["name", "in", [
            "Submit for Approval", "Approve", "Reject",
        ]]],
    },
    {
        "dt": "Workflow",
        "filters": [["document_type", "in", [
            "Property Sale Contract", "Maintenance Job Card",
        ]]],
    },

    # 12. Tenant portal and public listings.
    #
    #     WARNING: these templates reference /files/*.svg images that will not
    #     exist on a fresh site. Ship the images in public/ or the portal
    #     renders with empty picture frames.
    {
        "dt": "Web Page",
        "filters": [["route", "in", [
            "properties", "my-tenancy", "my-invoices", "my-requests",
        ]]],
    },
    {
        "dt": "Web Form",
        "filters": [["route", "in", ["report-a-problem"]]],
    },
]
