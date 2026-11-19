frappe.pages["assessment-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Assessment Dashboard"), single_column: true });
	const $body = $('<div class="am-dash" style="padding:12px 0"></div>').appendTo(page.main);
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const money = (v) => format_currency(v || 0);

	const card = (label, value, sub) => `
		<div class="col-sm-3" style="margin-bottom:12px"><div class="card" style="padding:14px;border:1px solid var(--border-color);border-radius:8px">
		<div class="text-muted small">${esc(label)}</div><div style="font-size:26px;font-weight:600">${value}</div>
		<div class="text-muted small">${sub || "&nbsp;"}</div></div></div>`;

	const table = (cols, rows) =>
		`<table class="table table-bordered" style="font-size:12px"><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>` +
		rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</table>";

	function load() {
		frappe.call({
			method: "assessment_management.api.get_dashboard",
			callback: (r) => render(r.message),
		});
	}
	page.set_primary_action(__("Refresh"), load);

	function render(d) {
		if (d.mode === "admin") {
			const pct = d.target ? Math.round((100 * d.finished_assessments) / d.target) : 0;
			let h = '<div class="row">' +
				card(__("Assessment Finished vs Target"), `${d.finished_assessments} / ${d.target}`, `${pct}%`) +
				card(__("Assessors Assigned"), d.assessors_assigned) +
				card(__("Paid"), d.paid, money(d.paid_amount)) +
				card(__("Need to Be Paid"), d.need_to_be_paid, money(d.unpaid_amount)) + "</div>";
			h += '<div class="row"><div class="col-sm-8"><h5>' + __("Assessment Completion by Periode") + '</h5><div id="am-chart"></div></div>' +
				'<div class="col-sm-4"><h5>' + __("Assessor KPI") + ` ${esc(d.kpi.month || "")}</h5>` +
				`<p>${__("On Target")}: <b>${d.kpi.on_target}</b><br>${__("Below Target")}: <b>${d.kpi.below_target}</b></p></div></div>`;
			h += "<h5>" + __("Latest Activities") + "</h5>" + table(
				[__("Assessment"), __("Assessee"), __("Type"), __("Assessor"), __("Status"), __("Updated")],
				d.latest.map((x) => [esc(x.assessment), esc(x.assessee), esc(x.type), esc(x.assessor), esc(x.status), esc(x.modified)]));
			$body.html(h);
			if (d.completion_by_period.length) {
				new frappe.Chart("#am-chart", {
					data: { labels: d.completion_by_period.map((x) => x[0]), datasets: [{ name: __("Finished"), values: d.completion_by_period.map((x) => x[1]) }] },
					type: "bar", height: 240, colors: ["#5e64ff"],
				});
			}
		} else {
			let h = '<div class="row">' +
				card(__("Assessment Finished vs Assigned"), `${d.finished} / ${d.assigned}`) +
				card(__("Paid"), d.paid, money(d.paid_amount)) +
				card(__("Need to Be Paid"), d.need_to_be_paid, money(d.unpaid_amount)) + "</div>";
			h += "<h5>" + __("My Schedule") + "</h5>" + table(
				[__("Assessee"), __("Type"), __("Scheduled At"), __("Deadline"), __("Status"), ""],
				d.my_schedule.map((x) => [esc(x.assessee), esc(x.type), esc(x.scheduled_at), esc(x.deadline_at), esc(x.status),
					x.working_sheet ? `<a href="/app/working-sheet/${encodeURIComponent(x.working_sheet)}">${__("Open Working Sheet")}</a>` : ""]));
			$body.html(h);
		}
	}
	load();
};
