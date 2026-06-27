"""Shared helpers for the CB Maintenance app."""

import frappe
from frappe.utils import add_days, add_months, getdate

# Canonical frequency -> interval. Used to roll next_due forward consistently.
FREQUENCY_DAYS = {
	"Weekly": 7,
}
FREQUENCY_MONTHS = {
	"Monthly": 1,
	"Quarterly": 3,
	"Half-Yearly": 6,
	"Yearly": 12,
}


def next_due_from(base_date, frequency):
	"""Return the next due date after ``base_date`` for the given frequency."""
	base_date = getdate(base_date)
	if frequency in FREQUENCY_DAYS:
		return add_days(base_date, FREQUENCY_DAYS[frequency])
	if frequency in FREQUENCY_MONTHS:
		return add_months(base_date, FREQUENCY_MONTHS[frequency])
	# Unknown / missing frequency: default to monthly so nothing silently stalls.
	frappe.log_error(
		f"Unknown PM frequency '{frequency}', defaulting to Monthly.",
		"CB Maintenance",
	)
	return add_months(base_date, 1)


def get_zonal_office_for_outlet(outlet):
	"""Resolve the zonal office for an outlet name."""
	if not outlet:
		return None
	return frappe.db.get_value("Maintenance Outlet", outlet, "zonal_office")


def pick_technician(zonal_office, prefer_role="Maintenance Incharge"):
	"""Pick a technician to own work in a zonal office.

	Strategy: prefer an active incharge in the office; otherwise the active
	technician in that office with the fewest open assignments (simple load
	balancing). Returns the Maintenance Technician name or None.
	"""
	if not zonal_office:
		return None

	techs = frappe.get_all(
		"Maintenance Technician",
		filters={"zonal_office": zonal_office, "is_active": 1},
		fields=["name", "job_title"],
	)
	if not techs:
		return None

	incharge = [t for t in techs if (t.job_title or "") == prefer_role]
	if incharge:
		return incharge[0].name

	# Load-balance reactive tickets across the remaining technicians.
	def open_load(tech):
		return frappe.db.count(
			"Maintenance Ticket",
			{"assigned_technician": tech, "status": ["not in", ["Resolved", "Closed", "Cancelled"]]},
		)

	techs.sort(key=lambda t: open_load(t.name))
	return techs[0].name
