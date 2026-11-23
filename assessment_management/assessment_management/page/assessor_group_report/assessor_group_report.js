frappe.pages["assessor-group-report"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Report Assessor Group"), single_column: true });
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const isAdmin = () => frappe.user.has_role("Assessment Admin") || frappe.user.has_role("System Manager");
	const $body = $('<div style="padding:8px 0"></div>').appendTo(page.main);
	const table = (cols, rows) =>
		`<table class="table table-bordered" style="font-size:12px"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
		rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody></table>";

	function showList() {
		page.clear_actions();
		page.set_title(__("Report Assessor Group"));
		$body.empty();
		const $search = $(`<input class="form-control" style="max-width:260px;margin-bottom:10px" placeholder="${__("Search group")}">`).appendTo($body);
		const $out = $("<div></div>").appendTo($body);
		let data = [];
		function draw() {
			const q = ($search.val() || "").toLowerCase();
			const rows = data.filter((g) => !q || (g.group_name || "").toLowerCase().includes(q));
			$out.html(table(["No", __("Group Name"), __("Project"), __("Members"), ""], rows.map((g, i) => [
				i + 1, esc(g.group_name), esc(g.project),
				"<ul style='margin:0;padding-left:16px'>" + g.members.map((m) => `<li>${esc(m)}</li>`).join("") + "</ul>",
				`<a class="btn btn-xs btn-default" href="/app/assessor-group-report/${encodeURIComponent(g.name)}">${__("Detail")}</a>`])));
		}
		$search.on("input", draw);
		frappe.call({ method: "assessment_management.api.get_group_list", callback: (r) => { data = r.message || []; draw(); } });
	}

	function showDetail(name) {
		page.clear_actions();
		page.set_title(__("Report Assessor Group"));
		page.set_secondary_action(__("Back"), () => frappe.set_route("assessor-group-report"));
		$body.empty();
		frappe.call({ method: "assessment_management.api.get_group_detail", args: { name }, callback: (r) => {
			const g = r.message;
			$body.append(`<div class="card" style="padding:14px;margin-bottom:14px;border:1px solid var(--border-color)"><h5>${__("Group Info")}</h5>
				<div><b>${__("Name")}:</b> ${esc(g.group_name)}</div><div><b>${__("Project")}:</b> ${esc(g.project)}</div></div>`);
			$body.append(`<h5>${__("Group Members")}</h5>` + table([__("Name"), __("Email"), __("Unique ID")],
				g.members.map((m) => [esc(m.name), esc(m.email), esc(m.unique_id)])));
			$body.append(`<h5 style="margin-top:18px">${__("Group KPI")}</h5>`);
			const $kpi = $("<div></div>").appendTo($body);
			function load() {
				frappe.call({ method: "assessment_management.api.get_kpi", args: { kind: "group", key: name }, callback: (r2) => {
					const L = r2.message.labels, KF = Object.keys(L);
					const tag = (v) => (v ? `<span class="indicator-pill ${v === "On Target" ? "green" : "red"}">${esc(v)}</span>` : "-");
					$kpi.html(table(["#", __("Period")].concat(KF.map((k) => L[k])).concat(isAdmin() ? [__("Action")] : []),
						r2.message.rows.map((x, i) => [i + 1, esc(x.label)].concat(KF.map((k) => tag(x[k]))).concat(isAdmin() ?
							[`<button class="btn btn-xs btn-warning" data-edit="${esc(x.name)}">${__("Edit")}</button> <button class="btn btn-xs btn-danger" data-del="${esc(x.name)}">${__("Delete")}</button>`] : []))));
					$kpi.data("rows", r2.message.rows);
				} });
			}
			function dialog(row) {
				const opts = "\nOn Target\nBelow Target";
				const d = new frappe.ui.Dialog({
					title: row ? __("Edit KPI Entry") : __("Add KPI Entry"),
					fields: [{ fieldname: "month", fieldtype: "Date", label: __("Period (any day of the month)"), reqd: 1, default: row && row.month },
						...["jumlah_simulasi", "kualitas_observasi", "konsistensi_pelaporan", "kepatuhan_administratif", "feedback_peserta"].map((f) => ({
							fieldname: f, fieldtype: "Select", options: opts, label: __(f.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ")), default: row && row[f] })),
						{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks"), default: row && row.remarks }],
					primary_action_label: __("Save KPI"),
					primary_action(v) {
						frappe.call({ method: "assessment_management.api.save_kpi", args: { kind: "group", key: name, values: v, name: row ? row.name : null },
							callback: () => { d.hide(); load(); } });
					},
				});
				d.show();
			}
			if (isAdmin()) {
				$(`<button class="btn btn-sm btn-primary" style="margin-bottom:10px">${__("Add KPI Entry")}</button>`).insertBefore($kpi).on("click", () => dialog(null));
				$kpi.on("click", "[data-edit]", function () { dialog(($kpi.data("rows") || []).find((x) => x.name === $(this).data("edit"))); });
				$kpi.on("click", "[data-del]", function () {
					const n = $(this).data("del");
					frappe.confirm(__("Delete this KPI entry?"), () =>
						frappe.call({ method: "assessment_management.api.delete_kpi", args: { kind: "group", name: n }, callback: load }));
				});
			}
			load();
		} });
	}

	function render() {
		const route = frappe.get_route();
		if (route[1]) showDetail(decodeURIComponent(route.slice(1).join("/")));
		else showList();
	}
	frappe.pages["assessor-group-report"].on_page_show = render;
};
