from frappe.model.document import Document

from assessment_management.utils import validate_attachment


class BankStatement(Document):
	def validate(self):
		validate_attachment(self.attachment, ("pdf", "jpg", "jpeg", "png"), label="Attachment")
