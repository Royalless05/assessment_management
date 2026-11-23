import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_first_day


class AssessorKPI(Document):
	def validate(self):
		# one entry per period (month) per assessor
		self.month = get_first_day(self.month)
		clash = frappe.db.exists(
			"Assessor KPI", {"assessor": self.assessor, "month": self.month, "name": ["!=", self.name]}
		)
		if clash:
			frappe.throw(_("A KPI entry for {0} in this period already exists ({1}).").format(self.assessor, clash))
