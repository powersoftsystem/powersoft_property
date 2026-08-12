"""
Collapse the duplicate number cards on the demo site, before exporting.

The demo ended up with two parallel sets of the same four cards:

    Total Units          used by Property Setup       filtered on a hardcoded
    Occupied Units       used by Property Setup,      list of six demo property
    Vacant Units         Property Leasing,            names — matches nothing on
    Active Leases        Property Sales               a customer site

    Total Units — Ghana      used by the main workspace and the Property
    Occupied Units — Ghana   Management dashboard; filters are already clean,
    Vacant Units — Ghana     but the names carry a country
    Active Leases — Ghana

Neither set is disposable on its own: delete the first and three sub-workspaces
lose their cards; delete the second and the main workspace and dashboard lose
theirs. So collapse them — give the cleanly-named cards correct filters, point
every workspace and dashboard at those, then drop the duplicates.

Two more cards carry a company in their filter and a currency in their name:
"Monthly Rent Roll (GHS)" and "Rent Outstanding (GHS)". Those are cleaned and
renamed in place.

    bench --site demo-v16.powersoftsystem.com execute \\
        powersoft_property.tidy_number_cards.run

Safe to run twice. Nothing is deleted while anything still points at it.
"""

import frappe


# Duplicate -> the cleanly named card that should survive.
COLLAPSE = {
	"Total Units — Ghana": "Total Units",
	"Occupied Units — Ghana": "Occupied Units",
	"Vacant Units — Ghana": "Vacant Units",
	"Active Leases — Ghana": "Active Leases",
}

# Carries a currency in the name and a company in the filter.
RENAME = {
	"Monthly Rent Roll (GHS)": "Monthly Rent Roll",
	"Rent Outstanding (GHS)": "Rent Outstanding",
}

# The filter each surviving card should end up with. No company, no currency,
# no property names — the card counts whatever the site holds.
FILTERS = {
	"Total Units": "[]",
	"Occupied Units": '[["Property Unit","unit_status","=","Occupied"]]',
	"Vacant Units": '[["Property Unit","unit_status","=","Vacant"]]',
	"Active Leases": (
		'[["PS Lease Agreement","lease_status","in",["Active","Expiring Soon"]],'
		'["PS Lease Agreement","docstatus","=",1]]'
	),
	"Monthly Rent Roll": (
		'[["PS Lease Agreement","lease_status","in",["Active","Expiring Soon"]],'
		'["PS Lease Agreement","docstatus","=",1]]'
	),
	"Rent Outstanding": '[["Sales Invoice","docstatus","=",1]]',
}

WORKSPACES = [
	"Powersoft Property", "Property Setup", "Property Leasing",
	"Property Sales", "Property Billing", "Property Facilities",
]

DIRTY_TOKENS = ("PS Realty", "Ghana", "GHS", "GBP", "Cantonments", "East Legon",
                "Osu Oxford", "Airport West", "Spintex", "Tema Community")


def run():
	_apply_filters()

	moved = _repoint(COLLAPSE)
	dropped = _drop(list(COLLAPSE.keys()))

	renamed = _rename(RENAME)
	_repoint(renamed)
	_apply_filters()

	_align_labels()

	frappe.db.commit()
	frappe.clear_cache()

	print("\nRepointed {0} reference(s), dropped {1} duplicate(s), renamed {2}.".format(
		moved, len(dropped), len(renamed)))
	_report()


# ---------------------------------------------------------------------------

def _apply_filters():
	for name, filters in FILTERS.items():
		if not frappe.db.exists("Number Card", name):
			continue
		current = frappe.db.get_value("Number Card", name, "filters_json")
		if current == filters:
			continue
		frappe.db.set_value("Number Card", name, "filters_json", filters, update_modified=False)
		print("Filter cleaned: {0}".format(name))


