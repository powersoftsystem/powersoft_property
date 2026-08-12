"""
Run this ONCE on the demo site, before you export fixtures.

It does two jobs.

**One that is cosmetic.** Several number cards and charts still carry "— Ghana"
or "— UK" in their names. Harmless to the machine, but a paying customer should
not open their new system and read "Money — Ghana".

**One that is a real defect.** The report named "Vacancy / Void Loss" contains a
forward slash. Frappe routes desk pages by name, so the slash splits the route
and the report cannot be opened at all — it returns
`TypeError: getdoctype() missing 1 required positional argument`. It also makes
for an awkward fixture filename. Renaming it to "Vacancy and Void Loss" fixes
both.

None of this can be done through the REST API. Renaming needs `frappe.rename_doc`,
and the workspace layout lives in a JSON string that has to be rewritten in place.

    bench --site demo-v16.powersoftsystem.com execute \\
        powersoft_property.deneutralise_demo_labels.run

Safe to run twice. Everything checks before it acts.
"""

import frappe


REPORT_RENAMES = {
	# The slash makes this report unreachable in the desk. Not optional.
	"Vacancy / Void Loss": "Vacancy and Void Loss",
}

CARD_RENAMES = {
	"Rent Roll — Ghana": "Rent Roll",
	"Arrears — Ghana": "Arrears",
	"Deposits Held — Ghana": "Deposits Held",
	"Total Units — Ghana": "Total Units",
	"Occupied Units — Ghana": "Occupied Units",
	"Vacant Units — Ghana": "Vacant Units",
	"Active Leases — Ghana": "Active Leases",
	"Total Units — UK": "Units (secondary)",
	"Vacant Units — UK": "Vacant Units (secondary)",
}

CHART_RENAMES = {
	"Units by Property — Ghana": "Units by Property (all)",
}

HEADER_REPLACEMENTS = [
	("Money — Ghana", "Money"),
	("Occupancy — Ghana", "Occupancy"),
]


def run():
	renamed = {}
	renamed.update(_rename("Report", REPORT_RENAMES))
	renamed.update(_rename("Number Card", CARD_RENAMES))
	renamed.update(_rename("Dashboard Chart", CHART_RENAMES))

	_fix_workspaces(renamed)
	_fix_dashboards(renamed)

	frappe.db.commit()
	frappe.clear_cache()

	print("Done. Renamed {0} record(s).".format(len(renamed)))
	print("Now run: bench --site <site> export-fixtures --app powersoft_property")


def _rename(doctype, mapping):
	"""Rename, skipping anything already done or already taken."""
	done = {}

	# Whatever field mirrors the name and shows on screen, so it does not go
	# stale after the rename.
	title_field = {
		"Report": "report_name",
		"Number Card": "label",
		"Dashboard Chart": "chart_name",
	}.get(doctype)

	for old, new in mapping.items():
		if not frappe.db.exists(doctype, old):
			continue
		if frappe.db.exists(doctype, new):
			print("Skipping {0}: '{1}' already exists".format(doctype, new))
			continue

		frappe.rename_doc(doctype, old, new, force=True, show_alert=False)
		if title_field:
			frappe.db.set_value(doctype, new, title_field, new, update_modified=False)
		done[old] = new
		print("{0}: '{1}' -> '{2}'".format(doctype, old, new))

	return done


def _fix_workspaces(renamed):
	"""
	Rewrite the layout JSON and the child tables together.

	The workspace renderer looks a card up by the label on its child row, so
	the child row's label MUST equal the card's name. Getting this wrong makes
	the card vanish from the page with no error anywhere.
	"""
	names = frappe.get_all(
		"Workspace",
		filters={"name": ["in", [
			"Powersoft Property", "Property Setup", "Property Leasing",
			"Property Sales", "Property Billing", "Property Facilities",
		]]},
		pluck="name",
	)

	for name in names:
		ws = frappe.get_doc("Workspace", name)
		touched = False

		content = ws.content or ""
		for old, new in renamed.items():
			if old in content:
				content = content.replace(old, new)
				touched = True
		for old, new in HEADER_REPLACEMENTS:
			if old in content:
				content = content.replace(old, new)
				touched = True

		if touched:
			ws.content = content

		for row in ws.number_cards:
			if row.number_card_name in renamed:
				row.number_card_name = renamed[row.number_card_name]
				touched = True
			# label must mirror the name, or the card silently disappears
			if row.label != row.number_card_name:
				row.label = row.number_card_name
				touched = True

		for row in ws.charts:
			if row.chart_name in renamed:
				row.chart_name = renamed[row.chart_name]
				touched = True
			if row.label != row.chart_name:
				row.label = row.chart_name
				touched = True

		# Sidebar links pointing at a renamed report.
		for row in ws.links:
			if row.link_to in renamed:
				old = row.link_to
				row.link_to = renamed[old]
				if row.label == old:
					row.label = renamed[old]
				touched = True

		if touched:
			ws.flags.ignore_permissions = True
			ws.save()
			print("Workspace updated: {0}".format(name))


def _fix_dashboards(renamed):
	for name in frappe.get_all(
		"Dashboard", filters={"module": "Powersoft Property"}, pluck="name"
	):
		dash = frappe.get_doc("Dashboard", name)
		touched = False

		for row in dash.cards:
			if row.card in renamed:
				row.card = renamed[row.card]
				touched = True

		for row in dash.charts:
			if row.chart in renamed:
				row.chart = renamed[row.chart]
				touched = True

		if touched:
			dash.flags.ignore_permissions = True
			dash.save()
			print("Dashboard updated: {0}".format(name))
