import frappe

from assessment_management.utils import get_assessor_for_user, is_viewer

_ASSIGNED = (
	"select parent from `tabAssessment Schedule Result` "
	"where parenttype = 'Assessment' and assessor = {a}"
)


def _scope(user):
	"""Returns (unrestricted, assessor_name)."""
	user = user or frappe.session.user
	if user == "Administrator" or is_viewer(user):
		return True, None
	return False, get_assessor_for_user(user)


def working_sheet_query(user=None):
	free, a = _scope(user)
	if free:
		return ""
	if not a:
		return "1=0"
	return f"`tabWorking Sheet`.assessor = {frappe.db.escape(a)}"


def assessment_query(user=None):
	free, a = _scope(user)
	if free:
		return ""
	if not a:
		return "1=0"
	return f"`tabAssessment`.name in ({_ASSIGNED.format(a=frappe.db.escape(a))})"


def assessee_query(user=None):
	free, a = _scope(user)
	if free:
		return ""
	if not a:
		return "1=0"
	sub = _ASSIGNED.format(a=frappe.db.escape(a))
	return f"`tabAssessee`.name in (select assessee from `tabAssessment` where name in ({sub}))"


def assessee_answer_query(user=None):
	free, a = _scope(user)
	if free:
		return ""
	if not a:
		return "1=0"
	sub = _ASSIGNED.format(a=frappe.db.escape(a))
	return (
		"`tabAssessee Answer`.assessee in "
		f"(select assessee from `tabAssessment` where name in ({sub}))"
	)


def working_sheet_has_permission(doc, ptype=None, user=None, **kwargs):
	free, a = _scope(user)
	if free:
		return True
	return bool(a and doc.assessor == a)


def assessment_has_permission(doc, ptype=None, user=None, **kwargs):
	free, a = _scope(user)
	if free:
		return True
	if not a or ptype not in ("read", "select", None):
		return False
	return any(r.assessor == a for r in doc.get("schedules") or [])


def has_app_permission():
	"""Controls visibility of the app tile on the desk Apps screen."""
	return bool(is_viewer() or get_assessor_for_user())
