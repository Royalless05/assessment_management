app_name = "assessment_management"
app_title = "Assessment Management"
app_publisher = "Your Company"
app_description = "Competency assessment management: scheduling, working sheets, QC, fees, KPI"
app_email = "dev@example.com"
app_license = "mit"

required_apps = ["erpnext"]

before_install = "assessment_management.setup.install.create_roles"
after_migrate = "assessment_management.setup.install.create_roles"

# Row/record level restriction for Assessor role (Admin / Admin View see everything)
permission_query_conditions = {
	"Working Sheet": "assessment_management.permissions.working_sheet_query",
	"Assessment": "assessment_management.permissions.assessment_query",
	"Assessee": "assessment_management.permissions.assessee_query",
	"Assessee Answer": "assessment_management.permissions.assessee_answer_query",
}

has_permission = {
	"Working Sheet": "assessment_management.permissions.working_sheet_has_permission",
	"Assessment": "assessment_management.permissions.assessment_has_permission",
}

scheduler_events = {
	"hourly": ["assessment_management.tasks.mark_overdue"],
}

# Available inside Print Formats (Final Report Assessee)
jinja = {"methods": ["assessment_management.api.get_final_report"]}

# Show the app on the desk "Apps" screen (app switcher)
add_to_apps_screen = [
	{
		"name": "assessment_management",
		"logo": "/assets/assessment_management/images/logo.svg",
		"title": "Assessment Management",
		"route": "/app/assessment-management",
		"has_permission": "assessment_management.permissions.has_app_permission",
	}
]
