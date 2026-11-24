# Meeting Hub

Adds an **Online Meeting** section to the Frappe `Event` DocType. Pick Google Meet, Zoom or
Microsoft Teams, save the Event, and the join link is created in the background.

Setup: open **Online Meeting Settings**, enable the platform(s) and fill the credentials.
Other apps can react to a finished meeting through the hooks `meeting_hub_meeting_created`
and `meeting_hub_meeting_failed` (each receives the Event document).
