import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Assessor(Document):
	def before_insert(self):
		# name is derived from unique_id (autoname) so normalise it first
		self.unique_id = (self.unique_id or "").strip().upper()

	def validate(self):
		self.unique_id = (self.unique_id or "").strip().upper()
		if not re.fullmatch(r"[A-Z0-9]{2,10}", self.unique_id):
			frappe.throw(_("Unique ID must be 2-10 letters/digits, e.g. AMF."))

		if self.nik and not re.fullmatch(r"\d{16}", self.nik.strip()):
			frappe.throw(_("NIK must be exactly 16 digits."))

		seen = set()
		for row in self.fees:
			if row.assessment_type in seen:
				frappe.throw(_("Row {0}: duplicate fee for {1}.").format(row.idx, row.assessment_type))
			seen.add(row.assessment_type)
			if flt(row.fee_amount) < 0:
				frappe.throw(_("Row {0}: fee cannot be negative.").format(row.idx))

	def on_update(self):
		self.grant_access()

	def grant_access(self):
		user = frappe.get_doc("User", self.user)
		if "Assessor" not in [r.role for r in user.roles]:
			user.flags.ignore_permissions = True
			user.add_roles("Assessor")

		# User Permission: this login may only ever see its own Assessor record
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": self.user,
				"allow": "Assessor",
				"for_value": self.name,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

	def on_trash(self):
		for up in frappe.get_all("User Permission", filters={"allow": "Assessor", "for_value": self.name}):
			frappe.delete_doc("User Permission", up.name, ignore_permissions=True)


@frappe.whitelist()
def get_fee_for(assessor, assessment_type):
	from assessment_management.utils import get_fee

	frappe.has_permission("Assessor", "read", throw=True)
	return get_fee(assessor, assessment_type)
