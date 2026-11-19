import frappe
from frappe.utils import now_datetime


def mark_overdue():
	"""Hourly: unfinished rows past deadline become Overdue."""
	frappe.db.sql(
		"""
		update `tabAssessment Schedule Result`
		set status = 'Overdue'
		where finished_at is null
		  and deadline_at is not null
		  and deadline_at < %s
		  and status != 'Overdue'
		""",
		now_datetime(),
	)
