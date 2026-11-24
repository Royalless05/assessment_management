import frappe

ROLES = ["Assessment Admin", "Assessment Admin View", "Assessor"]


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def create_event_fields():
	"""Link an Event back to the assessment schedule row it was made for."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Event": [
				{
					"fieldname": "custom_assessment",
					"fieldtype": "Link",
					"label": "Assessment",
					"options": "Assessment",
					"read_only": 1,
					"insert_after": "event_participants",
				},
				{
					"fieldname": "custom_assessment_row",
					"fieldtype": "Data",
					"label": "Assessment Schedule Row",
					"read_only": 1,
					"hidden": 1,
					"insert_after": "custom_assessment",
				},
			]
		},
		update=True,
	)
