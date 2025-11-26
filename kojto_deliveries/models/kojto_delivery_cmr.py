from odoo import models, fields, api
from ..utils.kojto_delivery_cmr_name_generator import get_temp_name, get_final_name
from math import ceil


class KojtoDeliveryCmr(models.Model):
    _name = "kojto.delivery.cmr"
    _description = "Delivery CMR"
    _rec_name = "name"
    _sort = "name desc"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_deliveries.report_kojto_delivery_cmr"
    _sql_constraints = [('name_unique', 'UNIQUE(name)', 'CMR name must be unique!')]

    name = fields.Char(string="Name", required=True, copy=False, default=lambda self: get_temp_name())
    delivery_ids = fields.One2many("kojto.deliveries", "cmr_id", string="Deliveries")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    taking_place = fields.Char(string="Taking Place")
    taking_address = fields.Char(string="Taking Address")
    date_taking = fields.Date(string="Taking Date")
    time_of_departure = fields.Char(string="Time of Departure")

    country_id = fields.Many2one("res.country", string="Arrival Country")
    place_for_delivery = fields.Char(string="Place for Delivery")
    time_of_arrival = fields.Char(string="Time of Arrival")

    warehouse_work_time = fields.Char(string="Warehouse Work Time")
    sender_instructions = fields.Text(string="Sender Instructions")
    special_agreements = fields.Text(string="Special Agreements")
    other_particulars = fields.Text(string="Other Particulars")
    cash_on_delivery = fields.Char(string="Cash On Delivery")
    established_in = fields.Char(string="Established In")
    date_established_on = fields.Date(string="Established On")
    contact_person = fields.Char(string="Contact Person")
    phone_number = fields.Char(string="Phone Number")

    document_by_sender = fields.Text(string="Document By Sender", compute="get_document_by_sender",)
    packing_list = fields.Text(string="Packing List", compute="_compute_packing_list")
    gross_weight = fields.Float(string="Gross Weight", compute="_compute_gross_weight")

    packing_list_overflow = fields.Boolean(string="Packing List Overflow", compute="_compute_packing_list_overflow")
    loading_list_pages = fields.Json(string="Loading List Pages", compute="_compute_loading_list_pages")
    number_of_packages_in_cmr = fields.Integer(string="Number of Packages in CMR", compute="_compute_number_of_packages_in_cmr")

    # PDF attachment field for printing
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment")

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate CMR names following warehouse batch pattern"""
        cmrs = super(KojtoDeliveryCmr, self).create(vals_list)
        for cmr in cmrs:
            cmr.write({'name': get_final_name(cmr.id)})
        return cmrs

    @api.depends("delivery_ids", "delivery_ids.attachments")
    def get_document_by_sender(self):
        for record in self:
            if not record.delivery_ids:
                record.document_by_sender = ""
                continue

            document_lines = []
            for delivery in record.delivery_ids:
                # Add delivery name as document
                if delivery.name:
                    document_lines.append(f"Delivery: {delivery.name}")

                # Add attachments
                if delivery.attachments:
                    for attachment in delivery.attachments:
                        if attachment.name:
                            document_lines.append(f"Attachment: {attachment.name}")

                # Add PDF attachment if exists
                if delivery.pdf_attachment_id and delivery.pdf_attachment_id.name:
                    document_lines.append(f"PDF: {delivery.pdf_attachment_id.name}")

                # Add invoices if any
                if delivery.invoices_ids:
                    for invoice in delivery.invoices_ids:
                        if invoice.consecutive_number:
                            document_lines.append(f"Invoice: {invoice.consecutive_number}")

            record.document_by_sender = "\n".join(document_lines)

    @api.depends("delivery_ids.packages")
    def _compute_packing_list(self):
        for record in self:
            if not record.delivery_ids:
                record.packing_list = ""
                continue

            packing_lines = []
            total_weight = 0.0

            for delivery in record.delivery_ids:
                if not delivery.packages:
                    continue

                for package in delivery.packages:
                    # Calculate package weight (sum of item weights)
                    package_weight = 0.0
                    if package.package_content_ids:
                        for item in package.package_content_ids:
                            if item.delivery_content_id:
                                package_weight += item.total_weight or 0.0
                    material_desc = self.get_package_material_description(package)
                    package_header = f"Package {package.name or ''} ({package_weight:.2f} kg)"
                    if material_desc:
                        package_header += f" - {material_desc}"
                    packing_lines.append(package_header)
                    total_weight += package_weight

            record.packing_list = "\n".join(packing_lines)

    @api.depends("packing_list")
    def _compute_packing_list_overflow(self):
        for record in self:
            lines = record.packing_list.split("\n") if record.packing_list else []
            record.packing_list_overflow = len(lines) > 5

    @api.depends("packing_list", "name")
    def _compute_loading_list_pages(self):
        for record in self:
            lines = record.packing_list.split("\n") if record.packing_list else []
            cmr_number = record.name or ""
            if len(lines) > 5:
                record.loading_list_pages = [f"Loading list for CMR {cmr_number} ({i+1}/7)" for i in range(7)]
            else:
                record.loading_list_pages = []

    @api.depends("delivery_ids.gross_weight")
    def _compute_gross_weight(self):
        for record in self:
            total_weight = 0.0
            for delivery in record.delivery_ids:
                if not delivery.packages:
                    continue
                total_weight += delivery.gross_weight
            record.gross_weight = total_weight

    @api.depends("delivery_ids.packages")
    def _compute_number_of_packages_in_cmr(self):
        for record in self:
            total = 0
            for delivery in record.delivery_ids:
                total += len(delivery.packages)
            record.number_of_packages_in_cmr = total

    def get_package_material_description(self, package):
        if not package.packaging_material_item_ids:
            return ""

        material_descs = []
        for item in package.packaging_material_item_ids:
            if item.packaging_material_id and item.packaging_material_id.description:
                material_descs.append(item.packaging_material_id.description)

        return ", ".join(material_descs)

    def print_delivery_cmr(self):
        """Print CMR document"""
        self.ensure_one()
        report_name = "kojto_deliveries.report_kojto_delivery_cmr"
        print_objects = self.ids
        html = self.generate_delivery_cmr_report_html(report_name, print_objects, 1)
        html = self.inject_report_css(html)
        attachment = self.create_pdf_attachment(html)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def generate_delivery_cmr_report_html(self, report_name, print_objects, copy):
        """Generate CMR report HTML exactly as it was when called from delivery"""
        self = self.with_context(lang=self.language_id.code if self.language_id else "en_US")
        report = self.env["ir.actions.report"]._get_report_from_name(report_name)
        if not report:
            raise ValueError("Report " + report_name + " not found.")
        try:
            return report.with_context(lang=self._context["lang"], copy=copy)._render_qweb_html(docids=print_objects, report_ref=report_name)[0].decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to generate HTML: {str(e)}") from e

    def create_pdf_attachment(self, html):
        """Create PDF attachment with CMR name as filename"""
        from weasyprint import HTML
        import base64

        try:
            pdf = HTML(string=html).write_pdf()
        except Exception as e:
            raise ValueError(f"Failed to generate PDF: {str(e)}") from e

        filename = f"{self.name}.pdf" if self.name else "CMR_Document.pdf"
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("name", "=", filename)
        ], limit=1)

        vals = {
            "datas": base64.b64encode(pdf).decode("utf-8"),
            "mimetype": "application/pdf",
            "store_fname": filename
        }

        if attachment:
            attachment.write(vals)
        else:
            attachment = self.env["ir.attachment"].create({
                **vals,
                "name": filename,
                "type": "binary",
                "res_model": self._name,
                "res_id": self.id
            })

        if attachment:
            self.write({"pdf_attachment_id": attachment.id})

        return attachment
