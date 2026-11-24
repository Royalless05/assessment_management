"""Automatic online meeting links for assessment schedule rows (needs the meeting_hub app).

Flow: Admin saves a schedule (assessor + Scheduled At) -> an Event with a meeting platform is
created -> meeting_hub generates the join URL in the background -> `on_meeting_created`
copies the URL into the schedule row's Link Meet.
Without meeting_hub or without a Default Meeting Platform nothing here runs and Link Meet
keeps working as before (typed by hand, or the assessor's default Feedback link).
"""

from datetime import timedelta

import frappe
from frappe.utils import cint, get_datetime

from assessment_management.utils import SCHEDULE_DT

SETTINGS = "Online Meeting Settings"


def default_platform():
	if "meeting_hub" not in frappe.get_installed_apps():
		return None
	return frappe.db.get_single_value(SETTINGS, "default_platform") or None


def auto_enabled():
	return bool(default_platform())


def _duration_minutes():
	return cint(frappe.db.get_single_value(SETTINGS, "default_duration_minutes")) or 60


def sync_meetings(assessment):
	"""Called after an Assessment is saved. Creates / replaces meetings for scheduled rows."""
	platform = default_platform()
	if not platform:
		return

	for row in assessment.schedules:
		if row.finished_at or not (row.assessor and row.scheduled_at):
			continue

		existing = frappe.db.get_value(
			"Event", {"custom_assessment_row": row.name}, ["name", "starts_on"], as_dict=True
		)
		if existing:
			if get_datetime(existing.starts_on) == get_datetime(row.scheduled_at):
				continue  # nothing changed
			# Rescheduled: drop the old Event (the old provider meeting is not cancelled) and make a new one
			frappe.delete_doc("Event", existing.name, ignore_permissions=True, force=1)
			frappe.db.set_value(SCHEDULE_DT, row.name, "link_meet", None, update_modified=False)
			row.link_meet = None
		elif row.link_meet:
			continue  # Admin typed a link by hand: respect it

		_create_event(assessment, row, platform)


def _create_event(assessment, row, platform):
	assessee = frappe.db.get_value("Assessee", assessment.assessee, ["full_name", "email"], as_dict=True)
	assessor = frappe.db.get_value("Assessor", row.assessor, ["full_name", "user"], as_dict=True)
	start = get_datetime(row.scheduled_at)

	participants = []
	if assessor and assessor.user:
		participants.append({"reference_doctype": "User", "reference_docname": assessor.user, "email": assessor.user})
	if assessee and assessee.email:
		participants.append(
			{"reference_doctype": "Assessee", "reference_docname": assessment.assessee, "email": assessee.email}
		)

	frappe.get_doc(
		{
			"doctype": "Event",
			"subject": f"{row.assessment_type} - {assessee.full_name} ({assessment.project})",
			"event_type": "Private",
			"status": "Open",
			"starts_on": start,
			"ends_on": start + timedelta(minutes=_duration_minutes()),
			"description": f"Assessment {assessment.name}, stage {row.assessment_type}. Assessor: {assessor.full_name or row.assessor}.",
			"custom_meeting_platform": platform,
			"custom_assessment": assessment.name,
			"custom_assessment_row": row.name,
			"event_participants": participants,
		}
	).insert(ignore_permissions=True)


def remove_events_for_row(row_name):
	for name in frappe.get_all("Event", filters={"custom_assessment_row": row_name}, pluck="name"):
		frappe.delete_doc("Event", name, ignore_permissions=True, force=1)


def remove_events_for_assessment(assessment_name):
	for name in frappe.get_all("Event", filters={"custom_assessment": assessment_name}, pluck="name"):
		frappe.delete_doc("Event", name, ignore_permissions=True, force=1)


# ------------------------------------------------------- hooks from meeting_hub
def on_meeting_created(event):
	row = event.get("custom_assessment_row")
	url = event.get("custom_meeting_url")
	if row and url and frappe.db.exists(SCHEDULE_DT, row):
		frappe.db.set_value(SCHEDULE_DT, row, "link_meet", url, update_modified=False)


def on_meeting_failed(event):
	"""Fallback so Feedback is never left without a link: use the assessor's own default link."""
	row = event.get("custom_assessment_row")
	if not row or not frappe.db.exists(SCHEDULE_DT, row):
		return
	data = frappe.db.get_value(SCHEDULE_DT, row, ["assessment_type", "assessor", "link_meet"], as_dict=True)
	if data.assessment_type == "Feedback" and data.assessor and not data.link_meet:
		link = frappe.db.get_value("Assessor", data.assessor, "default_feedback_link")
		if link:
			frappe.db.set_value(SCHEDULE_DT, row, "link_meet", link, update_modified=False)
