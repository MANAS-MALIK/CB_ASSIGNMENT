frappe.listview_settings["PM Schedule"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const map = {
			Overdue: ["Overdue", "red", "status,=,Overdue"],
			Due: ["Due", "orange", "status,=,Due"],
			Scheduled: ["Scheduled", "blue", "status,=,Scheduled"],
			Done: ["Done", "green", "status,=,Done"],
		};
		return map[doc.status] || ["Unknown", "gray", ""];
	},
};
