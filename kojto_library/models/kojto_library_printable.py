from odoo import tools, models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64

from weasyprint import HTML


class KojtoLibraryPrintable(models.AbstractModel):
    _name = "kojto.library.printable"
    _description = "Kojto Library Printable"

    def print_document_as_pdf(self):
        html = self.generate_report_html()
        html = self.inject_report_css(html)
        attachment = self.create_pdf_attachment(html)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def generate_report_html(self):
        self = self.with_context(lang=self.language_id.code if self.language_id else "en_US")

        # If force_report_ref is in context, only use the context report_ref
        if self._context.get('force_report_ref'):
            report_ref = self._context.get('report_ref')
            if not report_ref:
                raise ValueError("force_report_ref is set but no report_ref provided in context")
        else:
            report_ref = self._context.get('report_ref') or getattr(self, "_report_ref", f"{self._name}.report_{self._name}")

        report = self.env["ir.actions.report"]._get_report_from_name(report_ref)
        if not report:
            raise ValueError(f"Report {report_ref} not found.")
        try:
            return report.with_context(lang=self._context["lang"])._render_qweb_html(docids=[self.id], report_ref=report_ref)[0].decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to generate HTML: {str(e)}") from e

    def inject_report_css(self, html):
        report_css_ref = getattr(self, "_report_css_ref", "kojto_pdf_main_document_header.css")
        kojto_pdf_header_css_file_path = tools.misc.file_path(f"kojto_file_assets/static/src/css/{report_css_ref}")
        with open(kojto_pdf_header_css_file_path, "r") as f:
            css = f.read()
        return html.replace("</head>", f"<style>@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&subset=cyrillic&display=swap');\n{css}</style></head>") if "</head>" in html else f"<html><head><style>{css}</style></head><body>{html}</body></html>"

    def create_pdf_attachment(self, html):
        try:
            pdf = HTML(string=html).write_pdf()
        except Exception as e:
            raise ValueError(f"Failed to generate PDF: {str(e)}") from e
        attachment = self.env["ir.attachment"].search([("res_model", "=", self._name), ("res_id", "=", self.id), ("name", "=", f"{self.name}.pdf")], limit=1)
        vals = {"datas": base64.b64encode(pdf).decode("utf-8"), "mimetype": "application/pdf", "store_fname": f"{self.name}.pdf"}
        if attachment:
            attachment.write(vals)
        else:
            attachment = self.env["ir.attachment"].create({**vals, "name": f"{self.name}.pdf", "type": "binary", "res_model": self._name, "res_id": self.id})
        if attachment:
            self.write({"pdf_attachment_id": attachment.id})
        return attachment
