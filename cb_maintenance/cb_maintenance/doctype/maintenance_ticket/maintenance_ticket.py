import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from cb_maintenance.cb_maintenance.utils import pick_technician


class MaintenanceTicket(Document):
	def before_save(self):
		self.set_zonal_office()
		self.suggest_spare_part()
		self.auto_assign()
		self.sync_status()

	def set_zonal_office(self):
		if self.outlet and not self.zonal_office:
			self.zonal_office = frappe.db.get_value(
				"Maintenance Outlet", self.outlet, "zonal_office"
			)

	def auto_assign(self):
		# Route to a technician in the outlet's zonal office if not chosen manually.
		if not self.assigned_technician and self.zonal_office:
			self.assigned_technician = pick_technician(self.zonal_office)

	def suggest_spare_part(self):
		"""Match the ticket sub-category text against spare-part keywords.

		e.g. sub_category "Gasket Broken" -> Spare Part with match_keyword "Gasket".
		Prefer a part scoped to the same asset category when available.
		"""
		if self.suggested_spare_part or not self.sub_category:
			return
		text = (self.sub_category or "").lower()
		parts = frappe.get_all(
			"Spare Part",
			filters={"match_keyword": ["is", "set"]},
			fields=["name", "match_keyword", "asset_category"],
		)
		matches = [
			p for p in parts if p.match_keyword and p.match_keyword.lower() in text
		]
		if not matches:
			return
		scoped = [p for p in matches if p.asset_category and p.asset_category == self.asset_category]
		self.suggested_spare_part = (scoped or matches)[0].name

	def sync_status(self):
		if self.status in ("Resolved", "Closed") and not self.resolved_on:
			self.resolved_on = now_datetime()
		if self.assigned_technician and self.status == "Open":
			self.status = "Assigned"

	def after_insert(self):
		self.notify_assignee()

	def on_update(self):
		# Notify when assignment changes after creation.
		if self.has_value_changed("assigned_technician") and not self.flags.in_insert:
			self.notify_assignee()

	def notify_assignee(self):
		if not self.assigned_technician:
			return
		user = frappe.db.get_value(
			"Maintenance Technician", self.assigned_technician, "user"
		)
		if not user:
			return
		# Use Frappe's ToDo/assignment primitive so it shows in the assignee's inbox.
		from frappe.desk.form.assign_to import add as assign_add

		try:
			assign_add(
				{
					"assign_to": [user],
					"doctype": self.doctype,
					"name": self.name,
					"description": self.subject,
				}
			)
		except frappe.DuplicateEntryError:
			pass
