import frappe
from frappe import _
from frappe.utils import now_datetime

ASSESSMENT_TYPES = ["SPM", "SRB", "PK", "RW", "QC", "Feedback"]
BASE_TYPES = ["SPM", "SRB", "PK"]
ANSWER_TYPES = ["SPM", "SRB", "PK", "Aspirasi Karir", "Tanggung Jawab"]
TOTAL_STAGES = len(ASSESSMENT_TYPES)
MIN_NARRATIVE_CHARS = 1300
SCHEDULE_DT = "Assessment Schedule Result"

ADMIN_ROLES = {"Assessment Admin", "System Manager"}
VIEW_ROLES = ADMIN_ROLES | {"Assessment Admin View"}


def _roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def is_admin(user=None):
	return bool(ADMIN_ROLES & _roles(user))


def is_viewer(user=None):
	return bool(VIEW_ROLES & _roles(user))


def require_admin():
	if not is_admin():
		frappe.throw(_("Only Assessment Admin can perform this action."), frappe.PermissionError)


def require_viewer():
	if not is_viewer():
		frappe.throw(_("You are not permitted to view this."), frappe.PermissionError)


def get_assessor_for_user(user=None):
	return frappe.db.get_value("Assessor", {"user": user or frappe.session.user}, "name")


def get_schedule_row(assessment, assessment_type):
	rows = frappe.get_all(
		SCHEDULE_DT,
		filters={"parent": assessment, "parenttype": "Assessment", "assessment_type": assessment_type},
		fields=["*"],
		limit=1,
	)
	return rows[0] if rows else None


def get_lock_reason(assessment, assessment_type):
	"""RW needs SPM+SRB+PK finished; QC needs RW finished."""
	required = {"RW": BASE_TYPES, "QC": ["RW"]}.get(assessment_type)
	if not required:
		return None
	rows = frappe.get_all(
		SCHEDULE_DT,
		filters={"parent": assessment, "parenttype": "Assessment", "assessment_type": ["in", required]},
		fields=["assessment_type", "finished_at"],
	)
	done = {r.assessment_type for r in rows if r.finished_at}
	missing = [t for t in required if t not in done]
	if missing:
		return _("Locked: {0} must be Finished before {1} can be worked on.").format(
			", ".join(missing), assessment_type
		)
	return None


def get_fee(assessor, assessment_type):
	if not assessor:
		return 0
	return (
		frappe.db.get_value(
			"Assessor Fee",
			{"parent": assessor, "parenttype": "Assessor", "assessment_type": assessment_type},
			"fee_amount",
		)
		or 0
	)


def narrative_length(text):
	return len((text or "").strip())


def validate_attachment(file_url, allowed_exts, max_bytes=1024 * 1024, label="File"):
	if not file_url:
		return
	ext = file_url.rsplit(".", 1)[-1].lower() if "." in file_url else ""
	if ext not in allowed_exts:
		frappe.throw(_("{0}: only {1} files are allowed.").format(label, ", ".join(e.upper() for e in allowed_exts)))
	size = frappe.db.get_value("File", {"file_url": file_url}, "file_size")
	if size and int(size) > max_bytes:
		frappe.throw(_("{0}: file size must not exceed 1 MB.").format(label))


def refresh_parent_progress(assessment):
	rows = frappe.get_all(
		SCHEDULE_DT, filters={"parent": assessment, "parenttype": "Assessment"}, fields=["finished_at"]
	)
	done = sum(1 for r in rows if r.finished_at)
	frappe.db.set_value(
		"Assessment",
		assessment,
		{"completion_progress": f"{done}/{TOTAL_STAGES}", "completed_count": done},
		update_modified=False,
	)
	return done


def finish_row(assessment, assessment_type):
	"""Mark a schedule row as finished. finished_at is never overwritten (Revise keeps it)."""
	row = get_schedule_row(assessment, assessment_type)
	if not row:
		return
	vals = {"status": "Finished"}
	if not row.finished_at:
		vals["finished_at"] = now_datetime()
	if row.payment_status != "Paid":
		vals["payment_status"] = "Need to Be Paid"
		vals["fee_amount"] = get_fee(row.assessor, assessment_type)
	frappe.db.set_value(SCHEDULE_DT, row.name, vals, update_modified=False)
	refresh_parent_progress(assessment)
