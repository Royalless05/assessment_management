"""Whitelisted API: import, sheet context, dashboards, monitoring, final report, fee summary."""
import csv
import io
import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime

from assessment_management.utils import (
	ANSWER_TYPES,
	ASSESSMENT_TYPES,
	BASE_TYPES,
	TOTAL_STAGES,
	get_assessor_for_user,
	get_lock_reason,
	is_viewer,
	require_admin,
	require_viewer,
)

ROW_SQL = """
	select p.name as assessment, p.project, p.assessee, c.name as row_name, c.assessment_type,
	       c.assessor, c.status, c.scheduled_at, c.deadline_at, c.finished_at, c.fee_amount,
	       c.payment_status, c.paid_date, c.working_sheet, c.modified
	from `tabAssessment` p
	join `tabAssessment Schedule Result` c on c.parent = p.name and c.parenttype = 'Assessment'
	where 1=1 {cond}
"""


def _rows(project=None, assessee=None, assessor=None, status=None):
	cond, vals = "", {}
	for key, col, val in (
		("project", "p.project", project),
		("assessee", "p.assessee", assessee),
		("assessor", "c.assessor", assessor),
		("status", "c.status", status),
	):
		if val:
			cond += f" and {col} = %({key})s"
			vals[key] = val
	return frappe.db.sql(ROW_SQL.format(cond=cond), vals, as_dict=True)


# ============================================================ Import Answer Assessee
@frappe.whitelist()
def import_answers(project, assessment_type, file_url, overwrite=1):
	"""Bulk import raw answers. First column = assessee_id, every other column = a question."""
	require_admin()
	if assessment_type not in ANSWER_TYPES:
		frappe.throw(_("Assessment Type must be one of: {0}").format(", ".join(ANSWER_TYPES)))
	if not frappe.db.exists("Assessment Project", project):
		frappe.throw(_("Project {0} not found.").format(project))

	ext = file_url.rsplit(".", 1)[-1].lower()
	if ext == "xlsx":
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		rows = read_xlsx_file_from_attached_file(file_url=file_url)
	elif ext == "csv":
		content = frappe.get_doc("File", {"file_url": file_url}).get_content()
		if isinstance(content, bytes):
			content = content.decode("utf-8-sig")
		rows = list(csv.reader(io.StringIO(content)))
	else:
		frappe.throw(_("Only .xlsx or .csv files are supported."))

	if not rows or len(rows) < 2:
		frappe.throw(_("The file has no data rows."))

	header = [str(h or "").strip() for h in rows[0]]
	key_idx = next((i for i, h in enumerate(header) if h.lower().replace(" ", "_") == "assessee_id"), None)
	if key_idx is None:
		frappe.throw(_("The first row must contain an 'assessee_id' column."))

	result = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
	for n, raw in enumerate(rows[1:], start=2):
		assessee = str(raw[key_idx] or "").strip() if len(raw) > key_idx else ""
		if not assessee:
			continue
		if not frappe.db.exists("Assessee", assessee):
			result["errors"].append(_("Row {0}: assessee {1} not found.").format(n, assessee))
			continue
		answers = {
			header[i]: ("" if v is None else str(v))
			for i, v in enumerate(raw)
			if i != key_idx and i < len(header) and header[i]
		}
		existing = frappe.db.get_value(
			"Assessee Answer", {"project": project, "assessee": assessee, "assessment_type": assessment_type}
		)
		if existing:
			if not cint(overwrite):
				result["skipped"] += 1
				continue
			frappe.db.set_value("Assessee Answer", existing, "answers_json", json.dumps(answers, ensure_ascii=False))
			result["updated"] += 1
		else:
			frappe.get_doc(
				{
					"doctype": "Assessee Answer",
					"project": project,
					"assessee": assessee,
					"assessment_type": assessment_type,
					"answers_json": json.dumps(answers, ensure_ascii=False),
				}
			).insert()
			result["created"] += 1
	return result


# ============================================================ Working Sheet context
def _sheet_results(assessment, assessment_type):
	ws = frappe.db.get_value(
		"Working Sheet",
		{"assessment": assessment, "assessment_type": assessment_type},
		["name", "sheet_status", "ig_notes", "qc_notes", "strength", "weakness"],
		as_dict=True,
	)
	if not ws:
		return None
	ws["items"] = frappe.get_all(
		"Working Sheet Item",
		filters={"parent": ws.name},
		fields=["competency", "rating", "suggested_score", "qc_rating", "flag", "evidence", "analysis",
		        "assessor_notes", "qc_notes"],
		order_by="idx asc",
	)
	return ws


