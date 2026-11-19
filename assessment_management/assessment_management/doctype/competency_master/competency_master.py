import frappe
from frappe import _
from frappe.model.document import Document


class CompetencyMaster(Document):
	def validate(self):
		levels = [int(r.level) for r in self.levels]
		if len(levels) != len(set(levels)):
			frappe.throw(_("Duplicate level in Levels table."))
		if any(l < 1 or l > 5 for l in levels):
			frappe.throw(_("Level must be between 1 and 5."))

		valid = set(levels)
		for row in self.indicators:
			if int(row.level) not in valid:
				frappe.throw(
					_("Positive Indicator row {0}: Level {1} is not defined in the Levels table.").format(
						row.idx, row.level
					)
				)
		self.levels = sorted(self.levels, key=lambda r: int(r.level))
		self.indicators = sorted(self.indicators, key=lambda r: int(r.level))
		for i, r in enumerate(self.levels, 1):
			r.idx = i
		for i, r in enumerate(self.indicators, 1):
			r.idx = i


def build_competency_tree():
	tree = []
	names = frappe.get_all(
		"Competency Master", order_by="sort_order asc, creation asc", pluck="name"
	)
	for name in names:
		doc = frappe.get_doc("Competency Master", name)
		levels = []
		for lv in doc.levels:
			levels.append(
				{
					"level": int(lv.level),
					"description": lv.level_description,
					"indicators": [i.indicator for i in doc.indicators if int(i.level) == int(lv.level)],
				}
			)
		tree.append(
			{
				"name": doc.name,
				"competency_name": doc.competency_name,
				"definition": doc.definition,
				"levels": levels,
			}
		)
	return tree


@frappe.whitelist()
def get_competency_tree():
	frappe.has_permission("Competency Master", "read", throw=True)
	return build_competency_tree()
