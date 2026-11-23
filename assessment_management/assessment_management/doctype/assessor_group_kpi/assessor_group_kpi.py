import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_first_day


class AssessorGroupKPI(Document):
	def validate(self):
		# one entry per period (month) per group
		self.month = get_first_day(self.month)
		clash = frappe.db.exists(
			"Assessor Group KPI",
			{"assessor_group": self.assessor_group, "month": self.month, "name": ["!=", self.name]},
		)
		if clash:
			frappe.throw(_("A KPI entry for {0} in this period already exists ({1}).").format(self.assessor_group, clash))
