import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, now_datetime

from assessment_management.integrations.meeting import auto_enabled
from assessment_management.utils import (
	ASSESSMENT_TYPES,
	SCHEDULE_DT,
	TOTAL_STAGES,
	get_fee,
	refresh_parent_progress,
	require_admin,
)

# Fields only the system may change (finishing a sheet, paying, ...).
# Whatever the client sends for them is discarded and restored from the DB.
PROTECTED = ("finished_at", "status", "payment_status", "paid_date", "working_sheet")


class Assessment(Document):
	# Working Sheet links back to Assessment; allow deleting the parent
	ignore_linked_doctypes = ("Working Sheet",)

	def validate(self):
		self.validate_unique()
		self.ensure_stage_rows()
		self.restore_protected_fields()
		self.validate_rows()
		self.apply_fees_and_defaults()
		self.refresh_status()
		self.update_progress()

	def on_update(self):
		self.ensure_working_sheets()
		from assessment_management.integrations.meeting import sync_meetings

		sync_meetings(self)

	def on_trash(self):
		from assessment_management.integrations.meeting import remove_events_for_assessment

		remove_events_for_assessment(self.name)
		for ws in frappe.get_all("Working Sheet", filters={"assessment": self.name}, pluck="name"):
			frappe.delete_doc("Working Sheet", ws, force=1, ignore_permissions=True)

	# ------------------------------------------------------------------ validate
	def validate_unique(self):
		if frappe.db.exists(
			"Assessment", {"project": self.project, "assessee": self.assessee, "name": ["!=", self.name]}
		):
			frappe.throw(_("Assessment for {0} in project {1} already exists.").format(self.assessee, self.project))

	def ensure_stage_rows(self):
		seen = {}
		for r in self.schedules:
			if r.assessment_type in seen:
				frappe.throw(_("Row {0}: duplicate stage {1}.").format(r.idx, r.assessment_type))
			seen[r.assessment_type] = r
		for t in ASSESSMENT_TYPES:
			if t not in seen:
				seen[t] = self.append("schedules", {"assessment_type": t})
		self.schedules = [seen[t] for t in ASSESSMENT_TYPES]
		for i, r in enumerate(self.schedules, 1):
			r.idx = i

	def restore_protected_fields(self):
		self._old = {}
		if not self.is_new():
			self._old = {
				r.name: r
				for r in frappe.get_all(
					SCHEDULE_DT,
					filters={"parent": self.name, "parenttype": "Assessment"},
					fields=["name", "assessor", *PROTECTED],
				)
			}
		for row in self.schedules:
			old = self._old.get(row.name)
			if old:
				for f in PROTECTED:
					row.set(f, old.get(f))
			else:
				row.finished_at = row.paid_date = row.working_sheet = None
				row.status = "Pending"
				row.payment_status = "Not Finished Yet"

	def validate_rows(self):
		for row in self.schedules:
			old = self._old.get(row.name)
			if old and old.finished_at and (row.assessor or None) != (old.assessor or None):
				frappe.throw(
					_("Row {0} ({1}) is already finished. Use 'Delete Finished At' before changing the assessor.").format(
						row.idx, row.assessment_type
					)
				)
			if row.scheduled_at and not row.assessor:
				frappe.throw(_("Row {0} ({1}): assessor is required when a schedule is set.").format(row.idx, row.assessment_type))
			if row.scheduled_at and row.deadline_at and get_datetime(row.deadline_at) < get_datetime(row.scheduled_at):
				frappe.throw(_("Row {0} ({1}): deadline cannot be before the scheduled time.").format(row.idx, row.assessment_type))

	def apply_fees_and_defaults(self):
		for row in self.schedules:
			if row.payment_status != "Paid":  # fee is frozen once paid
				row.fee_amount = get_fee(row.assessor, row.assessment_type)
				if row.assessor and not row.fee_amount:
					frappe.msgprint(
						_("Assessor {0} has no fee configured for {1}.").format(row.assessor, row.assessment_type),
						indicator="orange",
						alert=True,
					)
			if row.assessment_type == "Feedback" and row.assessor and not row.link_meet and not auto_enabled():
				row.link_meet = frappe.db.get_value("Assessor", row.assessor, "default_feedback_link")

	def refresh_status(self):
		now = now_datetime()
		for row in self.schedules:
			if row.finished_at:
				row.status = "Finished"
				row.payment_status = "Paid" if row.paid_date else "Need to Be Paid"
				continue
			row.payment_status = "Not Finished Yet"
			row.paid_date = None
			if row.deadline_at and get_datetime(row.deadline_at) < now:
				row.status = "Overdue"
			elif row.working_sheet and frappe.db.get_value("Working Sheet", row.working_sheet, "last_autosaved"):
				row.status = "In Progress"
			else:
				row.status = "Pending"

	def update_progress(self):
		done = sum(1 for r in self.schedules if r.finished_at)
		self.completed_count = done
		self.completion_progress = f"{done}/{TOTAL_STAGES}"

	# ------------------------------------------------------------ working sheets
	def ensure_working_sheets(self):
		for row in self.schedules:
			if not row.assessor:
				continue
			if row.working_sheet:
				frappe.db.set_value("Working Sheet", row.working_sheet, "assessor", row.assessor, update_modified=False)
				continue
			ws = frappe.get_doc(
				{"doctype": "Working Sheet", "assessment": self.name, "assessment_type": row.assessment_type}
			)
			ws.flags.ignore_permissions = True
			ws.insert()
			frappe.db.set_value(SCHEDULE_DT, row.name, "working_sheet", ws.name, update_modified=False)
			row.working_sheet = ws.name