@frappe.whitelist()
def get_sheet_context(name):
	from assessment_management.assessment_management.doctype.competency_master.competency_master import (
		build_competency_tree,
	)

	ws = frappe.get_doc("Working Sheet", name)
	ws.check_permission("read")

	answers = []
	if ws.assessment_type in BASE_TYPES:
		wanted = [ws.assessment_type, "Aspirasi Karir", "Tanggung Jawab"]
		for t in wanted:
			ans = frappe.db.get_value(
				"Assessee Answer",
				{"project": ws.project, "assessee": ws.assessee, "assessment_type": t},
				"answers_json",
			)
			if ans:
				answers.append({"type": t, "qa": list(json.loads(ans).items())})

	previous = {}
	prev_types = {"RW": BASE_TYPES, "QC": BASE_TYPES + ["RW"]}.get(ws.assessment_type, [])
	for t in prev_types:
		previous[t] = _sheet_results(ws.assessment, t)

	return {
		"answers": answers,
		"competencies": build_competency_tree(),
		"previous": previous,
		"lock_reason": get_lock_reason(ws.assessment, ws.assessment_type),
	}


@frappe.whitelist()
def get_result_summary(assessment):
	"""Matrix of competency vs Level 1-5 (Feedback popup)."""
	require_viewer_or_assigned(assessment)
	qc, rw = _sheet_results(assessment, "QC"), _sheet_results(assessment, "RW")
	final = {}
	for it in (rw or {}).get("items", []):
		if flt(it.rating):
			final[it.competency] = flt(it.rating)
	for it in (qc or {}).get("items", []):
		if flt(it.qc_rating):
			final[it.competency] = flt(it.qc_rating)
	names = frappe.get_all("Competency Master", order_by="sort_order asc, creation asc", pluck="name")
	return [
		{"competency": n, "final_rating": final.get(n), "level": round(final[n]) if n in final else None}
		for n in names
	]


def require_viewer_or_assigned(assessment):
	if is_viewer():
		return
	frappe.get_doc("Assessment", assessment).check_permission("read")


# ================================================================== Dashboards
@frappe.whitelist()
def get_dashboard():
	if is_viewer():
		return {"mode": "admin", **_admin_dashboard()}
	assessor = get_assessor_for_user()
	if not assessor:
		frappe.throw(_("No Assessor profile is linked to your user."), frappe.PermissionError)
	return {"mode": "assessor", **_assessor_dashboard(assessor)}


def _admin_dashboard():
	rows = _rows()
	target = sum(cint(t) for t in frappe.get_all("Assessment Project", pluck="target_data"))
	done_assessments = frappe.db.count("Assessment", {"completed_count": TOTAL_STAGES})

	by_month = {}
	for r in rows:
		if r.finished_at:
			k = r.finished_at.strftime("%Y-%m")
			by_month[k] = by_month.get(k, 0) + 1

	kpi_rows = frappe.get_all("Assessor KPI", fields=["month", "jumlah_simulasi", "kualitas_observasi",
		"konsistensi_pelaporan", "kepatuhan_administratif", "feedback_peserta"], order_by="month desc", limit=500)
	kpi = {"on_target": 0, "below_target": 0, "month": None}
	if kpi_rows:
		kpi["month"] = str(kpi_rows[0].month)
		for k in (x for x in kpi_rows if str(x.month) == kpi["month"]):
			for f in ("jumlah_simulasi", "kualitas_observasi", "konsistensi_pelaporan",
			          "kepatuhan_administratif", "feedback_peserta"):
				if k.get(f) == "On Target":
					kpi["on_target"] += 1
				elif k.get(f) == "Below Target":
					kpi["below_target"] += 1

	latest = sorted(rows, key=lambda r: r.modified, reverse=True)[:10]
	return {
		"finished_assessments": done_assessments,
		"target": target,
		"assessors_assigned": len({r.assessor for r in rows if r.assessor}),
		"paid": sum(1 for r in rows if r.payment_status == "Paid"),
		"need_to_be_paid": sum(1 for r in rows if r.payment_status == "Need to Be Paid"),
		"paid_amount": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Paid"),
		"unpaid_amount": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Need to Be Paid"),
		"completion_by_period": sorted(by_month.items()),
		"latest": [
			{"assessment": r.assessment, "assessee": r.assessee, "type": r.assessment_type,
			 "assessor": r.assessor, "status": r.status, "modified": str(r.modified)}
			for r in latest
		],
		"kpi": kpi,
	}


def _assessor_dashboard(assessor):
	rows = _rows(assessor=assessor)
	schedule = sorted(
		[r for r in rows if r.status != "Finished"],
		key=lambda r: (r.scheduled_at is None, r.scheduled_at),
	)
	return {
		"assessor": assessor,
		"assigned": len(rows),
		"finished": sum(1 for r in rows if r.status == "Finished"),
		"paid": sum(1 for r in rows if r.payment_status == "Paid"),
		"need_to_be_paid": sum(1 for r in rows if r.payment_status == "Need to Be Paid"),
		"paid_amount": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Paid"),
		"unpaid_amount": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Need to Be Paid"),
		"my_schedule": [
			{"assessment": r.assessment, "assessee": r.assessee, "type": r.assessment_type,
			 "scheduled_at": str(r.scheduled_at or ""), "deadline_at": str(r.deadline_at or ""),
			 "status": r.status, "working_sheet": r.working_sheet}
			for r in schedule
		],
	}


