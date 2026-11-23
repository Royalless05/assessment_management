frappe.pages["assessor-schedules"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Assessor Schedules"), single_column: true });
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const isViewer = ["Assessment Admin", "Assessment Admin View", "System Manager"].some((r) => frappe.user.has_role(r));
	const $body = $('<div style="padding:8px 0"></div>').appendTo(page.main);
	const $f = $('<div class="card" style="padding:12px;margin-bottom:12px;border:1px solid var(--border-color);display:flex;flex-wrap:wrap;gap:8px"></div>').appendTo($body);
	const c = {};
	const mk = (key, df) => {
		c[key] = frappe.ui.form.make_control({ parent: $("<div style='min-width:190px'></div>").appendTo($f), df: Object.assign({ fieldname: key }, df), render_input: true });
	};
	mk("project", { fieldtype: "Link", options: "Assessment Project", label: __("Project") });
	mk("assessee", { fieldtype: "Link", options: "Assessee", label: __("Assessee") });
	mk("assessment_type", { fieldtype: "Select", label: __("Type"), options: ["", "SPM", "SRB", "PK", "RW", "QC", "Feedback"] });
	mk("finished", { fieldtype: "Select", label: __("Finished"), options: ["", "Finished", "Not Finished"] });
	mk("status", { fieldtype: "Select", label: __("Status"), options: ["", "Pending", "In Progress", "Overdue", "Finished"] });
	if (isViewer) mk("assessor", { fieldtype: "Link", options: "Assessor", label: __("Assessor") });
	mk("scheduled_from", { fieldtype: "Date", label: __("Scheduled From") });
	mk("scheduled_to", { fieldtype: "Date", label: __("Scheduled To") });
	mk("finished_from", { fieldtype: "Date", label: __("Finished From") });
	mk("finished_to", { fieldtype: "Date", label: __("Finished To") });
	const $btns = $('<div style="align-self:flex-end"></div>').appendTo($f);
	const $apply = $(`<button class="btn btn-sm btn-primary">${__("Apply Filter")}</button>`).appendTo($btns);
	const $reset = $(`<button class="btn btn-sm btn-default" style="margin-left:6px">${__("Reset")}</button>`).appendTo($btns);
	const $out = $("<div></div>").appendTo($body);

	const badge = (v) => {
		const col = { Finished: "green", Overdue: "red", "In Progress": "blue" }[v] || "gray";
		return `<span class="indicator-pill ${col}">${esc(v)}</span>`;
	};
	function load() {
		const args = {};
		Object.keys(c).forEach((k) => { const v = c[k].get_value(); if (v) args[k] = v; });
		frappe.call({ method: "assessment_management.api.get_assessor_schedules", args, callback: (r) => {
			const rows = r.message || [];
			let h = `<table class="table table-bordered" style="font-size:12px"><thead><tr>${["No", __("Project"), __("Assessee"), __("Type")]
				.concat(isViewer ? [__("Assessor")] : []).concat([__("Scheduled At"), __("Deadline At"), __("Finished At"), __("Status"), ""])
				.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>`;
			rows.forEach((d, i) => {
				let act = "";
				if (d.working_sheet) {
					act = d.locked
						? `<button class="btn btn-xs btn-default" disabled title="${esc(d.lock_reason)}">${__("Working Sheet")}</button>`
						: `<button class="btn btn-xs btn-primary" data-ws="${esc(d.working_sheet)}">${__("Working Sheet")}</button>`;
				}
				h += `<tr><td>${i + 1}</td><td>${esc(d.project)}</td><td>${esc(d.assessee + " - " + d.assessee_name)}</td><td>${esc(d.assessment_type)}</td>` +
					(isViewer ? `<td>${esc(d.assessor)}</td>` : "") +
					`<td>${esc(d.scheduled_at)}</td><td>${esc(d.deadline_at)}</td><td>${esc(d.finished_at)}</td><td>${badge(d.locked && d.status !== "Overdue" ? "Locked" : d.status)}</td><td>${act}</td></tr>`;
			});
			$out.html(h + "</tbody></table>" + (rows.length ? "" : `<p class="text-muted">${__("No schedules found.")}</p>`));
		} });
	}
	$out.on("click", "[data-ws]", function () { frappe.set_route("Form", "Working Sheet", $(this).data("ws")); });
	$apply.on("click", load);
	$reset.on("click", () => { Object.keys(c).forEach((k) => c[k].set_value("")); load(); });
	frappe.pages["assessor-schedules"].on_page_show = load;
};
