"""
Runs once, immediately after `bench install-app powersoft_property`.

Its job is to create the things the module needs that cannot travel as
fixtures, because they depend on the customer's own chart of accounts.

Everything in here is derived from the Company record at run time. No account
name, company name, currency or abbreviation is hardcoded, so this file behaves
the same on a site in Accra, Lagos or Manchester.
"""

import frappe


def after_install():
	_create_asset_categories()

	companies = _property_companies()
	for company in companies:
		_create_income_accounts(company)
	_set_item_defaults(companies)

	_print_next_steps(companies)


def _property_companies():
	"""
	Only touch companies that actually do property.

	On a fresh single-company site there is no property data yet, so every
	company qualifies — which is what you want. On an established bench that
	already runs mining, hospitality and healthcare companies alongside, this
	stops the install creating a Rental Income account under each of them.
	"""
	all_companies = frappe.get_all("Company", pluck="name")

	if not frappe.db.table_exists("PS Property"):
		return all_companies

	with_property = frappe.get_all(
		"PS Property", pluck="company", distinct=True
	)
	with_property = [c for c in with_property if c]

	return with_property or all_companies


# ---------------------------------------------------------------------------
# Asset categories
# ---------------------------------------------------------------------------

def _create_asset_categories():
	"""
	Lands never depreciates. Buildings is straight line over 50 years.

	Accounts are deliberately left blank — the fixed asset, accumulated
	depreciation and depreciation expense accounts differ on every site and
	must be mapped per company by hand.
	"""
	categories = [
		{"name": "Lands", "non_depreciable": 1, "finance_books": []},
		{
			"name": "Buildings",
			"non_depreciable": 0,
			"finance_books": [
				{
					"depreciation_method": "Straight Line",
					"frequency_of_depreciation": 12,
					"total_number_of_depreciations": 50,
				}
			],
		},
	]

	for cat in categories:
		if frappe.db.exists("Asset Category", cat["name"]):
			continue

		doc = frappe.new_doc("Asset Category")
		doc.asset_category_name = cat["name"]
		doc.non_depreciable_category = cat["non_depreciable"]

		for fb in cat["finance_books"]:
			doc.append("finance_books", fb)

		doc.flags.ignore_permissions = True
		doc.insert()

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Income accounts
#
# This is the fix for the single most expensive mistake made while building
# the module: rent was posted to an account whose root type was Expense, so
# revenue showed up as a negative cost and every property P&L was wrong.
#
# Creating these automatically, under the company's own Income root, with the
# root type checked, means a fresh install cannot repeat it.
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
	'Direct Income' / 'Indirect Income' group, then the Income root itself.
	"""
	default_income = frappe.db.get_value("Company", company, "default_income_account")
	if default_income:
		parent = frappe.db.get_value("Account", default_income, "parent_account")
		if parent:
			return parent

	for account_name in ("Direct Income", "Indirect Income"):
		match = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_name": account_name,
				"is_group": 1,
			},
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
# to the accounts we just created means the button produces a correct invoice
# on the customer's very first try.
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
		# Never overwrite a deliberate choice — only fill a blank.
		if not row.income_account:
			row.income_account = account
			item.flags.ignore_permissions = True
			item.flags.ignore_validate_update_after_submit = True
			item.save()
		return

	item.append("item_defaults", {"company": company, "income_account": account})
	item.flags.ignore_permissions = True
	item.save()


# ---------------------------------------------------------------------------

def _print_next_steps(companies):
	frappe.msgprint(
		msg=_next_steps_html(companies),
		title="Powersoft Property installed",
		indicator="green",
	)


def _next_steps_html(companies):
	listed = ", ".join("<i>{0}</i>".format(c) for c in companies) or "—"

	return """
	<p>The module is installed. Two things were set up automatically:</p>

	<ul>
		<li><b>Asset categories</b> — <i>Lands</i> (never depreciates) and
		<i>Buildings</i> (straight line, 50 years) now exist.</li>

		<li><b>Income accounts</b> — <i>Rental Income</i> and <i>Service Charge
		Income</i> were created under the Income group of {0}, with the root type
		checked, and wired into Item Defaults on any rent or service charge item
		found. Companies with no property records were left alone.</li>
	</ul>""".format(listed) + """

	<p>Three things still need you:</p>

	<ol>
		<li><b>Map the asset category accounts.</b> Open <i>Lands</i> and
		<i>Buildings</i> and set the fixed asset, accumulated depreciation and
		depreciation expense accounts for your company. These cannot be guessed
		from your chart of accounts.</li>

		<li><b>Check the rent items.</b> The matcher looks for items whose code
		or name contains "rent" or "service charge". If yours are named
		differently, set the income account on them yourself.</li>

		<li><b>Upload property images.</b> The public listings site and the
		tenant portal reference image files that do not exist on a fresh site.
		Until you upload your own, the picture panels render empty.</li>
	</ol>

	<p>See <code>README.md</code> in the app for the full checklist.</p>
	"""
