frappe.pages["assessment-monitoring"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Assessment Monitoring"), single_column: true });
	const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
	const TABS = [
		["assessee", __("By Assessee")], ["assessor", __("By Assessor")], ["type", __("By Type")],
		["schedule", __("By Schedule")], ["matrix", __("By Assessment Matrix")],
	];
	let tab = "assessee";

	const f = {};
	f.project = page.add_field({ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Assessment Project", change: load });
	f.assessee = page.add_field({ fieldname: "assessee", label: __("Assessee"), fieldtype: "Link", options: "Assessee", change: load });
	f.assessor = page.add_field({ fieldname: "assessor", label: __("Assessor"), fieldtype: "Link", options: "Assessor", change: load });
	f.status = page.add_field({ fieldname: "status", label: __("Status"), fieldtype: "Select",
		options: ["", "Pending", "In Progress", "Overdue", "Finished"], change: load });

	const $tabs = $('<ul class="nav nav-tabs" style="margin-bottom:12px"></ul>').appendTo(page.main);
	TABS.forEach(([k, label]) => {
		$(`<li class="nav-item"><a class="nav-link ${k === tab ? "active" : ""}" data-tab="${k}" href="#">${label}</a></li>`)
			.appendTo($tabs);
	});
	const $out = $('<div></div>').appendTo(page.main);

	$tabs.on("click", "a", function (e) {
		e.preventDefault();
		tab = $(this).data("tab");
		$tabs.find("a").removeClass("active");
		$(this).addClass("active");
		load();
	});

	const filters = () => ({
		project: f.project.get_value(), assessee: f.assessee.get_value(),
		assessor: f.assessor.get_value(), status: f.status.get_value(),
	});

	function load() {
		frappe.call({
			method: "assessment_management.api.get_monitoring",
			args: Object.assign({ tab }, filters()),
			callback: (r) => {
				const { columns, data } = r.message;
				let h = `<table class="table table-bordered" style="font-size:12px"><tr>${columns.map((c) => `<th>${esc(c.label)}</th>`).join("")}</tr>`;
				data.forEach((row) => {
					h += "<tr>" + columns.map((c) => {
						let v = row[c.fieldname];
						if (c.fieldname === "progress") v = `${v}%`;
						return `<td>${esc(v == null ? "" : v)}</td>`;
					}).join("") + "</tr>";
				});
				$out.html(h + "</table>" + (data.length ? "" : `<p class="text-muted">${__("No data.")}</p>`));
			},
		});
	}

	const exporter = (file_type) => () =>
		open_url_post(frappe.request.url, {
			cmd: "assessment_management.api.export_monitoring",
			tab, filters: JSON.stringify(filters()), file_type,
		});
	page.add_menu_item(__("Export Excel"), exporter("xlsx"));
	page.add_menu_item(__("Export CSV"), exporter("csv"));
	load();
};
