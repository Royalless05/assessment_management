"""Create online meeting links (Google Meet / Zoom / Microsoft Teams) for Event."""

import uuid
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

import frappe
import requests
from frappe import _
from frappe.utils import cint, get_datetime, get_system_timezone

PLATFORMS = ("Google Meet", "Zoom", "Microsoft Teams")
LOCK_SECONDS = 60
HTTP_TIMEOUT = 25


# ------------------------------------------------------------------ doc events
def enqueue_meeting_creation(doc, method=None):
	"""after_insert / on_update of Event. Idempotent: does nothing when a link already exists."""
	platform = doc.get("custom_meeting_platform")
	if not platform or doc.get("custom_meeting_url"):
		return
	if platform not in PLATFORMS:
		return

	if not _acquire_lock(doc.name):
		return

	frappe.enqueue(
		"meeting_hub.api.create_meeting_for_event",
		queue="short",
		event_name=doc.name,
		enqueue_after_commit=True,
	)


def _lock_key(event_name):
	return f"meeting_hub:create:{event_name}"


def _acquire_lock(event_name):
	"""True when this call owns the lock. If Redis cannot be used, fall through (the worker re-checks)."""
	try:
		cache = frappe.cache
		return bool(cache.set(cache.make_key(_lock_key(event_name)), 1, nx=True, ex=LOCK_SECONDS))
	except Exception:
		frappe.log_error(title="Meeting Hub: lock unavailable", message=frappe.get_traceback())
		return True


def _release_lock(event_name):
	try:
		cache = frappe.cache
		cache.delete(cache.make_key(_lock_key(event_name)))
	except Exception:
		pass


# ---------------------------------------------------------------------- worker
def create_meeting_for_event(event_name):
	"""Runs on the 'short' queue."""
	try:
		if not frappe.db.exists("Event", event_name):
			return
		# Row lock + re-check: a second job for the same Event must not create another meeting.
		current_url = frappe.db.get_value("Event", event_name, "custom_meeting_url", for_update=True)
		if current_url:
			return

		doc = frappe.get_doc("Event", event_name)
		platform = doc.get("custom_meeting_platform")
		if platform not in PLATFORMS:
			return

		result = {
			"Google Meet": _create_google_meet,
			"Zoom": _create_zoom_meeting,
			"Microsoft Teams": _create_teams_meeting,
		}[platform](doc)

		doc.db_set(
			{
				"custom_meeting_url": result.get("url") or "",
				"custom_meeting_id": result.get("id") or "",
				"custom_meeting_password": result.get("password") or "",
				"custom_meeting_error": "",
			},
			update_modified=False,
		)
		frappe.db.commit()
		_publish_refresh(event_name)
		_run_hooks("meeting_hub_meeting_created", event_name)
	except Exception as e:
		frappe.db.rollback()
		message = _short_error(e)
		frappe.log_error(title=f"Meeting Hub: could not create meeting for {event_name}", message=frappe.get_traceback())
		try:
			frappe.db.set_value("Event", event_name, "custom_meeting_error", message, update_modified=False)
			frappe.db.commit()
			_publish_refresh(event_name)
			_run_hooks("meeting_hub_meeting_failed", event_name)
		except Exception:
			frappe.log_error(title="Meeting Hub: could not store error", message=frappe.get_traceback())
	finally:
		_release_lock(event_name)


def _short_error(e):
	text = str(e).strip().replace("\n", " ") or e.__class__.__name__
	return text[:300]


def _publish_refresh(event_name):
	frappe.publish_realtime("doc_update", {"doctype": "Event", "name": event_name}, doctype="Event", docname=event_name)


def _run_hooks(hook_name, event_name):
	"""Let other apps react (hook receives the Event document)."""
	for method in frappe.get_hooks(hook_name) or []:
		try:
			frappe.get_attr(method)(frappe.get_doc("Event", event_name))
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Meeting Hub: hook {method} failed", message=frappe.get_traceback())


# ------------------------------------------------------------------- time utils
def _system_tz():
	return ZoneInfo(get_system_timezone())


def _times(doc):
	"""Return (start, end) as timezone-aware datetimes in the system timezone."""
	tz = _system_tz()
	start = get_datetime(doc.starts_on)
	if not start:
		frappe.throw(_("The Event has no start time."))
	end = get_datetime(doc.ends_on) if doc.get("ends_on") else None
	if not end or end <= start:
		minutes = cint(frappe.db.get_single_value("Online Meeting Settings", "default_duration_minutes")) or 60
		end = start + timedelta(minutes=minutes)
	return start.replace(tzinfo=tz), end.replace(tzinfo=tz)


def _utc_iso(dt):
	return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plain(text):
	return frappe.utils.strip_html_tags(text or "").strip()


def _settings():
	return frappe.get_cached_doc("Online Meeting Settings")


def _raise_for(response, provider):
	if response.ok:
		return
	try:
		detail = response.json()
		detail = detail.get("message") or detail.get("error_description") or detail.get("error") or detail
	except ValueError:
		detail = response.text
	frappe.throw(_("{0} returned {1}: {2}").format(provider, response.status_code, str(detail)[:200]))


