frappe.pages["assessor-report"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Report Assessor"), single_column: true });
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const money = (v) => (v == null || v === "" ? "" : format_currency(v));
	const isAdmin = () => frappe.user.has_role("Assessment Admin") || frappe.user.has_role("System Manager");
	const $body = $('<div style="padding:8px 0"></div>').appendTo(page.main);
	const table = (cols, rows) =>
		`<table class="table table-bordered" style="font-size:12px"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
		rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
	const badge = (v) => {
		const c = { Finished: "green", Paid: "green", Overdue: "red", "Need to Be Paid": "orange", "In Progress": "blue" }[v] || "gray";
		return `<span class="indicator-pill ${c}">${esc(v)}</span>`;
	};

	// ------------------------------------------------------------- list view
	function showList() {
		page.clear_actions();
		page.set_title(__("Report Assessor"));
		$body.empty();
		const $top = $('<div class="form-inline" style="margin-bottom:12px"></div>').appendTo($body);
		const fp = frappe.ui.form.make_control({
			parent: $("<div style='display:inline-block;min-width:260px;margin-right:12px'></div>").appendTo($top),
			df: { fieldtype: "Link", options: "Assessment Project", label: __("Project"), fieldname: "project", change: load },
			render_input: true,
		});
		const $search = $(`<input class="form-control" style="max-width:240px" placeholder="${__("Search assessor")}">`).appendTo($top);
		const $out = $("<div></div>").appendTo($body);
		let data = [];
		function draw() {
			const q = ($search.val() || "").toLowerCase();
			const rows = data.filter((d) => !q || (d.full_name || "").toLowerCase().includes(q) || (d.unique_id || "").toLowerCase().includes(q));
			$out.html(table(["#", __("Assessor Name"), __("Unique ID"), __("Assessment Assigned"), __("Assessment Completed"), ""],
				rows.map((d, i) => [i + 1, esc(d.full_name), esc(d.unique_id), d.assigned, d.completed,
					`<a class="btn btn-xs btn-default" href="/app/assessor-report/${encodeURIComponent(d.assessor)}">${__("Detail")}</a>`])));
		}
		function load() {
			frappe.call({ method: "assessment_management.api.get_assessor_list", args: { project: fp.get_value() || null },
				callback: (r) => { data = r.message || []; draw(); } });
		}
		$search.on("input", draw);
		load();
	}

	// ----------------------------------------------------------- detail view
	function showDetail(name) {
		page.clear_actions();
		page.set_title(__("Report Assessor") + ": " + name);
		page.set_secondary_action(__("Back"), () => frappe.set_route("assessor-report"));
		$body.empty();
		frappe.call({ method: "assessment_management.api.get_assessor_detail", args: { assessor: name }, callback: (r) => {
			const a = r.message;
			let h = '<div class="card" style="padding:14px;margin-bottom:14px;border:1px solid var(--border-color)"><h5>' + __("Assessor Info") + "</h5><div class='row'>";
			[[__("Name"), a.full_name], [__("Email"), a.email], [__("Assigned"), a.assigned], [__("Finished"), a.finished],
			 [__("Phone"), a.phone], [__("Bank"), a.bank_name], [__("Account Number"), a.bank_account_number],
			 [__("Account Name"), a.bank_account_name], [__("NPWP"), a.npwp], [__("NIK"), a.nik],
			 [__("Marital Status"), a.marital_status], [__("Children Count"), a.children_count],
			 [__("Default Feedback Link"), a.default_feedback_link]].forEach(([l, v]) => {
				h += `<div class="col-sm-3" style="margin-bottom:8px"><div class="text-muted small">${esc(l)}</div><div>${esc(v == null ? "" : v)}</div></div>`;
			});
			h += "</div></div>";
			$body.append(h);

			const $tabs = $('<ul class="nav nav-tabs" style="margin-bottom:12px"></ul>').appendTo($body);
			const TABS = [["sheets", __("Working Sheets")], ["fee", __("Fee Summary")], ["kpi", __("Assessor KPI")]];
			TABS.forEach(([k, l], i) => $(`<li class="nav-item"><a class="nav-link ${i ? "" : "active"}" data-tab="${k}" href="#">${l}</a></li>`).appendTo($tabs));
			const $pane = $("<div></div>").appendTo($body);
			$tabs.on("click", "a", function (e) {
				e.preventDefault();
				$tabs.find("a").removeClass("active");
				$(this).addClass("active");
				({ sheets: tabSheets, fee: tabFee, kpi: tabKpi })[$(this).data("tab")]();
			});

			function tabSheets() {
				$pane.empty();
				const $f = $('<div class="form-inline" style="margin-bottom:10px;gap:8px;display:flex;flex-wrap:wrap"></div>').appendTo($pane);
				const mk = (df) => frappe.ui.form.make_control({ parent: $("<div style='min-width:200px'></div>").appendTo($f), df: Object.assign({ change: load }, df), render_input: true });
				const cProject = mk({ fieldtype: "Link", options: "Assessment Project", label: __("Project"), fieldname: "project" });
				const cMonth = mk({ fieldtype: "Date", label: __("Assigned Month (any day)"), fieldname: "month" });
				const cFin = mk({ fieldtype: "Select", label: __("Finished"), fieldname: "finished", options: ["", "Finished", "Not Finished"] });
				const cPaid = mk({ fieldtype: "Select", label: __("Paid"), fieldname: "paid", options: ["", "Paid", "Need to Be Paid", "Not Finished"] });
				const $btn = $(`<button class="btn btn-sm btn-success" style="align-self:flex-end">${__("Export to Excel")}</button>`).appendTo($f);
				const $out = $("<div></div>").appendTo($pane);
				const flt = () => ({
					project: cProject.get_value() || null,
					month: cMonth.get_value() ? cMonth.get_value().slice(0, 7) : null,
					finished: cFin.get_value() || null, paid: cPaid.get_value() || null,
				});
				function load() {
					frappe.call({ method: "assessment_management.api.get_assessor_sheets", args: Object.assign({ assessor: name }, flt()), callback: (r) => {
						$out.html(table(["#", __("Project"), __("Assessee"), __("Type"), __("Scheduled At"), __("Finished At"), __("Fee"), __("Paid")],
							(r.message || []).map((d, i) => [i + 1, esc(d.project), esc(d.assessee + " - " + d.assessee_name), esc(d.assessment_type),
								esc(d.scheduled_at), d.finished_at ? esc(d.finished_at) : badge(d.status), money(d.fee_amount),
								d.payment_status === "Paid" ? badge("Paid") + `<div class="text-muted small">${esc(d.paid_date)}</div>` : badge(d.payment_status)])));
					} });
				}
				$btn.on("click", () => open_url_post(frappe.request.url, { cmd: "assessment_management.api.export_assessor_sheets", assessor: name, filters: JSON.stringify(flt()) }));
				load();
			}

			function tabFee() {
				$pane.empty();
				const $f = $('<div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap"></div>').appendTo($pane);
				const mk = (df) => frappe.ui.form.make_control({ parent: $("<div style='min-width:200px'></div>").appendTo($f), df, render_input: true });
				const cFrom = mk({ fieldtype: "Date", label: __("From Date"), fieldname: "f", default: frappe.datetime.month_start() });
				const cTo = mk({ fieldtype: "Date", label: __("To Date"), fieldname: "t", default: frappe.datetime.month_end() });
				cFrom.set_value(frappe.datetime.month_start());
				cTo.set_value(frappe.datetime.month_end());
				const $apply = $(`<button class="btn btn-sm btn-primary" style="align-self:flex-end">${__("Apply")}</button>`).appendTo($f);
				const $out = $("<div></div>").appendTo($pane);
				function load() {
					frappe.call({ method: "assessment_management.api.get_fee_summary", args: { assessor: name, from_date: cFrom.get_value(), to_date: cTo.get_value() }, callback: (r) => {
						const d = r.message;
						$out.html(table(["#", __("Assessment Type"), __("Total Sheets"), __("Fee per Sheet"), __("Total Fee")],
							d.by_type.map((x, i) => [i + 1, esc(x.type), x.count, money(x.count ? x.amount / x.count : 0), money(x.amount)])) +
							`<p><b>${__("Grand Total")}: ${money(d.total)}</b> &nbsp; ${__("Paid")}: ${money(d.paid)} &nbsp; ${__("Unpaid")}: ${money(d.unpaid)}</p>`);
					} });
				}
				$apply.on("click", load);
				load();
			}

			function tabKpi() {
				$pane.empty();
				const $out = $("<div></div>").appendTo($pane);
				function load() {
					frappe.call({ method: "assessment_management.api.get_kpi", args: { kind: "assessor", key: name }, callback: (r) => {
						const L = r.message.labels, KF = Object.keys(L);
						const tag = (v) => (v ? `<span class="indicator-pill ${v === "On Target" ? "green" : "red"}">${esc(v)}</span>` : "-");
						$out.html(table(["#", __("Period")].concat(KF.map((k) => L[k])).concat(isAdmin() ? [__("Action")] : []),
							r.message.rows.map((x, i) => [i + 1, esc(x.label)].concat(KF.map((k) => tag(x[k]))).concat(isAdmin() ?
								[`<button class="btn btn-xs btn-warning" data-edit="${esc(x.name)}">${__("Edit")}</button> <button class="btn btn-xs btn-danger" data-del="${esc(x.name)}">${__("Delete")}</button>`] : []))));
						$out.data("rows", r.message.rows);
					} });
				}
				$pane.off("click", "[data-edit]").off("click", "[data-del]");
				if (isAdmin()) {
					$(`<button class="btn btn-sm btn-primary" style="margin-bottom:10px">${__("Add KPI Entry")}</button>`).prependTo($pane).on("click", () => kpiDialog(null));
					$pane.on("click", "[data-edit]", function () {
						kpiDialog(($out.data("rows") || []).find((x) => x.name === $(this).data("edit")));
					});
					$pane.on("click", "[data-del]", function () {
						const n = $(this).data("del");
						frappe.confirm(__("Delete this KPI entry?"), () =>
							frappe.call({ method: "assessment_management.api.delete_kpi", args: { kind: "assessor", name: n }, callback: load }));
					});
				}
				function kpiDialog(row) {
					const opts = "\nOn Target\nBelow Target";
					const d = new frappe.ui.Dialog({
						title: row ? __("Edit KPI Entry") : __("Add KPI Entry"),
						fields: [{ fieldname: "month", fieldtype: "Date", label: __("Period (any day of the month)"), reqd: 1, default: row && row.month },
							{ fieldname: "jumlah_simulasi", fieldtype: "Select", label: __("Jumlah Simulasi"), options: opts, default: row && row.jumlah_simulasi },
							{ fieldname: "kualitas_observasi", fieldtype: "Select", label: __("Kualitas Observasi"), options: opts, default: row && row.kualitas_observasi },
							{ fieldname: "konsistensi_pelaporan", fieldtype: "Select", label: __("Konsistensi Pelaporan"), options: opts, default: row && row.konsistensi_pelaporan },
							{ fieldname: "kepatuhan_administratif", fieldtype: "Select", label: __("Kepatuhan Administratif"), options: opts, default: row && row.kepatuhan_administratif },
							{ fieldname: "feedback_peserta", fieldtype: "Select", label: __("Feedback Peserta"), options: opts, default: row && row.feedback_peserta },
							{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks"), default: row && row.remarks }],
						primary_action_label: __("Save KPI"),
						primary_action(v) {
							frappe.call({ method: "assessment_management.api.save_kpi",
								args: { kind: "assessor", key: name, values: v, name: row ? row.name : null },
								callback: () => { d.hide(); load(); } });
						},
					});
					d.show();
				}
				load();
			}
			tabSheets();
		} });
	}

	function render() {
		const route = frappe.get_route();
		if (route[1]) showDetail(decodeURIComponent(route.slice(1).join("/")));
		else showList();
	}
	frappe.pages["assessor-report"].on_page_show = render;
};
