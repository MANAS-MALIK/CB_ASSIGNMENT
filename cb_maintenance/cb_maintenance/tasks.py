"""Scheduled jobs for CB Maintenance."""

import frappe
from frappe.utils import getdate, nowdate


def refresh_pm_status_and_notify():
	"""Daily: recompute PM Schedule status and escalate newly-overdue items.

	- Anything past next_due becomes Overdue; due today becomes Due.
	- For items that just flipped to Overdue, notify the assigned technician and
	  their reporting manager (one step up the chain).
	"""
	today = getdate(nowdate())
	schedules = frappe.get_all(
		"PM Schedule",
		filters={"status": ["in", ["Scheduled", "Due", "Overdue"]]},
		fields=["name", "status", "next_due", "assigned_technician", "task", "outlet"],
	)

	newly_overdue = []
	for s in schedules:
		if not s.next_due:
			continue
		due = getdate(s.next_due)
		if due < today:
			new_status = "Overdue"
		elif due == today:
			new_status = "Due"
		else:
			new_status = "Scheduled"

		if new_status != s.status:
			frappe.db.set_value("PM Schedule", s.name, "status", new_status)
			if new_status == "Overdue":
				newly_overdue.append(s)

	for s in newly_overdue:
		_notify_overdue(s)

	frappe.db.commit()
	return {"checked": len(schedules), "newly_overdue": len(newly_overdue)}


def _notify_overdue(schedule):
	tech = schedule.get("assigned_technician")
	recipients = set()
	if tech:
		user, manager = frappe.db.get_value(
			"Maintenance Technician", tech, ["user", "reports_to"]
		) or (None, None)
		if user:
			recipients.add(user)
		if manager:
			mgr_user = frappe.db.get_value("Maintenance Technician", manager, "user")
			if mgr_user:
				recipients.add(mgr_user)

	if not recipients:
		return

	subject = f"PM Overdue: {schedule.get('task')} @ {schedule.get('outlet')}"
	for user in recipients:
		notification = frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"for_user": user,
				"type": "Alert",
				"document_type": "PM Schedule",
				"document_name": schedule.get("name"),
			}
		)
		notification.insert(ignore_permissions=True)
