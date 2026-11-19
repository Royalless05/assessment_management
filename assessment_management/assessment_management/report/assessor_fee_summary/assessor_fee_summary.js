frappe.query_reports["Assessor Fee Summary"] = {
	filters: [
		{ fieldname: "assessor", label: __("Assessor"), fieldtype: "Link", options: "Assessor" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1,
		  default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1,
		  default: frappe.datetime.month_end() },
	],
};
