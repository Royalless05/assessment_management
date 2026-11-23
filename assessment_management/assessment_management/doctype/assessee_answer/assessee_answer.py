import json

import frappe
from frappe import _
from frappe.model.document import Document


def _rows_from_json(raw):
	try:
		data = json.loads(raw or "{}")
	except ValueError:
		return []
	if not isinstance(data, dict):
		return []
	return [{"question": str(q), "answer": "" if a is None else str(a)} for q, a in data.items()]


class AssesseeAnswer(Document):
	"""Answers are typed as plain Question / Answer rows. `answers_json` stays as the
	stored form read by the Working Sheet and written by the importer."""

	def onload(self):
		# Records made by the importer only have JSON; show them as normal rows.
		if not self.get("answers") and self.answers_json:
			for row in _rows_from_json(self.answers_json):
				self.append("answers", row)

	def before_validate(self):
		# Importer / API writes JSON only: fill the rows so the form shows them.
		if self.is_new() and not self.get("answers") and self.answers_json:
			for row in _rows_from_json(self.answers_json):
				self.append("answers", row)

	def validate(self):
		seen, data = set(), {}
		for row in self.get("answers") or []:
			q = (row.question or "").strip()
			if not q:
				continue
			if q.lower() in seen:
				frappe.throw(_("Row {0}: the question \"{1}\" is entered twice.").format(row.idx, q))
			seen.add(q.lower())
			data[q] = (row.answer or "").strip()
		self.answers_json = json.dumps(data, ensure_ascii=False)
