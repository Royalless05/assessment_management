import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from assessment_management.utils import (
	BASE_TYPES,
	MIN_NARRATIVE_CHARS,
	get_assessor_for_user,
	get_lock_reason,
	get_schedule_row,
	is_admin,
	narrative_length,
	finish_row,
	require_admin,
	validate_attachment,
	SCHEDULE_DT,
)


class WorkingSheet(Document):
	# ------------------------------------------------------------------ onload
	def onload(self):
		self.set_onload("lock_reason", get_lock_reason(self.assessment, self.assessment_type))
		self.set_onload("is_admin", is_admin())
		self.set_onload("min_chars", MIN_NARRATIVE_CHARS)

	# ---------------------------------------------------------------- validate
	def validate(self):
		self.load_context()
		if not self.flags.ignore_permissions:
			self.check_access()

		if self.is_new():
			self.sheet_status = "Draft"
			self.populate_items()
		else:
			old_status = frappe.db.get_value("Working Sheet", self.name, "sheet_status")
			self.check_lock()
			if old_status == "Finished" and not self.flags.revising:
				frappe.throw(_("This sheet is Finished. Ask an Assessment Admin to press Revise to reopen it."))
			if not (self.flags.finishing or self.flags.revising):
				self.sheet_status = old_status  # status is only changed through the actions below
			self.check_items_unchanged()
			if not self.flags.prefill:
				self.last_autosaved = now_datetime()

		self.validate_values()
		if self.assessment_type == "RW":
			self.compute_suggested_scores()
		if self.assessment_type == "Feedback":
			validate_attachment(self.feedback_photo, ("jpg", "jpeg", "png"), label=_("Photo Evidence"))
		if self.flags.finishing:
			self.validate_for_finish()

	def load_context(self):
		row = get_schedule_row(self.assessment, self.assessment_type)
		if not row:
			frappe.throw(_("Stage {0} does not exist in {1}.").format(self.assessment_type, self.assessment))
		if not row.assessor:
			frappe.throw(_("No assessor is scheduled for {0}.").format(self.assessment_type))
		self.assessor = row.assessor
		self.project, self.assessee = frappe.db.get_value("Assessment", self.assessment, ["project", "assessee"])

	def check_access(self):
		if is_admin():
			return
		if get_assessor_for_user() != self.assessor:
			frappe.throw(_("This Working Sheet is assigned to another assessor."), frappe.PermissionError)

	def check_lock(self):
		reason = get_lock_reason(self.assessment, self.assessment_type)
		if reason:
			frappe.throw(reason)

	def populate_items(self):
		if self.assessment_type == "Feedback":
			return
		from assessment_management.assessment_management.doctype.competency_master.competency_master import (
			build_competency_tree,
		)

		tree = build_competency_tree()
		if not tree:
			frappe.throw(_("Create Competency Master records before scheduling assessments."))
		for comp in tree:
			self.append("items", {"competency": comp["name"]})

	def check_items_unchanged(self):
		db_items = set(frappe.get_all("Working Sheet Item", filters={"parent": self.name}, pluck="competency"))
		if {i.competency for i in self.items} != db_items:
			frappe.throw(_("Competency rows cannot be added or removed."))

	def validate_values(self):
		for it in self.items:
			for f in ("rating", "qc_rating"):
				v = flt(it.get(f))
				if v and not (1 <= v <= 5):
					frappe.throw(_("{0}: {1} must be between 1 and 5.").format(it.competency, it.meta.get_label(f)))

	def compute_suggested_scores(self):
		scores = {}
		for t in BASE_TYPES:
			ws = frappe.db.get_value("Working Sheet", {"assessment": self.assessment, "assessment_type": t}, "name")
			if not ws:
				continue
			for it in frappe.get_all("Working Sheet Item", filters={"parent": ws}, fields=["competency", "rating"]):
				if flt(it.rating):
					scores.setdefault(it.competency, []).append(flt(it.rating))
		for it in self.items:
			vals = scores.get(it.competency)
			it.suggested_score = round(sum(vals) / len(vals), 2) if vals else None

	def validate_for_finish(self):
		t, errors = self.assessment_type, []

		if t in BASE_TYPES:
			for it in self.items:
				if it.flag:  # flagged items are allowed to stay unrated
					continue
				if not flt(it.rating):
					errors.append(_("{0}: Rating is required (or choose a Flag).").format(it.competency))
				if not (it.evidence or "").strip():
					errors.append(_("{0}: Evidence is required (or choose a Flag).").format(it.competency))

		if t == "RW":
			for it in self.items:
				if not flt(it.rating):
					errors.append(_("{0}: Final Rating is required.").format(it.competency))

		if t == "QC":
			for it in self.items:
				if not flt(it.qc_rating):
					errors.append(_("{0}: Final QC Rating is required.").format(it.competency))

		if t in ("RW", "QC"):
			for field, label in (("strength", _("Strength")), ("weakness", _("Weakness"))):
				n = narrative_length(self.get(field))
				if n < MIN_NARRATIVE_CHARS:
					errors.append(
						_("{0} must be at least {1} characters (currently {2}).").format(label, MIN_NARRATIVE_CHARS, n)
					)

		if t == "Feedback":
			if not (self.video_feedback_link or "").strip():
				errors.append(_("Video Feedback Results Link is required."))
			if not self.feedback_photo:
				errors.append(_("Photo evidence is required."))

		if errors:
			frappe.throw("<br>".join(errors), title=_("Cannot Submit and Finish"))

	# ------------------------------------------------------------------ hooks
	def on_update(self):
		if self.flags.in_insert:
			return
		if self.flags.finishing:
			finish_row(self.assessment, self.assessment_type)
			if self.assessment_type == "RW":
				self.prefill_qc()
			return
		row = get_schedule_row(self.assessment, self.assessment_type)
		if row and not row.finished_at and not self.flags.prefill:
			frappe.db.set_value(SCHEDULE_DT, row.name, "status", "In Progress", update_modified=False)

	def prefill_qc(self):
		"""When RW is finished, seed the QC sheet with RW ratings and narrative."""
		name = frappe.db.get_value("Working Sheet", {"assessment": self.assessment, "assessment_type": "QC"}, "name")
		if not name:
			return
		qc = frappe.get_doc("Working Sheet", name)
		if qc.sheet_status == "Finished":
			return
		qc.flags.ignore_permissions = True
		qc.flags.prefill = True
		qc.strength = qc.strength or self.strength
		qc.weakness = qc.weakness or self.weakness
		rw = {i.competency: i.rating for i in self.items}
		for it in qc.items:
			if not flt(it.qc_rating):
				it.qc_rating = rw.get(it.competency)
		qc.save()

	# ---------------------------------------------------------------- actions
	@frappe.whitelist()
	def submit_and_finish(self):
		"""Locks the sheet for the assessor and stamps finished_at on the Assessment stage."""
		self.check_permission("write")
		self.flags.finishing = True
		self.sheet_status = "Finished"
		self.save()
		return self

	@frappe.whitelist()
	def revise(self):
		"""Admin only: reopen a finished sheet. finished_at on the Assessment is untouched."""
		require_admin()
		if frappe.db.get_value("Working Sheet", self.name, "sheet_status") != "Finished":
			frappe.throw(_("Only a Finished sheet can be revised."))
		self.flags.revising = True
		self.sheet_status = "Revision"
		self.save()
		return self