# ---------------------------------------------------------------- admin actions
def _row_or_throw(assessment, assessment_type):
	from assessment_management.utils import get_schedule_row

	row = get_schedule_row(assessment, assessment_type)
	if not row:
		frappe.throw(_("Stage {0} not found in {1}.").format(assessment_type, assessment))
	return row


@frappe.whitelist()
def upsert_schedule(assessment, assessment_type, assessor, scheduled_at=None, deadline_at=None, link_meet=None):
	"""Create / Edit Schedule."""
	require_admin()
	doc = frappe.get_doc("Assessment", assessment)
	row = next((r for r in doc.schedules if r.assessment_type == assessment_type), None)
	if not row:
		frappe.throw(_("Stage {0} not found.").format(assessment_type))
	row.assessor = assessor
	row.scheduled_at = scheduled_at or None
	row.deadline_at = deadline_at or None
	if link_meet is not None:
		row.link_meet = link_meet
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def delete_schedule(assessment, assessment_type):
	require_admin()
	row = _row_or_throw(assessment, assessment_type)
	if row.finished_at:
		frappe.throw(_("Stage is finished. Use 'Delete Finished At' first."))
	if row.working_sheet:
		sheet_has_data = frappe.db.get_value("Working Sheet", row.working_sheet, "last_autosaved")
		if sheet_has_data:
			frappe.throw(_("The assessor has already started the Working Sheet; the schedule cannot be deleted."))
	from assessment_management.integrations.meeting import remove_events_for_row

	remove_events_for_row(row.name)
	frappe.db.set_value(
		SCHEDULE_DT,
		row.name,
		{"assessor": None, "scheduled_at": None, "deadline_at": None, "link_meet": None,
		 "status": "Pending", "fee_amount": 0, "working_sheet": None},
		update_modified=False,
	)
	if row.working_sheet:
		frappe.delete_doc("Working Sheet", row.working_sheet, force=1, ignore_permissions=True)
	refresh_parent_progress(assessment)


@frappe.whitelist()
def delete_finished_at(assessment, assessment_type):
	"""Reset a finished stage; its Working Sheet becomes editable again."""
	require_admin()
	row = _row_or_throw(assessment, assessment_type)
	if not row.finished_at:
		frappe.throw(_("Stage is not finished."))
	if row.payment_status == "Paid":
		frappe.throw(_("Stage is already Paid. Use 'Delete Paid' first."))
	frappe.db.set_value(
		SCHEDULE_DT,
		row.name,
		{"finished_at": None, "status": "In Progress", "payment_status": "Not Finished Yet"},
		update_modified=False,
	)
	if row.working_sheet:
		frappe.db.set_value("Working Sheet", row.working_sheet, "sheet_status", "Draft", update_modified=False)
	refresh_parent_progress(assessment)


@frappe.whitelist()
def mark_as_paid(assessment, assessment_type, paid_date):
	require_admin()
	row = _row_or_throw(assessment, assessment_type)
	if not row.finished_at:
		frappe.throw(_("Stage is not finished yet."))
	paid = get_datetime(paid_date)
	if paid > now_datetime():
		frappe.throw(_("Paid date cannot be in the future."))
	frappe.db.set_value(
		SCHEDULE_DT, row.name, {"paid_date": paid, "payment_status": "Paid"}, update_modified=False
	)


@frappe.whitelist()
def delete_paid(assessment, assessment_type):
	require_admin()
	row = _row_or_throw(assessment, assessment_type)
	if row.payment_status != "Paid":
		frappe.throw(_("Stage is not marked as Paid."))
	frappe.db.set_value(
		SCHEDULE_DT, row.name, {"paid_date": None, "payment_status": "Need to Be Paid"}, update_modified=False
	)
