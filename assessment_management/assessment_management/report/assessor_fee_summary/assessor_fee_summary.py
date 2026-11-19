import frappe
from frappe import _

from assessment_management.api import _assert_own_or_viewer, fee_summary_data
from assessment_management.utils import get_assessor_for_user, is_viewer


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("From Date and To Date are required."))
	assessor = filters.assessor
	if not is_viewer():
		assessor = get_assessor_for_user()  # an Assessor can only see own fees
	if not assessor:
		frappe.throw(_("Assessor is required."))
	_assert_own_or_viewer(assessor)

	data = fee_summary_data(assessor, filters.from_date, filters.to_date)["rows"]
	columns = [
		{"label": _("Assessment"), "fieldname": "assessment", "fieldtype": "Link", "options": "Assessment", "width": 130},
		{"label": _("Assessee"), "fieldname": "assessee", "fieldtype": "Link", "options": "Assessee", "width": 120},
		{"label": _("Type"), "fieldname": "assessment_type", "fieldtype": "Data", "width": 90},
		{"label": _("Finished At"), "fieldname": "finished_at", "fieldtype": "Datetime", "width": 150},
		{"label": _("Fee"), "fieldname": "fee_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Payment"), "fieldname": "payment_status", "fieldtype": "Data", "width": 120},
		{"label": _("Paid Date"), "fieldname": "paid_date", "fieldtype": "Datetime", "width": 150},
	]
	return columns, data
