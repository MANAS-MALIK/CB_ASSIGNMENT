import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate
from cb_maintenance.cb_maintenance.utils import get_zonal_office_for_outlet, next_due_from, pick_technician

class PMSchedule(Document):

    def before_save(self):
        self.set_status()
        if not self.assigned_technician and self.outlet:
            office = get_zonal_office_for_outlet(self.outlet)
            self.assigned_technician = pick_technician(office)

    def set_status(self):
        if not self.next_due:
            self.status = 'Scheduled'
            return
        today = getdate(nowdate())
        due = getdate(self.next_due)
        if due < today:
            self.status = 'Overdue'
        elif due == today:
            self.status = 'Due'
        else:
            self.status = 'Scheduled'

    @frappe.whitelist()
    def mark_done(self, done_on=None, done_by=None, inspection_failed=0, failure_note=None):
        done_on = getdate(done_on or nowdate())
        self.last_done = done_on
        if done_by:
            self.last_done_by = done_by
        self.next_due = next_due_from(done_on, self.frequency)
        self.set_status()
        self.save()
        ticket = None
        if int(inspection_failed or 0):
            ticket = self.create_corrective_ticket(failure_note)
        return {'next_due': str(self.next_due), 'corrective_ticket': ticket}

    def create_corrective_ticket(self, failure_note=None):
        desc = failure_note or f'Inspection failed during PM: {self.task}'
        ticket = frappe.get_doc({'doctype': 'Maintenance Ticket', 'outlet': self.outlet, 'store_asset': self.store_asset, 'source': 'PM Inspection', 'priority': 'High', 'subject': f'Corrective: {self.task} ({self.asset_category})', 'description': desc}).insert(ignore_permissions=True)
        return ticket.name

def list_view_indicator(doc):
    return {'Overdue': 'red', 'Due': 'orange', 'Scheduled': 'blue', 'Done': 'green'}.get(doc.get('status'), 'gray')
