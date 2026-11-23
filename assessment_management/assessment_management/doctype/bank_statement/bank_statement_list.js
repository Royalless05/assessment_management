frappe.listview_settings["Bank Statement"] = {
	add_fields: ["attachment", "amount"],
	formatters: {
		attachment(value) {
			return value ? `<a class="btn btn-xs btn-default" href="${frappe.utils.escape_html(value)}" target="_blank">${__("Open")}</a>` : "";
		},
	},
};
