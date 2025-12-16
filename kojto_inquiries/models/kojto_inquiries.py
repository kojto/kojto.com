from odoo import models, fields, api, _
from datetime import datetime, timedelta
from weasyprint import HTML
import uuid
import base64
import zipfile
import io
import re
from odoo.exceptions import ValidationError


class KojtoInquiries(models.Model):
    _name = "kojto.inquiries"
    _description = "Kojto Inquiry"
    _rec_name = "name"
    _order = "date_issue desc, name desc"
    _inherit = ["kojto.library.printable"]
    # General Information
    name = fields.Char(string="Name", compute="generate_inquiry_name", store=True)
    subject = fields.Char(string="Subject", default="Inquiry")
    active = fields.Boolean(string="Is Active", default=True)

    # Inquiry Specifics
    document_in_out_type = fields.Selection(selection=[("incoming", "In"), ("outgoing", "Out")], string="in/out:", required=True, default="outgoing")
    date_end = fields.Date(string="Valid Until", default=lambda self: fields.Date.today() + timedelta(days=7))
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today, required=True)

    # Nomenclature
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id.id)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    payment_terms_id = fields.Many2one("kojto.base.payment.terms", string="Payment Terms")
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
    counterparty_ids = fields.One2many("kojto.inquiry.counterparty", "inquiry_id", string="Counterparty")
    counterparty_names = fields.Text(string="Counterparties", compute="_compute_counterparty_names", store=False)

    # Document Content
    program = fields.Char(string="Program")
    pre_content_text = fields.Text(string="Pre Content Char")
    content = fields.One2many("kojto.inquiry.contents", "inquiry_id", string="Contents")
    post_content_text = fields.Text(string="Post Content Char")

    # Parent Relationship
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)

    # Additional Information
    issued_by_name_id = fields.Many2one("kojto.hr.employees", string="Created By")
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.inquiries'), ('res_id', '=', id)]")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")

    print_number = fields.Integer(string="print number", default=1)

    # Reports config for printing
    _report_ref = "kojto_inquiries.report_kojto_inquiry_counterparty"

    @api.depends("document_in_out_type", "subcode_id")
    def generate_inquiry_name(self):
        for record in self:
            if not (record.subcode_id and record.subcode_id.code_id and record.subcode_id.code_id.maincode_id):
                record.name = ""
                continue

            domain = [
                ("document_in_out_type", "=", record.document_in_out_type),
                ("subcode_id", "=", record.subcode_id.id),
                ("id", "!=", record.id),
            ]
            count = self.search_count(domain)
            suffix = "I" if record.document_in_out_type == "incoming" else "O"
            record.name = f"{record.subcode_id.code_id.maincode_id.maincode}." \
                         f"{record.subcode_id.subcode}.INQ.{suffix}.{str(count + 1).zfill(3)}"
        return {}

    @api.depends("counterparty_ids", "counterparty_ids.counterparty_id")
    def _compute_counterparty_names(self):
        for record in self:
            if record.counterparty_ids:
                names = []
                for counterparty in record.counterparty_ids:
                    if counterparty.counterparty_id and counterparty.counterparty_id.name:
                        names.append(counterparty.counterparty_id.name)
                record.counterparty_names = "\n".join(names) if names else ""
            else:
                record.counterparty_names = ""

    @api.onchange("company_id")
    def onchange_company(self):
        fields_to_reset = {
            "company_name_id": "company_id",
            "company_address_id": "company_id",
            "company_bank_account_id": "company_id",
            "company_tax_number_id": "company_id",
            "company_phone_id": "company_id",
            "company_email_id": "company_id",
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

    def copy_and_open(self):
        # Create a copy without attachments
        default_values = {
            'attachments': False,  # Don't copy attachments
        }
        new_record = self.copy(default_values)

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.inquiries",
            "res_id": new_record.id,
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
        }

    def action_import_inquiry_content(self):
        self.ensure_one()
        header = "Position\tName\tQuantity\tUnit\n"
        if self.content:
            lines = []
            for content in self.content:
                # Replace newlines and multiple whitespace in name with single space
                name = content.name or ''
                if name:
                    name = ' '.join(name.split())  # Replace all whitespace (including newlines) with single space

                position = content.position or ''
                if position:
                    position = ' '.join(position.split())  # Also clean position field

                lines.append(
                    f"{position}\t{name}\t{content.quantity or 0.0}\t{content.unit_id.name or ''}"
                )
            first_line = lines[0].split("\t") if lines else []
            is_header = (
                len(first_line) >= 4 and
                first_line[0].strip() == "Position" and
                first_line[1].strip() == "Name" and
                first_line[2].strip() == "Quantity" and
                first_line[3].strip() == "Unit"
            )
            data_lines = lines[1:] if is_header and len(lines) > 1 else lines
            inquiry_content_data = header + "\n".join(data_lines) + "\n"
        else:
            inquiry_content_data = header

        return {
            "name": "Import Inquiry Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.inquiry.content.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.inquiry.content.import.wizard"].create({
                "inquiry_id": self.id,
                "data": inquiry_content_data
            }).id,
            "target": "new",
            "context": {"default_inquiry_id": self.id}
        }

    @api.constrains('name')
    def _check_unique_inquiry_name(self):
        for record in self:
            if record.name:
                domain = [('name', '=', record.name)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError('Inquiry name must be unique!')