# -------------------------------------------------------------------- Google Meet
def _create_google_meet(doc):
	if not cint(_settings().google_meet_enabled):
		frappe.throw(_("Google Meet is turned off in Online Meeting Settings."))

	from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object

	calendar_name = doc.get("google_calendar") or frappe.db.get_value(
		"Google Calendar", {"user": doc.owner, "enable": 1}, "name"
	)
	if not calendar_name:
		frappe.throw(_("No enabled Google Calendar found for {0}.").format(doc.owner))
	gcal_doc = frappe.get_doc("Google Calendar", calendar_name)
	if not gcal_doc.enable:
		frappe.throw(_("Google Calendar {0} is not enabled.").format(calendar_name))

	google_calendar, account = get_google_calendar_object(gcal_doc)
	start, end = _times(doc)
	tz_name = get_system_timezone()

	body = {
		"summary": doc.subject,
		"description": _plain(doc.get("description")),
		"start": {"dateTime": start.isoformat(), "timeZone": tz_name},
		"end": {"dateTime": end.isoformat(), "timeZone": tz_name},
		"attendees": [{"email": e} for e in _participant_emails(doc)],
		"conferenceData": {
			"createRequest": {
				"requestId": uuid.uuid4().hex,
				"conferenceSolutionKey": {"type": "hangoutsMeet"},
			}
		},
	}
	created = (
		google_calendar.events()
		.insert(calendarId=account.google_calendar_id, body=body, conferenceDataVersion=1)
		.execute()
	)
	url = created.get("hangoutLink")
	if not url:
		frappe.throw(_("Google did not return a Meet link. Check that the calendar allows Google Meet."))
	return {"url": url, "id": created.get("id")}


def _participant_emails(doc):
	seen, emails = set(), []
	for p in doc.get("event_participants") or []:
		email = (p.get("email") or "").strip()
		if email and email.lower() not in seen:
			seen.add(email.lower())
			emails.append(email)
	return emails


# ------------------------------------------------------------------------- Zoom
def _create_zoom_meeting(doc):
	s = _settings()
	if not cint(s.zoom_enabled):
		frappe.throw(_("Zoom is turned off in Online Meeting Settings."))
	if not (s.zoom_account_id and s.zoom_client_id):
		frappe.throw(_("Zoom Account ID and Client ID are required."))

	token_response = requests.post(
		"https://zoom.us/oauth/token",
		params={"grant_type": "account_credentials", "account_id": s.zoom_account_id},
		auth=(s.zoom_client_id, s.get_password("zoom_client_secret")),
		timeout=HTTP_TIMEOUT,
	)
	_raise_for(token_response, "Zoom")
	token = token_response.json()["access_token"]

	start, end = _times(doc)
	minutes = max(1, int((end - start).total_seconds() // 60))
	response = requests.post(
		f"https://api.zoom.us/v2/users/{s.zoom_user_id or 'me'}/meetings",
		headers={"Authorization": f"Bearer {token}"},
		json={
			"topic": doc.subject,
			"type": 2,
			"start_time": _utc_iso(start),
			"duration": minutes,
			"timezone": "UTC",
			"agenda": _plain(doc.get("description"))[:2000],
		},
		timeout=HTTP_TIMEOUT,
	)
	_raise_for(response, "Zoom")
	data = response.json()
	return {"url": data.get("join_url"), "id": str(data.get("id") or ""), "password": data.get("password")}


# ---------------------------------------------------------------- Microsoft Teams
def _create_teams_meeting(doc):
	s = _settings()
	if not cint(s.teams_enabled):
		frappe.throw(_("Microsoft Teams is turned off in Online Meeting Settings."))
	if not (s.ms_tenant_id and s.ms_client_id and s.ms_organizer_user_id):
		frappe.throw(_("Microsoft Tenant ID, Client ID and Organizer User ID are required."))

	token_response = requests.post(
		f"https://login.microsoftonline.com/{s.ms_tenant_id}/oauth2/v2.0/token",
		data={
			"grant_type": "client_credentials",
			"client_id": s.ms_client_id,
			"client_secret": s.get_password("ms_client_secret"),
			"scope": "https://graph.microsoft.com/.default",
		},
		timeout=HTTP_TIMEOUT,
	)
	_raise_for(token_response, "Microsoft")
	token = token_response.json()["access_token"]

	start, end = _times(doc)
	response = requests.post(
		f"https://graph.microsoft.com/v1.0/users/{s.ms_organizer_user_id}/onlineMeetings",
		headers={"Authorization": f"Bearer {token}"},
		json={"subject": doc.subject, "startDateTime": _utc_iso(start), "endDateTime": _utc_iso(end)},
		timeout=HTTP_TIMEOUT,
	)
	_raise_for(response, "Microsoft Teams")
	data = response.json()
	return {"url": data.get("joinWebUrl"), "id": data.get("id")}
