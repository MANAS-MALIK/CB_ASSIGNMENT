frappe.ui.form.on("PM Schedule", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Mark Done"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Mark PM Task Done"),
				fields: [
					{ fieldname: "done_on", label: __("Done On"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldname: "done_by", label: __("Done By"), fieldtype: "Link", options: "Maintenance Technician" },
					{ fieldname: "inspection_failed", label: __("Inspection Failed?"), fieldtype: "Check", depends_on: "eval:" + (frm.doc.is_inspection ? "true" : "false") },
					{ fieldname: "failure_note", label: __("Failure Note"), fieldtype: "Small Text", depends_on: "inspection_failed" },
				],
				primary_action_label: __("Confirm"),
				primary_action(values) {
					frm.call("mark_done", values).then((r) => {
						d.hide();
						frm.reload_doc();
						if (r.message && r.message.corrective_ticket) {
							frappe.msgprint({
								title: __("Corrective Ticket Raised"),
								message: __("Inspection failed - ticket {0} created.", [r.message.corrective_ticket]),
								indicator: "orange",
							});
						}
					});
				},
			});
			d.show();
		});
	},
});