# ================================================================== Monitoring
MONITOR_TABS = ("assessee", "assessor", "type", "schedule", "matrix")


def _monitoring(tab, project=None, assessee=None, assessor=None, status=None):
	rows = _rows(project, assessee, assessor, status)
	names = dict(frappe.get_all("Assessee", fields=["name", "full_name"], as_list=True))

	def agg(group_rows):
		total = len(group_rows)
		fin = sum(1 for r in group_rows if r.status == "Finished")
		return total, fin, total - fin, sum(1 for r in group_rows if r.status == "Overdue")

	groups = {}
	if tab == "assessee":
		for r in rows:
			groups.setdefault((r.assessment, r.project, r.assessee), []).append(r)
		cols = [("assessment", "Assessment"), ("project", "Project"), ("assessee", "Assessee"),
		        ("target", "Target"), ("finished", "Finished"), ("remaining", "Remaining"),
		        ("overdue", "Overdue"), ("progress", "Progress %")]
		data = []
		for (a, p, e), g in groups.items():
			t, f, rem, od = agg(g)
			data.append({"assessment": a, "project": p, "assessee": f"{e} - {names.get(e, '')}",
			             "target": t, "finished": f, "remaining": rem, "overdue": od,
			             "progress": round(100 * f / t) if t else 0})
	elif tab == "assessor":
		for r in rows:
			if r.assessor:
				groups.setdefault(r.assessor, []).append(r)
		cols = [("assessor", "Assessor"), ("assigned", "Assigned"), ("finished", "Finished"),
		        ("remaining", "Remaining"), ("overdue", "Overdue")]
		data = []
		for a, g in groups.items():
			t, f, rem, od = agg(g)
			data.append({"assessor": a, "assigned": t, "finished": f, "remaining": rem, "overdue": od})
	elif tab == "type":
		cols = [("type", "Type"), ("assigned", "Assigned"), ("unassigned", "Unassigned"),
		        ("finished", "Finished"), ("remaining", "Remaining"), ("overdue", "Overdue")]
		data = []
		for t in ASSESSMENT_TYPES:
			g = [r for r in rows if r.assessment_type == t]
			assigned = [r for r in g if r.assessor]
			_t, f, rem, od = agg(assigned)
			data.append({"type": t, "assigned": len(assigned), "unassigned": len(g) - len(assigned),
			             "finished": f, "remaining": rem, "overdue": od})
	elif tab == "schedule":
		cols = [("assessment", "Assessment"), ("assessee", "Assessee"), ("type", "Type"),
		        ("assessor", "Assessor"), ("scheduled_at", "Scheduled At"), ("deadline_at", "Deadline At"),
		        ("finished_at", "Finished At"), ("status", "Status"), ("payment_status", "Payment")]
		data = [
			{"assessment": r.assessment, "assessee": f"{r.assessee} - {names.get(r.assessee, '')}",
			 "type": r.assessment_type, "assessor": r.assessor or "", "scheduled_at": str(r.scheduled_at or ""),
			 "deadline_at": str(r.deadline_at or ""), "finished_at": str(r.finished_at or ""),
			 "status": r.status, "payment_status": r.payment_status}
			for r in sorted(rows, key=lambda r: (r.scheduled_at is None, r.scheduled_at))
		]
	elif tab == "matrix":
		cols = [("assessee", "Assessee"), ("project", "Project")] + [(t, t) for t in ASSESSMENT_TYPES]
		pivot = {}
		for r in rows:
			d = pivot.setdefault(r.assessment, {"assessee": f"{r.assessee} - {names.get(r.assessee, '')}",
			                                    "project": r.project})
			d[r.assessment_type] = r.status
		data = list(pivot.values())
	else:
		frappe.throw(_("Unknown tab {0}").format(tab))
	return {"columns": [{"fieldname": f, "label": l} for f, l in cols], "data": data}


@frappe.whitelist()
def get_monitoring(tab, project=None, assessee=None, assessor=None, status=None):
	require_viewer()
	return _monitoring(tab, project, assessee, assessor, status)


