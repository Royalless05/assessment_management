frappe.pages["assessment-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Assessment Dashboard"), single_column: true });
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const money = (v) => format_currency(v || 0);
	const $top = $('<div style="margin:8px 0 12px;max-width:360px"></div>').appendTo(page.main);
	const fProject = frappe.ui.form.make_control({
		parent: $top, df: { fieldtype: "Link", options: "Assessment Project", label: __("Project"), fieldname: "project", change: load },
		render_input: true,
	});
	const $body = $('<div class="am-dash"></div>').appendTo(page.main);

	const card = (cls, label, value, foot, extra) => `
		<div class="col-sm-4" style="margin-bottom:12px"><div class="card" style="padding:16px;border-radius:8px;border:1px solid var(--border-color);height:100%">
		<div class="text-muted small">${esc(label)}</div><div style="font-size:28px;font-weight:600">${value}</div>${extra || ""}
		<div class="text-muted small" style="margin-top:6px">${foot || "&nbsp;"}</div></div></div>`;
	const table = (cols, rows) =>
		`<table class="table table-bordered" style="font-size:12px"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
		rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
	const badge = (v) => `<span class="indicator-pill ${({ Finished: "green", Overdue: "red", "In Progress": "blue" })[v] || "gray"}">${esc(v)}</span>`;
	const section = (title, inner) => `<div class="card" style="padding:14px;margin-bottom:14px;border:1px solid var(--border-color);border-radius:8px"><h5>${title}</h5>${inner}</div>`;

	function load() {
		frappe.call({ method: "assessment_management.api.get_dashboard_v2", args: { project: fProject.get_value() || null }, callback: (r) => render(r.message) });
	}
	page.set_primary_action(__("Refresh"), load);

	function render(d) {
		if (d.mode === "admin") {
			const pct = d.target ? Math.min(100, Math.round((100 * d.finished_assessments) / d.target)) : 0;
			let h = '<div class="row">' +
				card("", __("Assessment Finished"), d.finished_assessments,
					`${__("Project Assessment Target")}: <b>${d.target}</b>`,
					`<div class="progress" style="height:6px;margin-top:6px"><div class="progress-bar" style="width:${pct}%"></div></div>`) +
				card("", __("Assessor Assigned"), d.assessors_assigned, __("Active in this project")) +
				card("", __("Payment Status"), "",
					`${__("Total to be paid")}: <b>${d.paid + d.need_to_be_paid}</b>`,
					`<div style="display:flex;justify-content:space-around;margin-top:4px"><div><div class="text-success" style="font-size:22px;font-weight:600">${d.paid}</div><div class="small">${__("Paid")}</div><div class="small text-muted">${money(d.paid_amount)}</div></div>
					<div><div class="text-warning" style="font-size:22px;font-weight:600">${d.need_to_be_paid}</div><div class="small">${__("Need to be paid")}</div><div class="small text-muted">${money(d.unpaid_amount)}</div></div></div>`) +
				"</div>";
			h += '<div class="row"><div class="col-sm-7">' + section(__("Assessment Completion by Periode"), '<div id="am-chart"></div>' + (d.periods.length ? "" : `<p class="text-muted">${__("No finished assessments yet.")}</p>`)) + "</div>" +
				'<div class="col-sm-5">' + section(__("Latest Activities"), table([__("Date"), __("Assessee"), __("Assessor"), __("Type"), __("Status")],
					d.latest.map((x) => [esc(x.finished_at), esc(x.assessee), esc(x.assessor), esc(x.type), badge(x.status)]))) + "</div></div>";
			h += '<div class="row"><div class="col-sm-7">' + section(__("Assessor Schedules"), '<div class="am-sched"></div>') + "</div>" +
				'<div class="col-sm-5">' + section(__("Assessor KPI"), '<div class="am-kpi-assessor"></div>') + section(__("Assessor Group KPI"), '<div class="am-kpi-group"></div>') + "</div></div>";
			$body.html(h);
			if (d.periods.length) {
				const colors = ["#5e64ff", "#29cd42", "#ffa00a", "#ff5858", "#743ee2", "#98d85b"];
				new frappe.Chart("#am-chart", {
					type: "axis-mixed", height: 260, colors: colors.concat(["#444444"]), axisOptions: { xIsSeries: 1 }, barOptions: { stacked: 1 },
					data: { labels: d.periods, datasets: d.types.map((t) => ({ name: t, chartType: "bar", values: d.stack[t] }))
						.concat([{ name: __("Total"), chartType: "line", values: d.total_by_period }]) },
				});
			}
			scheduleWidget();
			kpiWidget("assessor", ".am-kpi-assessor", "Assessor");
			kpiWidget("group", ".am-kpi-group", "Assessor Group");
		} else {
			let h = '<div class="row">' +
				card("", __("Assessment Finished"), d.finished, `${__("Assessment Assigned")}: <b>${d.assigned}</b>`) +
				card("", __("Payment Status"), "", `${__("Based on completed assessment")}`,
					`<div style="display:flex;justify-content:space-around"><div><div class="text-success" style="font-size:22px;font-weight:600">${d.paid}</div><div class="small">${__("Paid")} (${money(d.paid_amount)})</div></div>
					<div><div class="text-warning" style="font-size:22px;font-weight:600">${d.need_to_be_paid}</div><div class="small">${__("Unpaid")} (${money(d.unpaid_amount)})</div></div></div>`) + "</div>";
			h += section(__("My Schedule"), table([__("Scheduled At"), __("Finished At"), __("Assessee"), __("Type"), __("Status"), ""],
				d.my_schedule.map((x) => [esc(x.scheduled_at), esc(x.finished_at), esc(x.assessee), esc(x.type), badge(x.status),
					x.working_sheet ? `<a class="btn btn-xs btn-primary" href="/app/working-sheet/${encodeURIComponent(x.working_sheet)}">${__("Sheet")}</a>` : ""])));
			$body.html(h);
		}
	}

	function scheduleWidget() {
		const $w = $body.find(".am-sched");
		const $bar = $('<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px"></div>').appendTo($w);
		const cA = frappe.ui.form.make_control({ parent: $("<div style='min-width:200px'></div>").appendTo($bar), df: { fieldtype: "Link", options: "Assessor", label: __("Select Assessor"), fieldname: "a", change: draw }, render_input: true });
		const cM = frappe.ui.form.make_control({ parent: $("<div style='min-width:160px'></div>").appendTo($bar), df: { fieldtype: "Date", label: __("Month (any day)"), fieldname: "m", change: draw }, render_input: true });
		const $out = $("<div></div>").appendTo($w);
		function draw() {
			if (!cA.get_value()) { $out.html(`<p class="text-muted">${__("Select an assessor to view schedule")}</p>`); return; }
			const args = { assessor: cA.get_value(), project: fProject.get_value() || null };
			if (cM.get_value()) {
				args.scheduled_from = moment(cM.get_value()).startOf("month").format("YYYY-MM-DD");
				args.scheduled_to = moment(cM.get_value()).endOf("month").format("YYYY-MM-DD");
			}
			frappe.call({ method: "assessment_management.api.get_assessor_schedules", args, callback: (r) => {
				$out.html(table([__("Scheduled At"), __("Finished At"), __("Assessee"), __("Type"), __("Status"), __("Action")],
					(r.message || []).slice(0, 25).map((x) => [esc(x.scheduled_at), esc(x.finished_at), esc(x.assessee_name), esc(x.assessment_type), badge(x.status),
						x.working_sheet ? `<a class="btn btn-xs btn-primary" href="/app/working-sheet/${encodeURIComponent(x.working_sheet)}">${__("Sheet")}</a>` : ""])));
			} });
		}
		draw();
	}

	function kpiWidget(kind, sel, doctype) {
		const $w = $body.find(sel);
		const $bar = $('<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px"></div>').appendTo($w);
		const cK = frappe.ui.form.make_control({ parent: $("<div style='min-width:170px'></div>").appendTo($bar), df: { fieldtype: "Link", options: doctype, label: __("Select") + " " + __(doctype), fieldname: "k", change: draw }, render_input: true });
		const cM = frappe.ui.form.make_control({ parent: $("<div style='min-width:150px'></div>").appendTo($bar), df: { fieldtype: "Date", label: __("Month (any day)"), fieldname: "m", change: draw }, render_input: true });
		const $out = $("<div></div>").appendTo($w);
		const id = "am-donut-" + kind;
		function draw() {
			if (!cK.get_value() || !cM.get_value()) { $out.html(`<p class="text-muted small">${__("Choose a name and a month.")}</p>`); return; }
			frappe.call({ method: "assessment_management.api.get_kpi_summary", args: { kind, key: cK.get_value(), month: cM.get_value().slice(0, 7) }, callback: (r) => {
				const { labels, values } = r.message;
				if (!values) { $out.html(`<div id="${id}"></div><p class="text-muted small">${__("No data")}</p>`); return; }
				const keys = Object.keys(labels);
				const on = keys.filter((k) => values[k] === "On Target").length, below = keys.filter((k) => values[k] === "Below Target").length;
				$out.html(`<div id="${id}"></div><ul class="small" style="margin-top:6px;padding-left:16px">${keys.map((k) => `<li>${esc(labels[k])}: <b>${esc(values[k] || "-")}</b></li>`).join("")}</ul>`);
				new frappe.Chart("#" + id, { type: "donut", height: 160, colors: ["#29cd42", "#ff5858"], data: { labels: [__("On Target"), __("Below Target")], datasets: [{ values: [on, below] }] } });
			} });
		}
		draw();
	}
	load();
};
