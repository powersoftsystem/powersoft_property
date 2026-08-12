"""
Runs once, immediately after `bench install-app powersoft_property`.

Its job is the few things that cannot travel as fixtures because they depend on
the customer's own chart of accounts and company records.

Two principles here, both learned the hard way.

Nothing is hardcoded to one country or company. Every value is read from the
Company record at run time, so this behaves the same in Accra, Lagos or
Manchester.

No step may abort the install. Each is wrapped individually. An earlier version
created a Lands asset category with its accounts left blank, intending them to
be mapped later. ERPNext makes that child table mandatory, so the save raised
MandatoryError, after_install died, and the whole install-app failed. The app
itself was fine; the setup helper broke it.

That category is gone for a second reason. Not every property business buys
land. Plenty buy a finished building and let it straight away. The module's
logic is simply: an asset exists, a project may build on it, that becomes a
property, which has units. Whether the customer calls their category Land,
Lands, Property or nothing at all is their decision, not ours.
"""

import frappe


def after_install():
    companies = _safe("find property companies", _property_companies) or []

    for company in companies:
        _safe("create income accounts for {0}".format(company),
              _create_income_accounts, company)

    _safe("set item defaults", _set_item_defaults, companies)

    scoped = _safe("schedule card scoping", _schedule_card_scope)

    _safe("show next steps", _print_next_steps, companies, scoped)


def _safe(label, fn, *args):
    """Run a setup step. Log and carry on if it fails, never abort the install."""
    try:
        return fn(*args)
    except Exception:
        frappe.log_error(
            title="Powersoft Property setup: {0}".format(label),
            message=frappe.get_traceback(),
        )
        print("  [skipped] {0} - see the Error Log".format(label))
        return None


# ---------------------------------------------------------------------------
# Number cards
#
# The cards ship with no company filter at all. A filter naming the company
# they were built on would read zero on every other site.
#
# But "no filter" is only right for a site with one company. On a bench running
# several, the cards would count across all of them and disagree with the
# workspace hero panel, which scopes properly through PS Property.
#
# So the company is written in here, at install time, from the customer's own
# records. Ship neutral, scope on arrival.
#
# Safe to re-run:
#   bench --site <site> execute powersoft_property.install.scope_cards_to_company
# ---------------------------------------------------------------------------

CARD_DOCTYPES = {
    "Rent Roll": "PS Lease Agreement",
    "Active Leases": "PS Lease Agreement",
    "Monthly Rent Roll": "PS Lease Agreement",
    "Arrears": "Sales Invoice",
    "Rent Outstanding": "Sales Invoice",
    "Deposits Held": "Security Deposit",
    "Active Listings": "Property Listing",
    "Open Maintenance Requests": "PS Maintenance Request",
}

# Property Unit has no company of its own. It reaches company through its
# parent property, so those cards are filtered by property list instead.
UNIT_CARDS = ["Total Units", "Occupied Units", "Vacant Units"]


def _ps_property_ready():
    """
    True once the app's own tables exist.

    after_install runs BEFORE the fixtures are synced, so on a fresh install
    `tabPS Property` does not exist yet and any query against it raises
    TableMissingError. That is what made the first install log
    "[skipped] scope dashboard cards". The scoping is not lost - after_migrate
    runs once the tables are there and does it properly.
    """
    try:
        return bool(frappe.db.table_exists("PS Property"))
    except Exception:
        return False


def scope_cards_to_company(company=None, commit=True):
    """Write the site's own company into every property number card."""
    import json

    company = company or _default_company()
    if not company:
        print("No company found, cards left unscoped.")
        return None

    scoped = 0
    for card, doctype in CARD_DOCTYPES.items():
        if _add_company_clause(card, doctype, company, json):
            scoped += 1

    properties = (
        frappe.get_all("PS Property", filters={"company": company}, pluck="name")
        if _ps_property_ready()
        else []
    )
    for card in UNIT_CARDS:
        if _add_property_clause(card, properties, json):
            scoped += 1

    if commit:
        frappe.db.commit()
    frappe.clear_cache()

    print("Scoped {0} card(s) to {1}.".format(scoped, company))
    if not properties:
        print("No properties exist yet, so unit cards count all units.")
        print("Re-run this once properties are created.")
    return company


def _default_company():
    """The company this site is really about."""
    from_defaults = frappe.db.get_single_value("Global Defaults", "default_company")
    if from_defaults:
        return from_defaults

    if not _ps_property_ready():
        companies = frappe.get_all("Company", pluck="name")
        return companies[0] if len(companies) == 1 else None

    with_property = frappe.get_all("PS Property", pluck="company", distinct=True)
    with_property = [c for c in with_property if c]
    if len(with_property) == 1:
        return with_property[0]

    companies = frappe.get_all("Company", pluck="name")
    if len(companies) == 1:
        return companies[0]

    return with_property[0] if with_property else None


