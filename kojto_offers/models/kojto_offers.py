from odoo import models, fields, api, _
from datetime import datetime, timedelta
import xlsxwriter
import uuid
import io
import base64
from odoo.exceptions import UserError, ValidationError
import re


class KojtoOffers(models.Model):
    _name = "kojto.offers"
    _description = "Kojto Docs Offer"
    _rec_name = "name"
    _order = "id desc"
    _inherit = ["kojto.library.printable"]

    # General Information
    name = fields.Char(string="Name", compute="generate_offer_name", store=True)
    subject = fields.Char(string="Subject", default="Offer")
    active = fields.Boolean(string="Is Active", default=True)

    # Offer Specifics
    document_in_out_type = fields.Selection(selection=[("incoming", "In"), ("outgoing", "Out")], string="in/out", required=True, default="outgoing")
    date_end = fields.Date(string="Valid Until", default=lambda self: fields.Date.today() + timedelta(days=7))
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today, required=True)

    # Financial Details
    pre_vat_total = fields.Float(string="Pre VAT total", compute="compute_all_totals", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="compute_all_totals", digits=(9, 2))
    vat_total = fields.Float(string="VAT", compute="compute_all_totals", digits=(9, 2))

    # Nomenclature
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id.id)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    payment_terms_id = fields.Many2one("kojto.base.payment.terms", string="Payment Terms", required=True)
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


    # Counterparty Information
    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", ondelete="restrict", required=True)
    counterparty_type = fields.Selection(related="counterparty_id.contact_type", string="Counterparty Type")
    counterparty_registration_number = fields.Char(related="counterparty_id.registration_number", string="Registration Number")
    counterparty_registration_number_type = fields.Char(related="counterparty_id.registration_number_type", string="Registration Number Type")
    counterparty_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank account")
    counterparty_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    counterparty_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    counterparty_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    counterparty_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    counterparty_email_id = fields.Many2one("kojto.base.emails", string="Email")
    counterpartys_reference = fields.Char(string="Your Reference")

    # Document Content
    program = fields.Char(string="Program")
    pre_content_text = fields.Text(string="Pre Content Char")
    content = fields.One2many("kojto.offer.contents", "offer_id", string="Contents")
    post_content_text = fields.Text(string="Post Content Char")

    consolidation_breakdown_ids = fields.One2many('kojto.offer.consolidation.breakdown', 'offer_id', string='Consolidation Breakdown', compute='_compute_consolidation_breakdown_ids', store=False, readonly=True,)

    # Parent Relationship
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    est_total_price = fields.Float(string="Est. Total Price", compute="compute_est_total_price", digits=(9, 2))
    est_total_contribution_margin = fields.Float(string="C-Margin (%)", compute="compute_est_total_contribution_margin", digits=(9, 2))
    est_total_contribution_margin_percent = fields.Float(string="C-Margin", compute="compute_est_total_contribution_margin_percent", digits=(9, 2))

    # Additional Information
    issued_by_name_id = fields.Many2one("kojto.hr.employees", string="Created By")
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.offers'), ('res_id', '=', id)]")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")
    repr_attachments = fields.Char(string="Attachments", compute="compute_single_attachment")

    offer_vat_rate = fields.Float(string="VAT Rate (in %)", digits=(9, 2))

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    def _compute_consolidation_breakdown_ids(self):
        for record in self:
            record.consolidation_breakdown_ids = self.env['kojto.offer.consolidation.breakdown'].search([('offer_id', '=', record.id)])

    @api.onchange("offer_vat_rate")
    def _onchange_offer_vat_rate(self):
        """Update vat_rate in all content lines when offer_vat_rate changes."""
        for line in self.content:
            line.vat_rate = self.offer_vat_rate

    # Reports config for printing
    _report_ref = "kojto_offers.print_offer"

    @api.model
    def web_search_read(self, **kwargs):
        order = kwargs.get("order", "")

        if not order:
            return super().web_search_read(**kwargs)

        custom_order_cols = {
        }

        for custom_order_col, order_col in custom_order_cols.items():
            if custom_order_col in order:
                order = order.replace(custom_order_col, order_col)

        kwargs["order"] = order
        return super().web_search_read(**kwargs)

    @api.depends("document_in_out_type", "subcode_id")
    def generate_offer_name(self):
        for record in self:
            if not record.subcode_id:
                record.name = ""
                continue

            suffix = "I" if record.document_in_out_type == "incoming" else "O"
            name_pattern = f"{record.subcode_id.name}.OF.{suffix}."

            # Find existing offers with the same subcode and same I/O type
            existing_offers = self.search([
                ("subcode_id", "=", record.subcode_id.id),
                ("document_in_out_type", "=", record.document_in_out_type),
                ("id", "!=", record.id),
            ])

            max_number = 0
            for offer in existing_offers:
                if offer.name and offer.name.startswith(name_pattern):
                    try:
                        # Extract the number part after the pattern
                        remaining_part = offer.name[len(name_pattern):]
                        # Find the first sequence of digits
                        number_match = re.search(r'^(\d+)', remaining_part)
                        if number_match:
                            number_part = number_match.group(1)
                            max_number = max(max_number, int(number_part))
                    except (ValueError, IndexError):
                        continue

            next_number = max_number + 1

            # Ensure uniqueness by checking if the name already exists
            proposed_name = f"{name_pattern}{str(next_number).zfill(3)}"
            while self.search([("name", "=", proposed_name), ("id", "!=", record.id)], limit=1):
                next_number += 1
                proposed_name = f"{name_pattern}{str(next_number).zfill(3)}"

            record.name = proposed_name

    @api.constrains('name')
    def _check_unique_offer_name(self):
        for record in self:
            if record.name:
                domain = [('name', '=', record.name)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError('Offer name must be unique!')


    @api.depends("attachments")
    def compute_single_attachment(self):
        for record in self:
            if not record.attachments:
                record.repr_attachments = ""
                continue

            sorted_attachments = record.attachments.sorted(key=lambda r: r.id)
            if len(sorted_attachments) > 1:
                record.repr_attachments = f"{sorted_attachments[0].name} + {len(sorted_attachments) - 1} more"
            else:
                record.repr_attachments = sorted_attachments[0].name
        return {}

    @api.depends("content", "content.pre_vat_total", "content.vat_total", "content.vat_rate")
    def compute_all_totals(self):
        for record in self:
            pre_vat_total = 0
            vat_total = 0
            for content in record.content:
                pre_vat_total += content.pre_vat_total
                vat_total += content.vat_total
            record.pre_vat_total = pre_vat_total
            record.vat_total = vat_total
            record.total_price = record.pre_vat_total + record.vat_total
        return {}

    @api.depends("content.est_total_price")
    def compute_est_total_price(self):
        for record in self:
            record.est_total_price = sum(content.est_total_price for content in record.content if content.est_total_price)
        return {}

    @api.depends("content.est_total_contribution_margin")
    def compute_est_total_contribution_margin(self):
        for record in self:
            record.est_total_contribution_margin = sum(content.est_total_contribution_margin for content in record.content if content.est_total_contribution_margin)
        return {}

    @api.depends("est_total_contribution_margin", "est_total_price")
    def compute_est_total_contribution_margin_percent(self):
        for record in self:
            record.est_total_contribution_margin_percent = record.est_total_contribution_margin / record.est_total_price * 100 if record.est_total_price else 0.0
        return {}

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

    def copy(self, default=None):
        default = dict(default or {})

        # Don't copy attachments by default
        if 'attachments' not in default:
            default['attachments'] = False

        # Create the copy of the offer
        copied_offer = super().copy(default)

        # Copy all content and their elements
        for content in self.content:
            content.copy({"offer_id": copied_offer.id})

        # Generate new name for the copied offer
        copied_offer.generate_offer_name()

        return copied_offer

    def copy_offer(self):
        """Copy offer and return action to open the copied offer."""
        copied_offer = self.copy()
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offers",
            "res_id": copied_offer.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_invoice(self):
        self.ensure_one()

        # Get default VAT treatment based on document type
        default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
            ("vat_in_out_type", "=", self.document_in_out_type), ("vat_treatment_type", "=", "full_vat")
        ], limit=1)
        if not default_vat_treatment:
            default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
                ("vat_in_out_type", "=", self.document_in_out_type)
            ], limit=1)

        currency_eur = self.env.ref("base.EUR")
        currency_bgn = self.env.ref("base.BGN")
        if self.currency_id and self.currency_id.id == currency_eur.id:
            exchange_rate_to_eur = 1.0
            exchange_rate_to_bgn = 1.0 / 1.95583
        elif self.currency_id and self.currency_id.id == currency_bgn.id:
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 1.95583
        else:
            exchange_rate_to_eur = 1.0
            exchange_rate_to_bgn = 1.0

        # Create temp_invoice for consecutive_number logic (same as copy_invoice method)
        temp_invoice = self.env["kojto.finance.invoices"].new({
            "document_in_out_type": self.document_in_out_type,
            "invoice_type": "invoice",
        })

        # Get consecutive number using the same logic as copy_invoice
        if self.document_in_out_type == "incoming":
            # For incoming invoices, use UUID like in copy_invoice
            consecutive_number = f"{uuid.uuid4()}"
        else:
            # For outgoing invoices, use pick_next_consecutive_number like in copy_invoice
            consecutive_number = temp_invoice.pick_next_consecutive_number()

        invoice = {
            "subject": self.subject,
            "active": True,
            "document_in_out_type": self.document_in_out_type,
            "invoice_type": "invoice",
            "consecutive_number": consecutive_number,
            "subcode_id": self.subcode_id.id,
            "parent_invoice_id": False,
            "payment_terms_id": self.payment_terms_id.id,
            "currency_id": self.currency_id.id,
            "language_id": self.language_id.id,
            "incoterms_id": self.incoterms_id.id,
            "incoterms_address": self.incoterms_address,
            "company_id": self.company_id.id,
            "company_address_id": self.company_address_id.id,
            "company_bank_account_id": self.company_bank_account_id.id if self.company_bank_account_id else False,
            "company_email_id": self.counterparty_email_id.id,
            "company_phone_id": self.counterparty_phone_id.id,
            "company_tax_number_id": self.company_tax_number_id.id,
            "company_name_id": self.company_name_id.id,
            "counterparty_id": self.counterparty_id.id,
            "counterparty_type": self.counterparty_type,
            "counterparty_name_id": self.counterparty_name_id.id,
            "counterparty_address_id": self.counterparty_address_id.id,
            "counterparty_email_id": self.counterparty_email_id.id,
            "counterparty_phone_id": self.counterparty_phone_id.id,
            "counterparty_tax_number_id": self.counterparty_tax_number_id.id,
            "counterpartys_reference": self.counterpartys_reference,
            "pre_content_text": self.pre_content_text,
            "post_content_text": self.post_content_text,
            "issued_by_name_id": self.issued_by_name_id.id if self.issued_by_name_id else False,
            "invoice_vat_rate": self.offer_vat_rate,
            "invoice_vat_treatment_id": default_vat_treatment.id if default_vat_treatment else False,
            "exchange_rate_to_eur": exchange_rate_to_eur,
            "exchange_rate_to_bgn": exchange_rate_to_bgn,
            "date_issue": self.date_issue if self.date_issue else fields.Date.today(),
            "date_tax_event": self.date_issue if self.date_issue else fields.Date.today(),
        }

        new_invoice = self.env["kojto.finance.invoices"].create(invoice)

        for invoice_content in self.content:
            self.env["kojto.finance.invoice.contents"].create(
                {
                    "invoice_id": new_invoice.id,
                    "name": invoice_content.name,
                    "position": invoice_content.position,
                    "quantity": invoice_content.quantity,
                    "unit_id": invoice_content.unit_id.id,
                    "unit_price": invoice_content.unit_price,
                    "vat_rate": invoice_content.vat_rate,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoices",
            "res_id": new_invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_contract(self):
        self.ensure_one()

        # --- Subcode creation logic ---
        offer_subcode = self.subcode_id
        code = offer_subcode.code_id
        if not code:
            raise UserError(_("Offer's subcode does not have a code domain."))

        # Get all subcodes for this code
        existing_subcodes = self.env['kojto.commission.subcodes'].search([
            ('code_id', '=', code.id)
        ])
        used_numbers = set()
        for sub in existing_subcodes:
            if sub.subcode and sub.subcode.isdigit() and len(sub.subcode) == 3:
                used_numbers.add(int(sub.subcode))
        # Find the first available 3-digit number
        new_subcode_num = None
        for i in range(1, 1000):
            if i not in used_numbers:
                new_subcode_num = i
                break
        if new_subcode_num is None:
            raise UserError(_("All 3-digit subcodes (001-999) are used in this code domain."))
        new_subcode_str = f"{new_subcode_num:03d}"
        # Create the new subcode
        new_subcode = self.env['kojto.commission.subcodes'].create({
            'subcode': new_subcode_str,
            'code_id': code.id,
            'description': self.subject or f"Contract for offer {self.name}",
            'active': True,
        })

        contract = {
            "subject": self.subject,
            "active": True,
            "document_in_out_type": self.document_in_out_type,
            "contract_type": "contract",
            "subcode_id": new_subcode.id,
            "payment_terms_id": self.payment_terms_id.id,
            "currency_id": self.currency_id.id,
            "language_id": self.language_id.id,
            "incoterms_id": self.incoterms_id.id,
            "incoterms_address": self.incoterms_address,
            "company_id": self.company_id.id,
            "company_address_id": self.company_address_id.id,
            "company_email_id": self.counterparty_email_id.id,
            "company_phone_id": self.counterparty_phone_id.id,
            "company_tax_number_id": self.company_tax_number_id.id,
            "company_bank_account_id": False,
            "company_name_id": self.company_name_id.id,
            "counterparty_id": self.counterparty_id.id,
            "counterparty_type": self.counterparty_type,
            "counterparty_name_id": self.counterparty_name_id.id,
            "counterparty_address_id": self.counterparty_address_id.id,
            "counterparty_tax_number_id": self.counterparty_tax_number_id.id,
            "counterparty_email_id": self.counterparty_email_id.id,
            "counterparty_phone_id": self.counterparty_phone_id.id,
            "counterpartys_reference": self.counterpartys_reference,
            "pre_content_text": self.pre_content_text,
            "post_content_text": self.post_content_text,
            "issued_by_name_id": self.issued_by_name_id.id if self.issued_by_name_id else False,
        }

        new_contract = self.env["kojto.contracts"].create(contract)

        for content in self.content:
            self.env["kojto.contract.contents"].create(
                {
                    "contract_id": new_contract.id,
                    "name": content.name,
                    "position": content.position,
                    "quantity": content.quantity,
                    "unit_id": content.unit_id.id,
                    "unit_price": content.unit_price,
                    "vat_rate": content.vat_rate,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.contracts",
            "res_id": new_contract.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_import_offer_content(self):
        self.ensure_one()
        header = "Position\tName\tQuantity\tUnit\tUnit Price\tVAT Rate\n"
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
                    f"{position}\t{name}\t{content.quantity or 0.0}\t{content.unit_id.name or ''}\t{content.unit_price or 0.0}\t{content.vat_rate or 0.0}"
                )
            first_line = lines[0].split("\t") if lines else []
            is_header = (
                len(first_line) >= 5 and
                first_line[0].strip() == "Position" and
                first_line[1].strip() == "Name" and
                first_line[2].strip() == "Quantity" and
                first_line[3].strip() == "Unit" and
                first_line[4].strip() == "Unit Price"
            )
            data_lines = lines[1:] if is_header and len(lines) > 1 else lines
            offer_content_data = header + "\n".join(data_lines) + "\n"
        else:
            offer_content_data = header

        return {
            "name": "Import Offer Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.content.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.offer.content.import.wizard"].create({
                "offer_id": self.id,
                "data": offer_content_data
            }).id,
            "target": "new",
            "context": {"default_offer_id": self.id}
        }

    def action_export_offer_to_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        # Define formats
        bold_format = workbook.add_format({'bold': True})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        currency_format = workbook.add_format({'num_format': '#,##0.00'})
        percent_format = workbook.add_format({'num_format': '0.00%'})

        # Sheet 1: Offer Info
        offer_sheet = workbook.add_worksheet('Offer')
        offer_fields = [
            ('Offer №', self.name),
            ('Subject', self.subject),
            ('Counterparty', self.counterparty_name_id.name if self.counterparty_name_id else ''),
            ('Issue Date', str(self.date_issue) if self.date_issue else ''),
            ('Valid To', str(self.date_end) if self.date_end else ''),
            ('Currency', self.currency_id.name if self.currency_id else ''),
            ('Total Price', self.total_price),
            ('VAT', self.vat_total),
            ('Net Amount', self.pre_vat_total),
            ('Reference №', self.counterpartys_reference),
            ('Program', self.program),
            ('Payment Terms', self.payment_terms_id.name if self.payment_terms_id else ''),
            ('Incoterms', self.incoterms_id.name if self.incoterms_id else ''),
            ('Incoterms Address', self.incoterms_address),
        ]
        for row, (label, value) in enumerate(offer_fields):
            offer_sheet.write(row, 0, label, bold_format)
            if isinstance(value, (int, float)) and 'Price' in label or 'VAT' in label or 'Amount' in label:
                offer_sheet.write(row, 1, value, currency_format)
            else:
                offer_sheet.write(row, 1, value)

        # Sheet 2: Breakdown
        breakdown_sheet = workbook.add_worksheet('Breakdown')
        headers = ["№", "Consolidation Name", "Quantity", "Unit", "Avg. Unit Price", "Est. Total Price", "C-Margin", "C-Margin %"]
        for col, header in enumerate(headers):
            breakdown_sheet.write(0, col, header, header_format)
        for row, breakdown in enumerate(self.consolidation_breakdown_ids, start=1):
            breakdown_sheet.write(row, 0, getattr(breakdown, 'position', ''))
            breakdown_sheet.write(row, 1, getattr(breakdown, 'name', ''))
            breakdown_sheet.write(row, 2, getattr(breakdown, 'quantity', ''))
            breakdown_sheet.write(row, 3, getattr(breakdown.unit_id, 'name', '') if breakdown.unit_id else '')
            breakdown_sheet.write(row, 4, getattr(breakdown, 'avg_unit_price', ''), currency_format)
            breakdown_sheet.write(row, 5, getattr(breakdown, 'total_price_with_all_surcharges', ''), currency_format)
            breakdown_sheet.write(row, 6, getattr(breakdown, 'total_contribution_margin', ''), currency_format)
            breakdown_sheet.write(row, 7, getattr(breakdown, 'total_contribution_margin_percent', 0) / 100, percent_format)

        # Create a separate sheet for each offer content
        for content in self.content:
            # Create sheet name (Excel has 31 character limit for sheet names)
            sheet_name = f"{content.position or 'NoPos'}_{content.name or 'Content'}"[:31]
            # Replace invalid characters
            sheet_name = ''.join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_'))
            if not sheet_name:
                sheet_name = f"Content_{content.id}"

            content_sheet = workbook.add_worksheet(sheet_name)

            # Content header information
            content_sheet.write(0, 0, f"Content: {content.name or 'No Name'}", bold_format)
            content_sheet.write(1, 0, f"Position: {content.position or 'No Position'}", bold_format)
            content_sheet.write(2, 0, f"Quantity: {content.quantity or 0}", bold_format)
            content_sheet.write(3, 0, f"Unit: {content.unit_id.name if content.unit_id else 'No Unit'}", bold_format)
            content_sheet.write(4, 0, f"Unit Price: {content.unit_price or 0}", bold_format)
            content_sheet.write(5, 0, f"Est. Total Price: {content.est_total_price or 0}", bold_format)
            content_sheet.write(6, 0, f"Est. Total C-Margin: {content.est_total_contribution_margin or 0}", bold_format)
            content_sheet.write(7, 0, f"Est. Total C-Margin %: {content.est_total_contribution_margin_percent or 0}%", bold_format)

            # Content elements headers (starting from row 9)
            element_headers = [
                "№", "Consolidation ID", "Name", "Quantity", "Unit", "Unit Price",
                "Base Price", "CM base(%)", "Surch. (%)", "Surch.", "CM (%)",
                "C-Margin", "Total Price", "Currency"
            ]

            for col, header in enumerate(element_headers):
                content_sheet.write(9, col, header, header_format)

            # Content elements data
            for row, element in enumerate(content.content_elements, start=10):
                content_sheet.write(row, 0, element.position or '')
                content_sheet.write(row, 1, element.consolidation_id.name if element.consolidation_id else '')
                content_sheet.write(row, 2, element.name or '')
                content_sheet.write(row, 3, element.quantity or 0)
                content_sheet.write(row, 4, element.unit_id.name if element.unit_id else '')
                content_sheet.write(row, 5, element.unit_price or 0, currency_format)
                content_sheet.write(row, 6, element.base_price or 0, currency_format)
                content_sheet.write(row, 7, (element.c_margin_from_consolidation_id or 0) / 100, percent_format)
                content_sheet.write(row, 8, (element.surcharges_percent or 0) / 100, percent_format)
                content_sheet.write(row, 9, element.surcharge or 0, currency_format)
                content_sheet.write(row, 10, (element.contribution_margin_percent or 0) / 100, percent_format)
                content_sheet.write(row, 11, element.contribution_margin or 0, currency_format)
                content_sheet.write(row, 12, element.total_price or 0, currency_format)
                content_sheet.write(row, 13, element.currency_id.name if element.currency_id else '')

            # Set column widths
            content_sheet.set_column('A:A', 8)   # №
            content_sheet.set_column('B:B', 20)  # Consolidation ID
            content_sheet.set_column('C:C', 25)  # Name
            content_sheet.set_column('D:D', 12)  # Quantity
            content_sheet.set_column('E:E', 12)  # Unit
            content_sheet.set_column('F:F', 15)  # Unit Price
            content_sheet.set_column('G:G', 15)  # Base Price
            content_sheet.set_column('H:H', 12)  # CM base(%)
            content_sheet.set_column('I:I', 12)  # Surch. (%)
            content_sheet.set_column('J:J', 12)  # Surch.
            content_sheet.set_column('K:K', 10)  # CM (%)
            content_sheet.set_column('L:L', 15)  # C-Margin
            content_sheet.set_column('M:M', 15)  # Total Price
            content_sheet.set_column('N:N', 10)  # Currency

        # Set column widths for main sheets
        offer_sheet.set_column('A:A', 20)
        offer_sheet.set_column('B:B', 30)

        breakdown_sheet.set_column('A:A', 8)   # №
        breakdown_sheet.set_column('B:B', 25)  # Consolidation Name
        breakdown_sheet.set_column('C:C', 12)  # Quantity
        breakdown_sheet.set_column('D:D', 12)  # Unit
        breakdown_sheet.set_column('E:E', 15)  # Avg. Unit Price
        breakdown_sheet.set_column('F:F', 15)  # Est. Total Price
        breakdown_sheet.set_column('G:G', 15)  # C-Margin
        breakdown_sheet.set_column('H:H', 12)  # C-Margin %

        workbook.close()
        xlsx_data = output.getvalue()
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"Offer Export - {self.name}.xlsx",
                "type": "binary",
                "datas": base64.b64encode(xlsx_data),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def write(self, vals):
        res = super().write(vals)
        if 'offer_vat_rate' in vals:
            for offer in self:
                offer.content.write({'vat_rate': vals['offer_vat_rate'], 'custom_vat': -1})
        return res


    def action_import_offer_content_elements(self):
        self.ensure_one()
        header = "Content Position\tPosition\tName\tConsolidation\tQuantity\tUnit Price\n"
        elements_data = []
        for content in self.content.sorted(key=lambda c: c.position or ''):
            for element in content.content_elements.sorted(key=lambda e: e.position or ''):
                # Replace newlines and multiple whitespace with single space
                element_name = element.name or ''
                if element_name:
                    element_name = ' '.join(element_name.split())

                content_position = content.position or ''
                if content_position:
                    content_position = ' '.join(content_position.split())

                element_position = element.position or ''
                if element_position:
                    element_position = ' '.join(element_position.split())

                elements_data.append(
                    f"{content_position}\t{element_position}\t{element_name}\t{element.consolidation_id.name or ''}\t{element.quantity or 0.0}\t{element.unit_price or 0.0}"
                )

        data = header + "\n".join(elements_data) + "\n" if elements_data else header

        return {
            "name": "Import Offer Content Elements",
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.content.elements.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.offer.content.elements.import.wizard"].create({
                "offer_id": self.id,
                "data": data
            }).id,
            "target": "new",
            "context": {"default_offer_id": self.id}
        }
