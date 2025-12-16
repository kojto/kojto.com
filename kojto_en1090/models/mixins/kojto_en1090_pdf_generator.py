from odoo import models, fields, api

class KojtoEn1090PDFGenerator(models.AbstractModel):
    """Mixin to handle PDF generation and attachment management for EN1090 documents.

    This mixin extends kojto.library.printable to provide consistent PDF generation
    and attachment management across all EN1090 document models.
    """
    _name = "kojto.en1090.pdf.generator"
    _description = "EN1090 PDF Generator Mixin"
    _inherit = ["kojto.library.printable"]

    # Fields
    pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        string="PDF Attachment",
        copy=False,
        help="The PDF attachment for this document"
    )
    attachments = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        domain=lambda self: [('res_model', '=', self._name)] + ([('res_id', '=', self.id)] if self.id else []),
        copy=False,
        help="Additional attachments for this document"
    )

    def generate_pdf_attachment_id(self):
        """Generate a PDF attachment for this document.

        Returns:
            int: The ID of the generated attachment
        """
        html = self.generate_report_html()
        html = self.inject_report_css(html)
        attachment = self.create_pdf_attachment(html)
        return attachment.id

    def delete_pdf_attachment_id(self):
        """Delete the PDF attachment for this document.

        Returns:
            bool: True if successful
        """
        for record in self:
            if record.pdf_attachment_id:
                record.pdf_attachment_id.unlink()
                record.pdf_attachment_id = False
        return True

    def action_generate_pdf(self):
        """Action to generate a PDF for this document.

        Returns:
            dict: Action to download the generated PDF
        """
        self.ensure_one()
        return self.print_document_as_pdf()