def _add_company_clause(card, doctype, company, json):
    if not frappe.db.exists("Number Card", card):
        return False

    raw = frappe.db.get_value("Number Card", card, "filters_json") or "[]"
    try:
        filters = json.loads(raw)
    except ValueError:
        filters = []

    filters = [f for f in filters
               if not (isinstance(f, list) and len(f) > 1 and f[1] == "company")]
    filters.append([doctype, "company", "=", company])

    frappe.db.set_value("Number Card", card, "filters_json",
                        json.dumps(filters), update_modified=False)
    return True


def _add_property_clause(card, properties, json):
    if not frappe.db.exists("Number Card", card):
        return False
    if not properties:
        return False

    raw = frappe.db.get_value("Number Card", card, "filters_json") or "[]"
    try:
        filters = json.loads(raw)
    except ValueError:
        filters = []

    filters = [f for f in filters
               if not (isinstance(f, list) and len(f) > 1 and f[1] == "property")]
    filters.append(["Property Unit", "property", "in", properties])

    frappe.db.set_value("Number Card", card, "filters_json",
                        json.dumps(filters), update_modified=False)
    return True


def _property_companies():
    """
    Only touch companies that actually do property.

    On a fresh single-company site there is no property data yet, so every
    company qualifies. On an established bench already running mining,
    hospitality and healthcare companies alongside, this stops the install
    creating a Rental Income account under each of them.
    """
    all_companies = frappe.get_all("Company", pluck="name")

    if not frappe.db.table_exists("PS Property"):
        return all_companies

    with_property = frappe.get_all("PS Property", pluck="company", distinct=True)
    with_property = [c for c in with_property if c]

    return with_property or all_companies


# ---------------------------------------------------------------------------
# Income accounts
#
# This fixes the most expensive mistake made while building the module: rent
# was posted to an account whose root type was Expense, so revenue showed up
# as a negative cost and every property P&L was wrong.
#
# Creating these under the company's own Income root, with the root type
# checked, means a fresh install cannot repeat it.
# ---------------------------------------------------------------------------

ACCOUNTS = [
    {"account_name": "Rental Income", "account_type": "Income Account"},
    {"account_name": "Service Charge Income", "account_type": "Income Account"},
]


def _create_income_accounts(company):
    parent = _income_parent(company)
    if not parent:
        return

    abbr = frappe.db.get_value("Company", company, "abbr")

    for spec in ACCOUNTS:
        name = "{0} - {1}".format(spec["account_name"], abbr)
        if frappe.db.exists("Account", name):
            continue

        doc = frappe.new_doc("Account")
        doc.account_name = spec["account_name"]
        doc.account_type = spec["account_type"]
        doc.parent_account = parent
        doc.company = company
        doc.root_type = "Income"
        doc.report_type = "Profit and Loss"
        doc.is_group = 0
        doc.flags.ignore_permissions = True
        doc.insert()

    frappe.db.commit()


def _income_parent(company):
    """
    Find a sensible group account to hang the new income accounts from.

    Prefers the company's own default income account's parent, then any
    Direct Income / Indirect Income group, then the Income root itself.
    """
    default_income = frappe.db.get_value("Company", company, "default_income_account")
    if default_income:
        parent = frappe.db.get_value("Account", default_income, "parent_account")
        if parent:
            return parent

    for account_name in ("Direct Income", "Indirect Income"):
        match = frappe.db.get_value(
            "Account",
            {"company": company, "account_name": account_name, "is_group": 1},
            "name",
        )
        if match:
            return match

    return frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Income", "is_group": 1, "parent_account": ""},
        "name",
    )


# ---------------------------------------------------------------------------
# Item defaults
#
# The Create Rent Invoice button reads the income account off Item Defaults,
# falling back to the Company default. Wiring the rent and service charge items
# to the accounts just created means the button produces a correct invoice on
# the customer's very first try.
# ---------------------------------------------------------------------------

ITEM_HINTS = {
    "Rental Income": ("rent",),
    "Service Charge Income": ("service charge", "service_charge"),
}


def _set_item_defaults(company_names):
    if not company_names:
        return

    companies = frappe.get_all(
        "Company", filters={"name": ["in", company_names]}, fields=["name", "abbr"]
    )

    for account_name, hints in ITEM_HINTS.items():
        for item_code in _matching_items(hints):
            for company in companies:
                account = "{0} - {1}".format(account_name, company.abbr)
                if not frappe.db.exists("Account", account):
                    continue
                _apply_item_default(item_code, company.name, account)

    frappe.db.commit()


def _matching_items(hints):
    """Service items whose code or name looks like rent or a service charge."""
    found = set()
    for hint in hints:
        for field in ("item_code", "item_name"):
            rows = frappe.get_all(
                "Item",
                filters={field: ["like", "%{0}%".format(hint)], "is_stock_item": 0},
                pluck="name",
            )
            found.update(rows)
    return found


