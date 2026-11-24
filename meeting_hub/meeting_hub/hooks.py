app_name = "meeting_hub"
app_title = "Meeting Hub"
app_publisher = "Your Company"
app_description = "Online meeting links (Google Meet, Zoom, Microsoft Teams) for Frappe Event"
app_email = "dev@example.com"
app_license = "mit"

required_apps = ["frappe"]

CUSTOM_FIELDS = [
	"custom_online_meeting_section",
	"custom_meeting_platform",
	"custom_meeting_url",
	"custom_meeting_id",
	"custom_meeting_password",
	"custom_meeting_error",
]

fixtures = [
	{"dt": "Custom Field", "filters": [["dt", "=", "Event"], ["fieldname", "in", CUSTOM_FIELDS]]},
]

doc_events = {
	"Event": {
		"after_insert": "meeting_hub.api.enqueue_meeting_creation",
		"on_update": "meeting_hub.api.enqueue_meeting_creation",
	}
}
