const WS_API = "assessment_management.api";
const AUTOSAVE_MS = 30000;
const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

// Which grid columns are relevant for each assessment type
const COLUMNS = {
	base: ["level_1_status", "level_2_status", "level_3_status", "level_4_status", "level_5_status",
	       "rating", "flag", "evidence", "analysis", "assessor_notes"],
	RW: ["rating", "suggested_score"],
	QC: ["qc_rating", "qc_notes"],
};
const ALL_COLS = [...new Set(Object.values(COLUMNS).flat())];

frappe.ui.form.on("Working Sheet", {
	refresh(frm) {
		if (frm.is_new()) return;
		const ob = frm.doc.__onload || {};
		const isAdmin = !!ob.is_admin;
		const finished = frm.doc.sheet_status === "Finished";
		const locked = !!ob.lock_reason;

		frm.trigger("setup_columns");
		frm.trigger("render_context");

		if (locked) {
			frm.disable_form();
			frm.dashboard.set_headline_alert(esc(ob.lock_reason), "red");
			return;
		}
		if (finished) {
			frm.disable_form();
			frm.dashboard.set_headline_alert(__("Finished - read only."), "green");
			if (isAdmin) {
				frm.add_custom_button(__("Revise"), () => {
					frappe.confirm(__("Reopen this sheet for editing? Finished At stays unchanged."), () =>
						frm.call({ doc: frm.doc, method: "revise", freeze: true }).then(() => frm.reload_doc())
					);
				}).addClass("btn-warning");
			}
		} else {
			frm.page.clear_primary_action();
			frm.page.set_primary_action(__("Submit and Finish"), () => frm.trigger("submit_and_finish"));
			frm.add_custom_button(isAdmin ? __("Save") : __("Save as Draft"), () => frm.save())
				.addClass(isAdmin ? "btn-primary" : "btn-warning");
			if (frm.doc.assessment_type === "Feedback" && !isAdmin) {
				// PDF: link video and photo are Admin-only inputs
				frm.set_df_property("video_feedback_link", "read_only", 1);
				frm.set_df_property("feedback_photo", "read_only", 1);
			}
			frm.trigger("start_autosave");
		}

		if (frm.doc.assessment_type === "Feedback") {
			frm.add_custom_button(__("Show Assessment Result Summary"), () => frm.trigger("show_summary"));
		}
		if (frm.doc.assessment) {
			frm.add_custom_button(__("Open Assessment"), () => frappe.set_route("Form", "Assessment", frm.doc.assessment));
		}
		frm.trigger("setup_counters");
	},

	// ----------------------------------------------------------------- columns
	setup_columns(frm) {
		const t = frm.doc.assessment_type;
		const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid) return;
		grid.cannot_add_rows = true;
		grid.cannot_delete_rows = true;
		const show = t === "RW" ? COLUMNS.RW : t === "QC" ? COLUMNS.QC : COLUMNS.base;
		ALL_COLS.forEach((f) => grid.update_docfield_property(f, "hidden", show.includes(f) ? 0 : 1));
		grid.refresh();
	},

	// ------------------------------------------------------------- context HTML
	render_context(frm) {
		const $w = frm.fields_dict.context_html && frm.fields_dict.context_html.$wrapper;
		if (!$w) return;
		frappe.call({
			method: `${WS_API}.get_sheet_context`,
			args: { name: frm.doc.name },
			callback: (r) => {
				const c = r.message || {};
				let html = "";

				(c.answers || []).forEach((set) => {
					html += `<details style="margin-bottom:8px"><summary><b>${__("Assessee Answers")} - ${esc(set.type)}</b></summary>`;
					set.qa.forEach(([q, a]) => {
						html += `<div style="margin:6px 0"><div class="text-muted">${esc(q)}</div><div>${esc(a)}</div></div>`;
					});
					html += "</details>";
				});

				if (["SPM", "SRB", "PK"].includes(frm.doc.assessment_type)) {
					html += `<details open><summary><b>${__("Competencies, Levels & Positive Indicators")}</b></summary>`;
					(c.competencies || []).forEach((comp) => {
						html += `<div style="margin:8px 0"><b>${esc(comp.competency_name)}</b>`;
						comp.levels.forEach((lv) => {
							html += `<div style="margin-left:12px"><u>Level ${lv.level}</u> ${esc(lv.description)}<ul>`;
							lv.indicators.forEach((i) => (html += `<li>${esc(i)}</li>`));
							html += "</ul></div>";
						});
						html += "</div>";
					});
					html += "</details>";
				}

				const prev = c.previous || {};
				const types = Object.keys(prev).filter((t) => prev[t]);
				if (types.length) {
					html += `<details open><summary><b>${__("Previous Results")}</b></summary>`;
					types.forEach((t) => {
						const p = prev[t];
						html += `<h6 style="margin-top:10px">${esc(t)} <span class="text-muted">(${esc(p.sheet_status)})</span></h6>
							<table class="table table-bordered" style="font-size:12px"><tr>
							<th>${__("Competency")}</th><th>${__("Rating")}</th><th>${__("Flag")}</th><th>${__("Evidence")}</th><th>${__("Analysis")}</th><th>${__("Notes")}</th></tr>`;
						p.items.forEach((i) => {
							html += `<tr><td>${esc(i.competency)}</td><td>${esc(i.rating || "")}${t === "RW" && i.qc_rating ? "" : ""}</td>
								<td>${esc(i.flag)}</td><td>${esc(i.evidence)}</td><td>${esc(i.analysis)}</td><td>${esc(i.assessor_notes)}</td></tr>`;
						});
						html += "</table>";
						if (t === "RW") {
							html += `<div><b>IG Notes:</b> ${esc(p.ig_notes)}</div>`;
						}
					});
					html += "</details>";
				}
				$w.html(html || `<div class="text-muted">${__("Nothing to show.")}</div>`);
			},
		});
	},

	// ------------------------------------------------------------------- counters
	setup_counters(frm) {
		if (!["RW", "QC"].includes(frm.doc.assessment_type)) return;
		const min = (frm.doc.__onload && frm.doc.__onload.min_chars) || 1300;
		["strength", "weakness"].forEach((fn) => {
			const field = frm.fields_dict[fn];
			if (!field || !field.$input) return;
			let $c = field.$wrapper.find(`.am-counter-${fn}`);
			if (!$c.length) {
				$c = $(`<div class="am-counter-${fn} small" style="margin-top:4px"></div>`).appendTo(
					field.$wrapper.find(".control-input-wrapper")
				);
				field.$input.on("input keyup", () => update(field, $c));
			}
			update(field, $c);
		});

		function update(field, $c) {
			const n = (field.$input.val() || "").trim().length;
			const ok = n >= min;
			$c.css("color", ok ? "var(--green-600, #2e7d32)" : "var(--red-600, #c62828)")
				.text(`${n} / ${min} ${__("characters")}${ok ? " ✓" : ` (${min - n} ${__("more needed")})`}`);
		}
	},

	// ------------------------------------------------------------------ autosave
	start_autosave(frm) {
		if (frm._am_timer) clearInterval(frm._am_timer);
		frm._am_timer = setInterval(() => {
			if (cur_frm !== frm || frm.doc.name === undefined) {
				clearInterval(frm._am_timer);
				return;
			}
			if (frm.is_dirty() && !frm.is_new() && !frm._am_saving && frm.doc.sheet_status !== "Finished") {
				frm._am_saving = true;
				frm.save("Save", () => {
					frm._am_saving = false;
					frappe.show_alert({ message: __("Draft autosaved"), indicator: "green" }, 3);
				}, null, () => (frm._am_saving = false));
			}
		}, AUTOSAVE_MS);
	},

	// ---------------------------------------------------------- submit and finish
	submit_and_finish(frm) {
		frappe.confirm(__("Submit and Finish? You will not be able to edit this sheet afterwards."), () => {
			const run = () =>
				frm.call({ doc: frm.doc, method: "submit_and_finish", freeze: true, freeze_message: __("Submitting...") })
					.then(() => frm.reload_doc());
			if (frm.is_dirty()) frm.save("Save", run);
			else run();
		});
	},

	// ------------------------------------------------------------------- summary
	show_summary(frm) {
		frappe.call({
			method: `${WS_API}.get_result_summary`,
			args: { assessment: frm.doc.assessment },
			callback: (r) => {
				let h = `<table class="table table-bordered"><tr><th>${__("Competency")}</th>`;
				for (let i = 1; i <= 5; i++) h += `<th class="text-center">Level ${i}</th>`;
				h += `<th class="text-center">${__("Final")}</th></tr>`;
				(r.message || []).forEach((row) => {
					h += `<tr><td>${esc(row.competency)}</td>`;
					for (let i = 1; i <= 5; i++) {
						h += `<td class="text-center" ${row.level === i ? 'style="background:var(--green-100,#c8e6c9)"' : ""}>${row.level === i ? "●" : ""}</td>`;
					}
					h += `<td class="text-center">${esc(row.final_rating || "-")}</td></tr>`;
				});
				frappe.msgprint({ title: __("Assessment Result Summary"), message: h + "</table>", wide: true });
			},
		});
	},
});
