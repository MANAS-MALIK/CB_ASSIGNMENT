import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate
from cb_maintenance.cb_maintenance.utils import next_due_from

class PMTemplate(Document):

    @frappe.whitelist()
    def roll_out_to_outlet(self, outlet, start_date=None):
        start_date = getdate(start_date or nowdate())
        asset_name = frappe.db.get_value('Store Asset', {'outlet': outlet, 'asset_category': self.asset_category}, 'name')
        if not asset_name:
            asset = frappe.get_doc({'doctype': 'Store Asset', 'outlet': outlet, 'asset_category': self.asset_category}).insert()
            asset_name = asset.name
        created = 0
        for task in self.tasks:
            exists = frappe.db.exists('PM Schedule', {'store_asset': asset_name, 'task': task.task})
            if exists:
                continue
            frappe.get_doc({'doctype': 'PM Schedule', 'store_asset': asset_name, 'task': task.task, 'frequency': task.frequency, 'is_inspection': task.is_inspection, 'next_due': next_due_from(start_date, task.frequency)}).insert()
            created += 1
        return {'store_asset': asset_name, 'schedules_created': created}

@frappe.whitelist()
def roll_out_to_all_outlets(template, start_date=None):
    doc = frappe.get_doc('PM Template', template)
    outlets = frappe.get_all('Maintenance Outlet', pluck='name')
    total = 0
    for outlet in outlets:
        result = doc.roll_out_to_outlet(outlet, start_date)
        total += result['schedules_created']
    return {'outlets': len(outlets), 'schedules_created': total}