def _apply_item_default(item_code, company, account):
    item = frappe.get_doc("Item", item_code)

    for row in item.item_defaults:
        if row.company != company:
            continue
        # Never overwrite a deliberate choice, only fill a blank.
        if not row.income_account:
            row.income_account = account
            item.flags.ignore_permissions = True
            item.flags.ignore_validate_update_after_submit = True
            item.save()
        return

    item.append("item_defaults", {"company": company, "income_account": account})
    item.flags.ignore_permissions = True
    item.save()


def _print_next_steps(companies, scoped):
    listed = ", ".join(companies) or "no company"
    where = "scoped to {0}".format(scoped) if scoped else "not scoped - no company found"

    frappe.msgprint(
        msg=(
            "<p>Powersoft Property is installed.</p>"
            "<ul>"
            "<li><b>Income accounts</b> created under the Income group of "
            "<i>{0}</i>, and wired into Item Defaults on any rent or service "
            "charge item found.</li>"
            "<li><b>Dashboard cards</b> {1}. They keep themselves scoped - "
            "on every migrate, when a company is created, and when a property "
            "is added or removed. Nothing to run by hand.</li>"
            "</ul>"
            "<p><b>Create your own asset categories.</b> The module creates "
            "none, on purpose. Some businesses buy land and build; others buy "
            "a finished building and let it immediately. Create whatever fits "
            "how you work. The flow is simply: an asset exists, a project may "
            "build on it, that becomes a property, which has units.</p>"
            "<p>Also check your rent items point at an <b>Income</b> account, "
            "and upload property images or the portal panels render empty.</p>"
        ).format(listed, where),
        title="Powersoft Property installed",
        indicator="green",
    )


# ---------------------------------------------------------------------------
# Keeping the cards scoped WITHOUT anyone running a command
#
# Scoping used to be a manual step: install the app, run the setup wizard,
# then remember to run
#
#     bench --site <site> execute powersoft_property.install.scope_cards_to_company
#
# Three ways that goes wrong. after_install runs before the company exists on a
# fresh site, so there is nothing to scope. Unit cards need re-running once
# properties are created. And nobody remembers the third step anyway.
#
# So it is wired to the events that actually change the answer: a migrate, a
# new company, a new or deleted property. The function replaces its own
# clauses rather than stacking them, so running it often is harmless.
# ---------------------------------------------------------------------------

def after_migrate():
    """Runs on every `bench migrate`, including the one install-app triggers."""
    _safe("scope dashboard cards", scope_cards_to_company)


def refresh_card_scope(doc=None, method=None):
    """
    Hooked to Company and PS Property changes.

    Never raise. A failure here must not stop someone saving a company or a
    property - the worst case is a card counts too much until the next migrate.
    """
    try:
        scope_cards_to_company(commit=False)
    except Exception:
        frappe.log_error(
            title="Powersoft Property: could not re-scope cards",
            message=frappe.get_traceback(),
        )


def _schedule_card_scope():
    """
    Scope the cards AFTER the install transaction commits.

    Order of events inside `bench install-app` is: create tables, run
    after_install, THEN sync fixtures. The number cards are fixtures, so at
    after_install time they do not exist yet - scoping there found nothing and
    reported "Scoped 0 card(s)", which is how the manual bench command crept
    into the install instructions in the first place.

    Enqueuing with enqueue_after_commit=True runs it once the fixtures are in.
    If no worker is running the job is simply lost, and after_migrate picks it
    up on the next migrate - so this degrades to "correct a bit later", never
    to "wrong forever".
    """
    company = _default_company()

    frappe.enqueue(
        "powersoft_property.install.scope_cards_to_company",
        queue="short",
        enqueue_after_commit=True,
        job_name="powersoft_property_scope_cards",
    )

    return company


def ensure_cards_scoped(login_manager=None):
    """
    Self-heal on login.

    Everything else about scoping is timing-dependent. after_install runs before
    the fixtures land, so there are no cards to scope. Enqueuing after commit
    does not survive a `bench install-app` CLI transaction. after_migrate works
    but only if someone runs migrate.

    Login is the one moment guaranteed to happen before anyone can look at a
    dashboard, needs no background worker, and costs one cached flag plus one
    COUNT. The flag lives in the cache, so it clears on migrate and on
    clear-cache - exactly when the answer might have changed.
    """
    try:
        cache = frappe.cache()
        if cache.get_value("powersoft_property_cards_scoped"):
            return

        pending = frappe.db.sql(
            """
            select count(*)
            from `tabNumber Card`
            where module = 'Powersoft Property'
              and ifnull(filters_json, '') not like '%company%'
            """
        )[0][0]

        if pending:
            scope_cards_to_company()

        cache.set_value("powersoft_property_cards_scoped", 1)
    except Exception:
        frappe.log_error(
            title="Powersoft Property: card self-heal failed",
            message=frappe.get_traceback(),
        )