def _repoint(mapping):
	"""Point every workspace and dashboard at the surviving card."""
	if not mapping:
		return 0

	count = 0

	for ws_name in frappe.get_all(
		"Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"
	):
		ws = frappe.get_doc("Workspace", ws_name)
		touched = False

		content = ws.content or ""
		for old, new in mapping.items():
			if old in content:
				content = content.replace(old, new)
				touched = True
		if touched:
			ws.content = content

		for row in ws.number_cards:
			if row.number_card_name in mapping:
				row.number_card_name = mapping[row.number_card_name]
				count += 1
				touched = True
			# The renderer looks a card up by the child row's label. If label
			# and name ever disagree the card silently vanishes from the page.
			if row.label != row.number_card_name:
				row.label = row.number_card_name
				touched = True

		if touched:
			ws.flags.ignore_permissions = True
			ws.save()
			print("Workspace repointed: {0}".format(ws_name))

	for dash_name in frappe.get_all("Dashboard", pluck="name"):
		dash = frappe.get_doc("Dashboard", dash_name)
		touched = False

		for row in dash.cards:
			if row.card in mapping:
				row.card = mapping[row.card]
				count += 1
				touched = True

		if touched:
			dash.flags.ignore_permissions = True
			dash.save()
			print("Dashboard repointed: {0}".format(dash_name))

	return count


def _drop(names):
	"""Delete, but only once nothing points at the card."""
	referenced = _referenced()
	dropped = []

	for name in names:
		if not frappe.db.exists("Number Card", name):
			continue
		if name in referenced:
			print("Keeping '{0}' — still referenced".format(name))
			continue

		frappe.delete_doc(
			"Number Card", name, force=True, ignore_permissions=True,
			delete_permanently=True,
		)
		dropped.append(name)
		print("Dropped duplicate: {0}".format(name))

	return dropped


def _referenced():
	names = set()

	for ws_name in frappe.get_all(
		"Workspace", filters={"name": ["in", WORKSPACES]}, pluck="name"
	):
		ws = frappe.get_doc("Workspace", ws_name)
		content = ws.content or ""
		for row in ws.number_cards:
			if row.number_card_name:
				names.add(row.number_card_name)
		for card in frappe.get_all("Number Card", pluck="name"):
			if '"{0}"'.format(card) in content:
				names.add(card)

	for dash_name in frappe.get_all("Dashboard", pluck="name"):
		for row in frappe.get_doc("Dashboard", dash_name).cards:
			if row.card:
				names.add(row.card)

	return names


def _rename(mapping):
	done = {}

	for old, new in mapping.items():
		if not frappe.db.exists("Number Card", old):
			continue
		if frappe.db.exists("Number Card", new):
			print("Cannot rename '{0}' — '{1}' is occupied".format(old, new))
			continue

		frappe.rename_doc("Number Card", old, new, force=True, show_alert=False)
		done[old] = new
		print("Renamed: '{0}' -> '{1}'".format(old, new))

	return done


def _align_labels():
	for card in frappe.get_all(
		"Number Card",
		filters={"module": "Powersoft Property"},
		fields=["name", "label"],
	):
		if card.label != card.name:
			frappe.db.set_value(
				"Number Card", card.name, "label", card.name, update_modified=False
			)
			print("Label aligned: {0}".format(card.name))


def _report():
	print("\nCards in the module:")
	offenders = []

	for card in frappe.get_all(
		"Number Card",
		filters={"module": "Powersoft Property"},
		fields=["name", "filters_json"],
		order_by="name",
	):
		blob = (card.filters_json or "") + " " + card.name
		dirty = [t for t in DIRTY_TOKENS if t in blob]

		print("  {0}{1}".format(
			card.name, "   <-- {0}".format(", ".join(dirty)) if dirty else ""))
		if dirty:
			offenders.append(card.name)

	if offenders:
		print("\n{0} card(s) still carry a company, country or currency.".format(len(offenders)))
	else:
		print("\nClean. No card carries a company, country or currency.")
