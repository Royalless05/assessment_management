import frappe

ROLES = ["Assessment Admin", "Assessment Admin View", "Assessor"]


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def create_event_fields():
	"""Custom fields on Event: online meeting section + link back to the schedule row."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	fields, prev = [], "event_participants"
	for fieldname, fieldtype, label, extra in [
		("custom_online_meeting_section", "Section Break", "Online Meeting", {}),
		("custom_meeting_platform", "Select", "Meeting Platform", {"options": "\nGoogle Meet\nZoom\nMicrosoft Teams"}),
		("custom_meeting_url", "Data", "Meeting URL", {"read_only": 1}),
		("custom_meeting_id", "Data", "Meeting ID", {"read_only": 1}),
		("custom_meeting_password", "Data", "Meeting Passcode", {"read_only": 1}),
		("custom_meeting_error", "Small Text", "Meeting Sync Error", {"read_only": 1}),
		("custom_assessment", "Link", "Assessment", {"options": "Assessment", "read_only": 1}),
		("custom_assessment_row", "Data", "Assessment Schedule Row", {"read_only": 1, "hidden": 1}),
	]:
		fields.append(
			{"fieldname": fieldname, "fieldtype": fieldtype, "label": label, "insert_after": prev, **extra}
		)
		prev = fieldname

	create_custom_fields({"Event": fields}, update=True)
