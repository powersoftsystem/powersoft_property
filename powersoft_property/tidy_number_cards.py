"""
Second pass over the number cards, run on the demo site before exporting.

`deneutralise_demo_labels` renamed what it could, but four cards refused:
"Total Units", "Occupied Units", "Vacant Units" and "Active Leases" were
already taken by older duplicates — the first set built during the demo, whose
filters name six specific properties:

    ["Property Unit", "property", "in",
        ["Cantonments Court Apartments", "East Legon Hills Villas", ...]]

That filter matches nothing on a customer site, so those cards would ship and
read zero forever. There are four more leftovers in the same state carrying a
company or currency in the filter: the UK/GHS rent roll and rent outstanding
pair.

So: delete the leftovers, then rename the good cards into the names they free
up. Deletion only happens when nothing points at the card — the check covers
workspace layout JSON, workspace child rows and dashboards.

    bench --site demo-v16.powersoftsystem.com execute \\
        powersoft_property.tidy_number_cards.run

Safe to run twice.
"""

import frappe


# Good card -> the clean name it should take, currently held by a duplicate.
RENAME_INTO = {
	"Total Units — Ghana": "Total Units",
	"Occupied Units — Ghana": "Occupied Units",
	"Vacant Units — Ghana": "Vacant Units",
	"Active Leases — Ghana": "Active Leases",
}

# Demo-only cards. Each carries a company or a currency in its filter and has
# a neutral equivalent already shipping.
LEFTOVERS = [
	"Monthly Rent Roll — UK (GBP)",
	"Monthly Rent Roll (GHS)",
	"Rent Outstanding — UK (GBP)",
	"Rent Outstanding (GHS)",
]

WORKSPACES = [
	"Powersoft Property", "Property Setup", "Property Leasing",
	"Property Sales", "Property Billing", "Property Facilities",
]


def run():
	referenced = _referenced_cards()

	removed = _remove(list(RENAME_INTO.values()) + LEFTOVERS, referenced)
	renamed = _rename_into_freed_names()

	_repoint_workspaces(renamed)
	_repoint_dashboards(renamed)
	_align_labels()

	frappe.db.commit()
	frappe.clear_cache()

	print("Removed {0} leftover card(s), renamed {1}.".format(len(removed), len(renamed)))
	_report()


# ---------------------------------------------------------------------------

def _referenced_cards():
	"""Every card name mentioned by a workspace or a dashboard."""
	names = set()

	for ws_name in frappe.get_all(
		"Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"
	):
		ws = frappe.get_doc("Workspace", ws_name)
		content = ws.content or ""

		for card in frappe.get_all("Number Card", pluck="name"):
			# The layout stores the card name inside a JSON string.
			if '"{0}"'.format(card) in content:
				names.add(card)

		for row in ws.number_cards:
			if row.number_card_name:
				names.add(row.number_card_name)

	for dash_name in frappe.get_all("Dashboard", pluck="name"):
		dash = frappe.get_doc("Dashboard", dash_name)
		for row in dash.cards:
			if row.card:
				names.add(row.card)

	return names


def _remove(candidates, referenced):
	removed = []

	for name in candidates:
		if not frappe.db.exists("Number Card", name):
			continue
		if name in referenced:
			print("Keeping '{0}' — still referenced".format(name))
			continue

		frappe.delete_doc(
			"Number Card", name, force=True, ignore_permissions=True, delete_permanently=True
		)
		removed.append(name)
		print("Removed leftover card: {0}".format(name))

	return removed


def _rename_into_freed_names():
	renamed = {}

	for old, new in RENAME_INTO.items():
		if not frappe.db.exists("Number Card", old):
			continue
		if frappe.db.exists("Number Card", new):
			print("Cannot rename '{0}' — '{1}' is still occupied".format(old, new))
			continue

		frappe.rename_doc("Number Card", old, new, force=True, show_alert=False)
		renamed[old] = new
		print("Number Card: '{0}' -> '{1}'".format(old, new))

	return renamed


def _repoint_workspaces(renamed):
	if not renamed:
		return

	for ws_name in frappe.get_all(
		"Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"
	):
		ws = frappe.get_doc("Workspace", ws_name)
		touched = False

		content = ws.content or ""
		for old, new in renamed.items():
			if old in content:
				content = content.replace(old, new)
				touched = True
		if touched:
			ws.content = content

		for row in ws.number_cards:
			if row.number_card_name in renamed:
				row.number_card_name = renamed[row.number_card_name]
				touched = True
			# The renderer matches a card by the child row's label. If the two
			# ever disagree the card silently vanishes from the page.
			if row.label != row.number_card_name:
				row.label = row.number_card_name
				touched = True

		if touched:
			ws.flags.ignore_permissions = True
			ws.save()
			print("Workspace repointed: {0}".format(ws_name))


def _repoint_dashboards(renamed):
	if not renamed:
		return

	for dash_name in frappe.get_all("Dashboard", pluck="name"):
		dash = frappe.get_doc("Dashboard", dash_name)
		touched = False

		for row in dash.cards:
			if row.card in renamed:
				row.card = renamed[row.card]
				touched = True

		if touched:
			dash.flags.ignore_permissions = True
			dash.save()
			print("Dashboard repointed: {0}".format(dash_name))


def _align_labels():
	"""A card's label should read the same as its name. Several drifted apart."""
	for card in frappe.get_all(
		"Number Card",
		filters={"module": "Powersoft Property"},
		fields=["name", "label"],
	):
		if card.label != card.name:
			frappe.db.set_value(
				"Number Card", card.name, "label", card.name, update_modified=False
			)
			print("Label aligned: '{0}' (was '{1}')".format(card.name, card.label))


def _report():
	print("\nRemaining cards in the module:")
	offenders = []

	for card in frappe.get_all(
		"Number Card",
		filters={"module": "Powersoft Property"},
		fields=["name", "filters_json"],
		order_by="name",
	):
		flt = card.filters_json or ""
		dirty = any(
			token in flt
			for token in ("PS Realty", "Ghana", "GHS", "GBP", "Cantonments", "East Legon")
		) or any(token in card.name for token in ("Ghana", "UK", "GHS", "GBP"))

		print("  {0}{1}".format(card.name, "   <-- still company-specific" if dirty else ""))
		if dirty:
			offenders.append(card.name)

	if offenders:
		print("\n{0} card(s) still carry a company, country or currency.".format(len(offenders)))
	else:
		print("\nClean. No card carries a company, country or currency.")
