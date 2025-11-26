from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from weasyprint import HTML
import base64


class KojtoDeliveries(models.Model):
    _name = "kojto.deliveries"
    _description = "Delivery Information"
    _rec_name = "name"
    _order = "date_delivery desc"
    _inherit = ["kojto.library.printable"]

    # General Information
    name = fields.Char(string="Name", compute="generate_delivery_name", copy=False, store=True)
    _sql_constraints = [
        ("unique_delivery_name", "unique(name)", "Delivery name must be unique!")
    ]
    active = fields.Boolean(string="Is Active", default=True)
    subject = fields.Text("Subject")

    # Delivery Specifics
    document_in_out_type = fields.Selection(selection=[("incoming", "In"), ("outgoing", "Out")], string="in/out:", required=True, default="outgoing")
    store_id = fields.Many2one("kojto.base.stores", string="Store")
    date_delivery = fields.Date(string="Delivery Date", default=fields.Date.today, required=True)
    tracking_number = fields.Char("Tracking Number")
    customs_number = fields.Char("Customs Number")
    exported_material = fields.Text("Exported Material")
    delivery_address = fields.Text("Delivery Address")
    net_weight = fields.Float(string="Net weight", compute="compute_net_weight", digits=(20, 2))
    tare_weight = fields.Float(string="Tare weight", compute="compute_tare_weight", digits=(20, 2))
    gross_weight = fields.Float(string="Gross weight", compute="compute_gross_weight", digits=(20, 2))
    signed_by = fields.Char("Signed By")  # dropdown with users who can sign declarations
    invoices_ids = fields.Many2many("kojto.finance.invoices", string="Export Invoices")

    # Nomenclature
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.EUR").id, required=True)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    incoterms_id = fields.Many2one("kojto.base.incoterms", "Incoterms")
    incoterms_address = fields.Char("Incoterms Address")

    # Company Information
    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True)

    company_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    company_registration_number = fields.Char(related="company_id.registration_number", string="Registration Number")
    company_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account")
    company_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    company_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    company_email_id = fields.Many2one("kojto.base.emails", string="Emails")

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    # Counterparty Information
    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", required=True)
    counterparty_type = fields.Selection(related="counterparty_id.contact_type", string="Counterparty Type")
    counterparty_registration_number = fields.Char(related="counterparty_id.registration_number", string="Registration Number")
    counterparty_registration_number_type = fields.Char(related="counterparty_id.registration_number_type", string="Registration Number Type")
    counterparty_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    counterparty_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank account")
    counterparty_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    counterparty_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    counterparty_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    counterparty_email_id = fields.Many2one("kojto.base.emails", string="Email")
    counterpartys_reference = fields.Char(string="Your Reference")

    # Document Content
    pre_content_text = fields.Text("Pre Content Text")
    post_content_text = fields.Text("Post Content Text")

    # o2m
    content = fields.One2many("kojto.delivery.contents", "delivery_id", string="Contents")
    packages = fields.One2many("kojto.delivery.packages", "delivery_id", string="Packages")

    # Parent Relationship
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    cmr_id = fields.Many2one("kojto.delivery.cmr", string="CMR", ondelete="set null")

    # Additional Information
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.deliveries'), ('res_id', '=', id)]")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")
    repr_html_gross_weight = fields.Html(compute="compute_html_delivery_gross_weight", string="Gross Weight")

    consumed_materials_ids = fields.One2many(comodel_name="kojto.delivery.consumed.materials", compute="compute_consumed_materials_ids", string="Consumed Materials")
    consumed_materials_table_html = fields.Html(compute="compute_consumed_materials_table_html", string="Consumed Materials Table")

    # Reports config for printing
    _report_ref = "kojto_deliveries.report_kojto_delivery"

    @api.model
    def web_search_read(self, **kwargs):
        order = kwargs.get("order", "")

        if not order:
            return super().web_search_read(**kwargs)

        custom_order_cols = {
            "repr_html_gross_weight": "gross_weight",
            "repr_html_dates": "date_delivery",
        }

        for custom_order_cols, order_col in custom_order_cols.items():
            if custom_order_cols in order:
                order = order.replace(custom_order_cols, order_col)

        kwargs["order"] = order
        return super().web_search_read(**kwargs)

    @api.depends("content")
    def compute_net_weight(self):
        for record in self:
            record.net_weight = sum(c.net_weight for c in record.content if c.net_weight)
        return {}

    @api.depends("packages")
    def compute_tare_weight(self):
        for record in self:
            record.tare_weight = sum(package.tare_weight for package in record.packages if package.tare_weight)
        return {}

    @api.depends("net_weight", "tare_weight")
    def compute_gross_weight(self):
        for record in self:
            record.gross_weight = record.net_weight + record.tare_weight
        return {}

    @api.depends("gross_weight", "net_weight", "tare_weight")
    def compute_html_delivery_gross_weight(self):
        for record in self:
            if not (record.packages and record.net_weight):
                record.repr_html_gross_weight = ""
                continue
            net = f"{record.net_weight:.2f} kg"
            tare = f"{record.tare_weight:.2f} kg"
            gross = f"{record.gross_weight:.2f} kg"
            # Make tare weight red
            tare_html = f"<span style='color: red; font-weight: bold;'>{tare}</span>"
            record.repr_html_gross_weight = f"{gross} (Net: {net}, Tare: {tare_html})"
        return {}

    @api.depends("document_in_out_type", "subcode_id")
    def generate_delivery_name(self):
        for record in self:
            if not (record.subcode_id and record.subcode_id.code_id and record.subcode_id.maincode_id):
                record.name = ""
                continue

            # Build the base name pattern
            suffix = "I" if record.document_in_out_type == "incoming" else "O"
            base_pattern = f"{record.subcode_id.maincode_id.maincode}.{record.subcode_id.code_id.code}.{record.subcode_id.subcode}.DL.{suffix}."

            # Find existing deliveries with the same domain
            domain = [
                ("document_in_out_type", "=", record.document_in_out_type),
                ("subcode_id", "=", record.subcode_id.id),
                ("name", "!=", False),
                ("name", "!=", ""),
            ]

            existing_deliveries = self.search(domain)
            max_number = 0

            # Extract the highest sequential number from existing names
            for delivery in existing_deliveries:
                if delivery.name and delivery.name.startswith(base_pattern):
                    try:
                        # Extract the number at the end of the name
                        number_part = delivery.name[len(base_pattern):]
                        if number_part.isdigit():
                            number = int(number_part)
                            max_number = max(max_number, number)
                    except (ValueError, IndexError):
                        continue

            # Increment the highest number by 1
            next_number = max_number + 1
            record.name = f"{base_pattern}{str(next_number).zfill(3)}"

    @api.onchange("company_id", "counterparty_id")
    def onchange_company_or_counterparty(self):
        fields_to_reset = {
            "company_name_id": "company_id",
            "company_address_id": "company_id",
            "company_bank_account_id": "company_id",
            "company_tax_number_id": "company_id",
            "company_phone_id": "company_id",
            "company_email_id": "company_id",
            "counterparty_name_id": "counterparty_id",
            "counterparty_address_id": "counterparty_id",
            "counterparty_tax_number_id": "counterparty_id",
            "counterparty_phone_id": "counterparty_id",
            "counterparty_email_id": "counterparty_id",
        }

        for field, id_field in fields_to_reset.items():
            setattr(self, field, False)

        if self.company_id:
            company = self.company_id
            for model, field in [
                ("kojto.base.names", "company_name_id"),
                ("kojto.base.addresses", "company_address_id"),
                ("kojto.base.bank.accounts", "company_bank_account_id"),
                ("kojto.base.tax.numbers", "company_tax_number_id"),
                ("kojto.base.phones", "company_phone_id"),
                ("kojto.base.emails", "company_email_id"),
            ]:
                record = self.env[model].search([("contact_id", "=", company.id)], limit=1)
                if record:
                    setattr(self, field, record.id)

        if self.counterparty_id:
            counterparty = self.counterparty_id
            for model, field in [
                ("kojto.base.names", "counterparty_name_id"),
                ("kojto.base.addresses", "counterparty_address_id"),
                ("kojto.base.tax.numbers", "counterparty_tax_number_id"),
                ("kojto.base.phones", "counterparty_phone_id"),
                ("kojto.base.emails", "counterparty_email_id"),
            ]:
                record = self.env[model].search([("contact_id", "=", counterparty.id)], limit=1)
                if record:
                    setattr(self, field, record.id)

    def open_cmr(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "CMR",
            "res_model": "kojto.delivery.cmr",
            "view_id": self.env.ref("kojto_deliveries.view_kojto_delivery_cmr_form_at").id,
            "view_mode": "form",
            "res_id": self.cmr_id.id,
            "target": "new",
            "context": {"default_delivery_ids": [(4, self.id)]},
        }

    def generate_delivery_report_html(self, report_name, print_objects):
        self = self.with_context(lang=self.language_id.code if self.language_id else "en_US")
        report = self.env["ir.actions.report"]._get_report_from_name(report_name)
        if not report:
            raise ValueError("Report " + report_name + " not found.")
        try:
            return report.with_context(lang=self._context["lang"])._render_qweb_html(docids=print_objects, report_ref=report_name)[0].decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to generate HTML: {str(e)}") from e

    def create_pdf_attachment(self, html, filename=None):
        """Create PDF attachment with custom filename"""
        try:
            pdf = HTML(string=html).write_pdf()
        except Exception as e:
            raise ValueError(f"Failed to generate PDF: {str(e)}") from e

        # Use custom filename if provided, otherwise use delivery name
        if filename:
            attachment_name = f"{filename}.pdf"
        else:
            attachment_name = f"{self.name}.pdf" if self.name else "Delivery_Document.pdf"

        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("name", "=", attachment_name)
        ], limit=1)

        vals = {
            "datas": base64.b64encode(pdf).decode("utf-8"),
            "mimetype": "application/pdf",
            "store_fname": attachment_name
        }

        if attachment:
            attachment.write(vals)
        else:
            attachment = self.env["ir.attachment"].create({
                **vals,
                "name": attachment_name,
                "type": "binary",
                "res_model": self._name,
                "res_id": self.id
            })

        if attachment:
            self.write({"pdf_attachment_id": attachment.id})

        return attachment

    def print_delivery_packages(self):
        report_name = "kojto_deliveries.report_kojto_delivery_packages"
        print_objects = self.packages.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_packages" if self.name else "delivery_packages"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_consumed_materials(self):
        report_name = "kojto_deliveries.report_kojto_delivery_consumed_materials"
        print_objects = self.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_consumed_materials" if self.name else "delivery_consumed_materials"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_origin_declaration(self):
        report_name = "kojto_deliveries.report_kojto_delivery_origin_declaration"
        print_objects = self.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_origin_declaration" if self.name else "delivery_origin_declaration"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_export_declaration(self):
        report_name = "kojto_deliveries.report_kojto_delivery_export_declaration"
        print_objects = self.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_export_declaration" if self.name else "delivery_export_declaration"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_dual_use_declaration(self):
        report_name = "kojto_deliveries.report_kojto_delivery_dual_use_declaration"
        print_objects = self.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_dual_use_declaration" if self.name else "delivery_dual_use_declaration"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_package_label(self):
        report_name = "kojto_deliveries.report_kojto_delivery_package_label"
        print_objects = self.ids
        html = self.generate_delivery_report_html(report_name, print_objects)
        html = self.inject_report_css(html)
        filename = f"{self.name}_package_label" if self.name else "delivery_package_label"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def print_delivery_cmr(self):
        report_name = "kojto_deliveries.report_kojto_delivery_cmr"
        print_objects = self.cmr_id.ids
        html = self.generate_delivery_cmr_report_html(report_name, print_objects, 1)
        html = self.inject_report_css(html)
        filename = f"{self.name}_cmr" if self.name else "delivery_cmr"
        attachment = self.create_pdf_attachment(html, filename)
        return {"type": "ir.actions.act_url", "url": f"/web/content/{attachment.id}?download=true", "target": "new"}

    def generate_delivery_cmr_report_html(self, report_name, print_objects, copy):
        self = self.with_context(lang=self.language_id.code if self.language_id else "en_US")
        report = self.env["ir.actions.report"]._get_report_from_name(report_name)
        if not report:
            raise ValueError("Report " + report_name + " not found.")
        try:
            return report.with_context(lang=self._context["lang"], copy=copy)._render_qweb_html(docids=print_objects, report_ref=report_name)[0].decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to generate HTML: {str(e)}") from e

    @api.depends("content")
    def compute_consumed_materials_table_html(self):
        for record in self:
            if not record.content:
                record.consumed_materials_table_html = "<p> No consumed materials found. </p>"
                continue

            # Filter contents that have consumed materials (content_compositions)
            contents_with_materials = [content for content in record.content if content.content_compositions]

            # Sort by position field
            contents_with_materials.sort(key=lambda x: x.position or '')

            if not contents_with_materials:
                record.consumed_materials_table_html = "<p> No consumed materials found. </p>"
                continue

            html = """
            <div style="margin-top: 30px; margin-bottom: 20px;">
                <h2 style="font-size: 1.5em; font-weight: bold; margin-bottom: 15px; color: #2c3e50;">Consumed Materials</h2>
                <table class="content-table" style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <thead>
                        <tr style="background-color: #B0C4DE;">
                            <th style="padding: 8px; text-align: left; width: 2%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Pos.</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Content</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Description</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Batch</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Material</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Certificate</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Invoice</th>
                            <th style="padding: 8px; text-align: left; width: 12%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Supplier</th>
                            <th style="padding: 8px; text-align: right; width: 6%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Used Qty</th>
                            <th style="padding: 8px; text-align: left; width: 2%; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: middle;">Unit</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            position_counter = 1
            for content in contents_with_materials:
                compositions_count = len(content.content_compositions)
                position_number = content.position or ''  # Use the actual position field from content

                for i, composition in enumerate(content.content_compositions):
                    # Build material description
                    material_desc = ""
                    if composition.batch_id:
                        batch = composition.batch_id
                        material_parts = []

                        # Add batch type
                        if batch.batch_type:
                            material_parts.append(batch.batch_type.title())

                        # Add material grade
                        if batch.material_id and batch.material_id.name:
                            material_parts.append(batch.material_id.name)

                        # Add thickness for sheets
                        if batch.batch_type == 'sheet' and batch.thickness:
                            material_parts.append(f"{batch.thickness}mm")

                        # Add profile for bars
                        if batch.batch_type == 'bar' and batch.profile_id and batch.profile_id.name:
                            material_parts.append(batch.profile_id.name)

                        material_desc = " - ".join(material_parts)

                    # Get first certificate name
                    certificate_name = ""
                    if composition.batch_id and composition.batch_id.certificate_ids:
                        # Find the first certificate with certificate_type = 'certificate'
                        certificate = composition.batch_id.certificate_ids.filtered(lambda c: c.certificate_type == 'certificate')
                        if certificate:
                            first_certificate = certificate[0]
                            certificate_name = first_certificate.name or ""
                        else:
                            # Fallback to first certificate if no 'certificate' type found
                            first_certificate = composition.batch_id.certificate_ids[0]
                            certificate_name = first_certificate.name or ""

                    if i == 0:
                        # First row for this content - include position and content name with rowspan
                        html += f"""
                        <tr>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;" rowspan="{compositions_count}">{position_number}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;" rowspan="{compositions_count}">{content.name or ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.description or ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_id.name if composition.batch_id else ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{material_desc}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{certificate_name}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.invoice_id.consecutive_number if composition.invoice_id else ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.invoice_id.counterparty_name_id.name if composition.invoice_id and composition.invoice_id.counterparty_name_id else ''}</td>
                            <td style="padding: 6px; text-align: right; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_quantity_consumed or ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_unit_id.name if composition.batch_unit_id else ''}</td>
                        </tr>
                        """
                    else:
                        # Subsequent rows for this content - only include the last 8 cells (no position or content name)
                        html += f"""
                        <tr>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.description or ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_id.name if composition.batch_id else ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{material_desc}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{certificate_name}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.invoice_id.consecutive_number if composition.invoice_id else ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.invoice_id.counterparty_name_id.name if composition.invoice_id and composition.invoice_id.counterparty_name_id else ''}</td>
                            <td style="padding: 6px; text-align: right; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_quantity_consumed or ''}</td>
                            <td style="padding: 6px; text-align: left; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; vertical-align: top;">{composition.batch_unit_id.name if composition.batch_unit_id else ''}</td>
                        </tr>
                        """

                position_counter += 1

            # Calculate the total consumed quantity and unit
            total_consumed = 0.0
            unit_name = ''
            for content in contents_with_materials:
                for composition in content.content_compositions:
                    if composition.batch_quantity_consumed:
                        total_consumed += composition.batch_quantity_consumed
                        # Use the first found unit name
                        if not unit_name and composition.batch_unit_id and composition.batch_unit_id.name:
                            unit_name = composition.batch_unit_id.name

            html += f"""
                    </tbody>
                </table>
                <div style='width: 100%; text-align: right; margin-top: -10px;'>
                    <span style='font-size: 1.1em; font-weight: bold;'>Total Used Qty: {total_consumed:.2f} {unit_name}</span>
                </div>
            </div>
            """

            record.consumed_materials_table_html = html
        return {}

    @api.depends("content")
    def compute_consumed_materials_ids(self):
        for record in self:
            consumed_materials = self.env['kojto.delivery.consumed.materials']
            for content in record.content:
                if content.content_compositions:
                    consumed_materials |= content.content_compositions
            record.consumed_materials_ids = consumed_materials
        return {}

    @api.constrains('name')
    def _check_unique_delivery_name(self):
        for record in self:
            if record.name:
                domain = [('name', '=', record.name)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError('Delivery name must be unique!')

    def copy_delivery(self):
        """Create a complete copy of the delivery including all contents and packages"""
        self.ensure_one()

        # Prepare default values for the new delivery
        default_values = {
            'date_delivery': fields.Date.today(),
            'tracking_number': False,
            'customs_number': False,
            'signed_by': False,
            'active': True,
        }

        # Create the new delivery
        new_delivery = self.copy(default_values)

        # Copy all delivery contents
        for content in self.content:
            content_values = {
                'delivery_id': new_delivery.id,
                'position': content.position,
                'name': content.name,
                'quantity': content.quantity,
                'unit_id': content.unit_id.id if content.unit_id else False,
                'quantity_package_contents': content.quantity_package_contents,
                'unit_weight': content.unit_weight,
            }
            new_content = self.env['kojto.delivery.contents'].create(content_values)

            # Copy consumed materials for this content
            for consumed_material in content.content_compositions:
                consumed_values = {
                    'delivery_content_id': new_content.id,
                    'name': consumed_material.name,
                    'description': consumed_material.description,
                    'invoice_id': consumed_material.invoice_id.id if consumed_material.invoice_id else False,
                    'invoice_content_id': consumed_material.invoice_content_id.id if consumed_material.invoice_content_id else False,
                    'batch_id': consumed_material.batch_id.id if consumed_material.batch_id else False,
                    'batch_quantity_consumed': consumed_material.batch_quantity_consumed,
                }
                self.env['kojto.delivery.consumed.materials'].create(consumed_values)

        # Copy all packages
        for package in self.packages:
            package_values = {
                'delivery_id': new_delivery.id,
                'name': package.name,
                'can_stack_on_it': package.can_stack_on_it,
                'pre_content_text': package.pre_content_text,
            }
            new_package = self.env['kojto.delivery.packages'].create(package_values)

            # Copy package contents
            for package_content in package.package_content_ids:
                package_content_values = {
                    'delivery_package_id': new_package.id,
                    'delivery_content_id': new_package.delivery_id.content.filtered(
                        lambda c: c.position == package_content.delivery_content_id.position
                    ).id if new_package.delivery_id.content.filtered(
                        lambda c: c.position == package_content.delivery_content_id.position
                    ) else False,
                    'name': package_content.name,
                    'position': package_content.position,
                    'quantity': package_content.quantity,
                }
                self.env['kojto.delivery.package.contents'].create(package_content_values)

            # Copy packaging material items
            for material_item in package.packaging_material_item_ids:
                material_item_values = {
                    'delivery_package_id': new_package.id,
                    'packaging_material_id': material_item.packaging_material_id.id if material_item.packaging_material_id else False,
                    'position': material_item.position,
                    'quantity': material_item.quantity,
                }
                self.env['kojto.delivery.packaging.material.items'].create(material_item_values)

        # Copy attachments
        # if self.attachments:
        #     new_delivery.attachments = [(6, 0, self.attachments.ids)]

        # Return action to open the new delivery
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.deliveries',
            'res_id': new_delivery.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_import_delivery_content(self):
        self.ensure_one()
        header = "Position\tName\tQuantity\tUnit\tUnit Weight\n"
        if self.content:
            lines = [
                f"{content.position or ''}\t{content.name or ''}\t{content.quantity or 0.0}\t{content.unit_id.name or ''}\t{content.unit_weight or 0.0}"
                for content in self.content
            ]
            first_line = lines[0].split("\t") if lines else []
            is_header = (
                len(first_line) >= 5 and
                first_line[0].strip() == "Position" and
                first_line[1].strip() == "Name" and
                first_line[2].strip() == "Quantity" and
                first_line[3].strip() == "Unit" and
                first_line[4].strip() == "Unit Weight"
            )
            data_lines = lines[1:] if is_header and len(lines) > 1 else lines
            delivery_content_data = header + "\n".join(data_lines) + "\n"
        else:
            delivery_content_data = header

        return {
            "name": "Import Delivery Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.delivery.content.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.delivery.content.import.wizard"].create({
                "delivery_id": self.id,
                "data": delivery_content_data
            }).id,
            "target": "new",
            "context": {"default_delivery_id": self.id}
        }

    def unlink(self):
        for delivery in self:
            if delivery.cmr_id:
                raise UserError(_("You cannot delete a delivery linked to a CMR document."))
        return super(KojtoDeliveries, self).unlink()