@frappe.whitelist()
def export_monitoring(tab, filters=None, file_type="xlsx"):
	require_viewer()
	f = json.loads(filters) if filters else {}
	res = _monitoring(tab, f.get("project"), f.get("assessee"), f.get("assessor"), f.get("status"))
	table = [[c["label"] for c in res["columns"]]]
	for d in res["data"]:
		table.append([d.get(c["fieldname"], "") for c in res["columns"]])
	title = f"assessment_monitoring_{tab}"
	if file_type == "csv":
		frappe.response["result"] = table
		frappe.response["type"] = "csv"
		frappe.response["doctype"] = title
	else:
		from frappe.utils.xlsxutils import make_xlsx

		frappe.response["filename"] = f"{title}.xlsx"
		frappe.response["filecontent"] = make_xlsx(table, "Monitoring").getvalue()
		frappe.response["type"] = "binary"


# ================================================================ Final Report
@frappe.whitelist()
def get_final_report(assessment):
	"""Data for the Final Report Assessee (page, print format, PDF)."""
	require_viewer()
	doc = frappe.get_doc("Assessment", assessment)
	res = {t: _sheet_results(assessment, t) for t in ("SPM", "SRB", "PK", "RW", "QC")}

	flags = {}
	for t in BASE_TYPES:
		for it in (res[t] or {}).get("items", []):
			if it.flag:
				flags[it.flag] = flags.get(it.flag, 0) + 1

	competence = []
	for name in frappe.get_all("Competency Master", order_by="sort_order asc, creation asc", pluck="name"):
		line = {"competency": name}
		for t in BASE_TYPES:
			line[t] = next((i.rating for i in (res[t] or {}).get("items", []) if i.competency == name), None)
		line["IG"] = next((i.rating for i in (res["RW"] or {}).get("items", []) if i.competency == name), None)
		line["QC"] = next((i.qc_rating for i in (res["QC"] or {}).get("items", []) if i.competency == name), None)
		competence.append(line)

	narrative = res["QC"] if res["QC"] and res["QC"].sheet_status == "Finished" else res["RW"]
	return {
		"assessment": doc.name,
		"project": doc.project,
		"assessee": frappe.db.get_value("Assessee", doc.assessee, ["assessee_id", "full_name", "email"], as_dict=True),
		"progress": doc.completion_progress,
		"stages": [{"type": r.assessment_type, "assessor": r.assessor, "status": r.status,
		            "finished_at": r.finished_at} for r in doc.schedules],
		"flag_distribution": flags,
		"competence": competence,
		"strength": (narrative or {}).get("strength"),
		"weakness": (narrative or {}).get("weakness"),
	}


# ============================================================= Fee Summary / KPI
def fee_summary_data(assessor, from_date, to_date):
	rows = frappe.db.sql(
		"""
		select p.name as assessment, p.assessee, c.assessment_type, c.finished_at, c.fee_amount,
		       c.payment_status, c.paid_date
		from `tabAssessment` p
		join `tabAssessment Schedule Result` c on c.parent = p.name and c.parenttype = 'Assessment'
		where c.assessor = %(assessor)s and c.finished_at is not null
		  and date(c.finished_at) between %(from_date)s and %(to_date)s
		order by c.finished_at
		""",
		{"assessor": assessor, "from_date": getdate(from_date), "to_date": getdate(to_date)},
		as_dict=True,
	)
	by_type = {}
	for r in rows:
		d = by_type.setdefault(r.assessment_type, {"type": r.assessment_type, "count": 0, "amount": 0})
		d["count"] += 1
		d["amount"] += flt(r.fee_amount)
	return {
		"rows": rows,
		"by_type": list(by_type.values()),
		"total": sum(flt(r.fee_amount) for r in rows),
		"paid": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Paid"),
		"unpaid": sum(flt(r.fee_amount) for r in rows if r.payment_status == "Need to Be Paid"),
	}


@frappe.whitelist()
def get_fee_summary(assessor, from_date, to_date):
	_assert_own_or_viewer(assessor)
	return fee_summary_data(assessor, from_date, to_date)


def _assert_own_or_viewer(assessor):
	if not is_viewer() and get_assessor_for_user() != assessor:
		frappe.throw(_("Not permitted."), frappe.PermissionError)


@frappe.whitelist()
def get_assessor_report(assessor, month=None, status=None):
	"""Profile + Working Sheet list (month = YYYY-MM)."""
	require_viewer()
	profile = frappe.db.get_value(
		"Assessor", assessor,
		["name", "full_name", "user", "unique_id", "phone", "bank_name", "bank_account_number",
		 "bank_account_name", "default_feedback_link"], as_dict=True)
	rows = _rows(assessor=assessor, status=status)
	if month:
		rows = [r for r in rows if r.scheduled_at and r.scheduled_at.strftime("%Y-%m") == month]
	kpi = frappe.get_all("Assessor KPI", filters={"assessor": assessor},
	                     fields=["month", "jumlah_simulasi", "kualitas_observasi", "konsistensi_pelaporan",
	                             "kepatuhan_administratif", "feedback_peserta"], order_by="month desc")
	return {"profile": profile, "sheets": rows, "kpi": kpi}
