import frappe
from frappe.model.document import Document

class MaintenanceOutlet(Document):

    def before_save(self):
        if not self.zonal_office and self.city:
            office = frappe.db.get_value('Zonal Office', {'city_code': self.city}, 'name')
            if office:
                self.zonal_office = office
