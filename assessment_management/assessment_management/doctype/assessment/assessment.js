const ASM = "assessment_management.assessment_management.doctype.assessment.assessment";
const ADMIN_ROLES = ["Assessment Admin", "System Manager"];

function am_is_admin() {
	return ADMIN_ROLES.some((r) => frappe.user.has_role(r));
}

// Ask which stage (row) to act on, optionally limited by a predicate
function am_pick_stage(frm, title, predicate, extra_fields, action) {
	const opts = (frm.doc.schedules || []).filter(predicate).map((r) => r.assessment_type);
	if (!opts.length) {
		frappe.msgprint(__("No stage is eligible for this action."));
		return;
	}
	frappe.prompt(
		[{ fieldname: "assessment_type", label: __("Stage"), fieldtype: "Select", options: opts, default: opts[0], reqd: 1 }]
			.concat(extra_fields || []),
		(v) => action(v),
		title,
		__("Continue")
	);
}

function am_call(method, args, frm) {
	return frappe.call({ method: `${ASM}.${method}`, args: Object.assign({ assessment: frm.doc.name }, args), freeze: true })
		.then(() => frm.reload_doc());
}

frappe.ui.form.on("Assessment", {
	refresh(frm) {
		if (frm.is_new()) return;
		// Schedule fields are changed only through the actions below
		if (frm.fields_dict.schedules) {
			frm.fields_dict.schedules.grid.cannot_add_rows = true;
			frm.fields_dict.schedules.grid.cannot_delete_rows = true;
		}
		frm.add_custom_button(__("Final Report (PDF)"), () => {
			window.open(
				`/printview?doctype=Assessment&name=${encodeURIComponent(frm.doc.name)}&format=Final%20Report%20Assessee&no_letterhead=1`
			);
		}, __("Reports"));
		frm.add_custom_button(__("Open Working Sheet"), () =>
			am_pick_stage(frm, __("Open Working Sheet"), (r) => r.working_sheet, [], (v) => {
				const row = frm.doc.schedules.find((r) => r.assessment_type === v.assessment_type);
				frappe.set_route("Form", "Working Sheet", row.working_sheet);
			}));

		if (!am_is_admin()) return;
		const G = __("Admin");

		frm.add_custom_button(__("Create / Edit Schedule"), () =>
			am_pick_stage(frm, __("Create / Edit Schedule"), (r) => !r.finished_at, [
				{ fieldname: "assessor", label: __("Assessor"), fieldtype: "Link", options: "Assessor", reqd: 1 },
				{ fieldname: "scheduled_at", label: __("Scheduled At"), fieldtype: "Datetime", reqd: 1 },
				{ fieldname: "deadline_at", label: __("Deadline At"), fieldtype: "Datetime" },
				{ fieldname: "link_meet", label: __("Link Meet"), fieldtype: "Data", options: "URL" },
			], (v) => am_call("upsert_schedule", v, frm)), G);

		frm.add_custom_button(__("Delete Schedule"), () =>
			am_pick_stage(frm, __("Delete Schedule"), (r) => r.assessor && !r.finished_at, [], (v) =>
				frappe.confirm(__("Delete the schedule for {0}?", [v.assessment_type]), () =>
					am_call("delete_schedule", v, frm))), G);

		frm.add_custom_button(__("Delete Finished At"), () =>
			am_pick_stage(frm, __("Delete Finished At"), (r) => r.finished_at && r.payment_status !== "Paid", [], (v) =>
				frappe.confirm(__("Reset {0} to unfinished? The assessor can edit the sheet again.", [v.assessment_type]), () =>
					am_call("delete_finished_at", v, frm))), G);

		frm.add_custom_button(__("Mark as Paid"), () =>
			am_pick_stage(frm, __("Mark as Paid"), (r) => r.payment_status === "Need to Be Paid", [
				{ fieldname: "paid_date", label: __("Paid Date"), fieldtype: "Datetime", reqd: 1, default: frappe.datetime.now_datetime() },
			], (v) => am_call("mark_as_paid", v, frm)), G);

		frm.add_custom_button(__("Delete Paid"), () =>
			am_pick_stage(frm, __("Delete Paid"), (r) => r.payment_status === "Paid", [], (v) =>
				am_call("delete_paid", v, frm)), G);

		frm.add_custom_button(__("Import Answer Assessee"), () => am_import_answers(frm), G);
	},
});

function am_import_answers(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Import Answer Assessee"),
		fields: [
			{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Assessment Project", reqd: 1, default: frm.doc.project },
			{ fieldname: "assessment_type", label: __("Assessment Type"), fieldtype: "Select", reqd: 1,
			  options: ["SPM", "SRB", "PK", "Aspirasi Karir", "Tanggung Jawab"] },
			{ fieldname: "file_url", label: __("Excel / CSV file"), fieldtype: "Attach", reqd: 1,
			  description: __("First column: assessee_id. Other columns: one per question.") },
			{ fieldname: "overwrite", label: __("Overwrite existing answers"), fieldtype: "Check", default: 1 },
		],
		primary_action_label: __("Import"),
		primary_action(v) {
			frappe.call({
				method: "assessment_management.api.import_answers",
				args: v,
				freeze: true,
				callback: (r) => {
					d.hide();
					const m = r.message || {};
					frappe.msgprint({
						title: __("Import Result"),
						indicator: m.errors && m.errors.length ? "orange" : "green",
						message: `${__("Created")}: ${m.created} &nbsp; ${__("Updated")}: ${m.updated} &nbsp; ${__("Skipped")}: ${m.skipped}` +
							(m.errors && m.errors.length ? "<hr>" + m.errors.map(frappe.utils.escape_html).join("<br>") : ""),
					});
				},
			});
		},
	});
	d.show();
}
