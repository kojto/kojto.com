# kojto_contracts/models/kojto_contracts.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import uuid
import logging

_logger = logging.getLogger(__name__)


class KojtoContracts(models.Model):
    _name = "kojto.contracts"
    _description = "Kojto Contracts"
    _rec_name = "name"
    _order = "date_start desc"
    _inherit = ["kojto.library.printable"]

    # Reports config for printing
    _report_ref = "kojto_contracts.report_kojto_contract"

    # General Information
    name = fields.Char(string="Number", compute="generate_contract_name", store=True)
    active = fields.Boolean(string="Is Active", default=True)
    subject = fields.Char(string="Subject")

    # Contract Specifics
    contract_type = fields.Selection(selection=[("contract", "Contract"), ("annex", "Annex"), ("order", "Order"), ("order_confirmation", "Order Confirmation")], string="Contract type", default="contract", required=True)
    document_in_out_type = fields.Selection(selection=[("incoming", "In"), ("outgoing", "Out")], string="in/out:", required=True, default="outgoing")
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date")
    color = fields.Integer("Color", default=4)

    # Financial Details
    pre_vat_total = fields.Float(string="Pre VAT total", compute="compute_all_totals", digits=(9, 2))
    vat_total = fields.Float(string="VAT", compute="compute_all_totals", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="compute_all_totals", digits=(9, 2))

    # Nomenclature
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.EUR").id, required=True)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    payment_terms_id = fields.Many2one("kojto.base.payment.terms", string="Payment Terms")
    incoterms_id = fields.Many2one("kojto.base.incoterms", string="Incoterms")
    incoterms_address = fields.Char(string="Incoterms Address")

    # Company Information - From
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
    program = fields.Text(string="Program")
    pre_content_text = fields.Text(string="Pre content comment")
    content = fields.One2many("kojto.contract.contents", "contract_id", string="Contents")
    post_content_text = fields.Text(string="Post content comment")

    contract_vat_rate = fields.Float(string="VAT Rate (in %)", digits=(9, 2))

    @api.onchange("contract_vat_rate")
    def _onchange_contract_vat_rate(self):
        """Update vat_rate in all content lines when contract_vat_rate changes."""
        for line in self.content:
            line.vat_rate = self.contract_vat_rate

    # Parent Relationship
    parent_contract_id = fields.Many2one("kojto.contracts", string="Parent Contract")
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)

    # Attachments
    issued_by_name_id = fields.Many2one("kojto.hr.employees", string="Issued By Name")
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.contracts'), ('res_id', '=', id)]")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")

    @api.depends("document_in_out_type", "subcode_id", "subcode_id.code_id", "subcode_id.code_id.maincode_id")
    def generate_contract_name(self):
        for record in self:
            try:
                # Validate required relations
                if not (record.subcode_id and record.subcode_id.code_id and record.subcode_id.code_id.maincode_id and record.document_in_out_type):
                    record.name = "TEMPORARY"
                    continue

                # Get field values
                maincode = record.subcode_id.code_id.maincode_id.maincode
                code = record.subcode_id.code_id.code
                subcode = record.subcode_id.subcode
                if not (maincode and code and subcode):
                    record.name = "TEMPORARY"
                    continue

                # Format name with subcode
                suffix = "I" if record.document_in_out_type == "incoming" else "O"
                base_name = f"{maincode}.{code}.CN.{suffix}.{subcode}"

                # Check for duplicates and add counter if needed
                counter = 1
                final_name = base_name
                while True:
                    domain = [("name", "=", final_name), ("id", "!=", record.id if record.id else False)]
                    if not self.search_count(domain):
                        break
                    final_name = f"{base_name}.{counter}"
                    counter += 1

                record.name = final_name
            except Exception:
                record.name = "TEMPORARY"

        return {}

    @api.depends("content", "content.quantity", "content.unit_price", "content.vat_rate")
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

    @api.constrains('name')
    def _check_unique_contract_name(self):
        for record in self:
            if record.name:
                domain = [('name', '=', record.name)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError('Contract name must be unique!')


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

    def create_invoice(self):
        self.ensure_one()

        if not self.env["ir.model"].search([("model", "=", "kojto.finance.invoices")], limit=1):
            raise UserError("The 'Kojto Finance' module is not installed. Please install it to create invoices.")

        # Invert the document_in_out_type: incoming contracts create outgoing invoices
        invoice_document_type = "outgoing" if self.document_in_out_type == "incoming" else "incoming"

        # Get default VAT treatment based on document type
        default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
            ("vat_in_out_type", "=", invoice_document_type), ("vat_treatment_type", "=", "full_vat")
        ], limit=1)
        if not default_vat_treatment:
            default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
                ("vat_in_out_type", "=", invoice_document_type)
            ], limit=1)

        now_date = fields.Date.today()
        currency_bgn = self.env.ref("base.BGN")
        currency_eur = self.env.ref("base.EUR")
        if self.currency_id and self.currency_id.id == currency_bgn.id:
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 1.95583
        elif self.currency_id and self.currency_id.id == currency_eur.id:
            exchange_rate_to_bgn = 1.0 / 1.95583
            exchange_rate_to_eur = 1.0
        else:
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 1.0

        # Find the first bank account of our company with the contract currency
        company_bank_account_id = False
        if self.company_id and self.currency_id:
            bank_account = self.env['kojto.base.bank.accounts'].search([
                ('contact_id', '=', self.company_id.id),
                ('currency_id', '=', self.currency_id.id)
            ], limit=1)
            if bank_account:
                company_bank_account_id = bank_account.id
            elif self.company_bank_account_id:
                company_bank_account_id = self.company_bank_account_id.id

        # Create temp_invoice for consecutive_number logic (same as copy_invoice method)
        temp_invoice = self.env["kojto.finance.invoices"].new({
            "document_in_out_type": invoice_document_type,
            "invoice_type": "invoice",
        })

        # Get consecutive number using the same logic as copy_invoice
        if invoice_document_type == "incoming":
            # For incoming invoices, use UUID like in copy_invoice
            consecutive_number = f"{uuid.uuid4()}"
        else:
            # For outgoing invoices, use pick_next_consecutive_number like in copy_invoice
            consecutive_number = temp_invoice.pick_next_consecutive_number()

        invoice = {
            "subcode_id": self.subcode_id.id,
            "subject": self.subject,
            "active": True,
            "document_in_out_type": invoice_document_type,
            "invoice_type": "invoice",
            "consecutive_number": consecutive_number,
            "parent_invoice_id": False,
            "invoice_vat_rate": self.contract_vat_rate,
            "invoice_vat_treatment_id": default_vat_treatment.id if default_vat_treatment else False,
            "payment_terms_id": self.payment_terms_id.id,
            "currency_id": self.currency_id.id,
            "language_id": self.language_id.id,
            "incoterms_id": self.incoterms_id.id,
            "incoterms_address": self.incoterms_address,
            "company_id": self.company_id.id,
            "company_name_id": self.company_name_id.id if self.company_name_id else False,
            "company_address_id": self.company_address_id.id if self.company_address_id else False,
            "company_bank_account_id": company_bank_account_id,
            "company_tax_number_id": self.company_tax_number_id.id if self.company_tax_number_id else False,
            "company_phone_id": self.company_phone_id.id if self.company_phone_id else False,
            "company_email_id": self.company_email_id.id if self.company_email_id else False,
            "counterparty_id": self.counterparty_id.id,
            "counterparty_type": self.counterparty_type,
            "counterparty_name_id": self.counterparty_name_id.id if self.counterparty_name_id else False,
            "counterparty_bank_account_id": self.counterparty_bank_account_id.id if self.counterparty_bank_account_id else False,
            "counterparty_address_id": self.counterparty_address_id.id if self.counterparty_address_id else False,
            "counterparty_tax_number_id": self.counterparty_tax_number_id.id if self.counterparty_tax_number_id else False,
            "counterparty_phone_id": self.counterparty_phone_id.id if self.counterparty_phone_id else False,
            "counterparty_email_id": self.counterparty_email_id.id if self.counterparty_email_id else False,
            "counterpartys_reference": self.counterpartys_reference,
            "pre_content_text": self.pre_content_text,
            "post_content_text": self.post_content_text,
            "issued_by_name_id": self.issued_by_name_id.id,
            "exchange_rate_to_eur": exchange_rate_to_eur,
            "exchange_rate_to_bgn": exchange_rate_to_bgn,
            "date_issue": now_date,
            "date_tax_event": now_date,
        }

        new_invoices = self.env["kojto.finance.invoices"].create(invoice)

        for invoice_content in self.content:
            content = self.env["kojto.finance.invoice.contents"].create(
                {
                    "invoice_id": new_invoices.id,
                    "name": invoice_content.name,
                    "position": invoice_content.position,
                    "quantity": invoice_content.quantity,
                    "unit_id": invoice_content.unit_id.id,
                    "unit_price": invoice_content.unit_price,
                    "subcode_id": self.subcode_id.id,
                    "vat_treatment_id": default_vat_treatment.id,
                }
            )

        new_invoices.refresh_compute_totals()

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoices",
            "res_id": new_invoices.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_annex(self):
        self.ensure_one()

        annex = {
            "subcode_id": self.subcode_id.id,
            "subject": self.subject,
            "active": True,
            "document_in_out_type": self.document_in_out_type,
            "contract_type": "annex",
            "parent_contract_id": self.id,
            "contract_vat_rate": self.contract_vat_rate,
            "payment_terms_id": self.payment_terms_id.id,
            "currency_id": self.currency_id.id,
            "language_id": self.language_id.id,
            "incoterms_id": self.incoterms_id.id,
            "incoterms_address": self.incoterms_address,
            "company_id": self.company_id.id,
            "company_address_id": self.company_address_id.id,
            "company_tax_number_id": self.company_tax_number_id.id,
            "company_bank_account_id": False,
            "counterparty_id": self.counterparty_id.id,
            "counterparty_type": self.counterparty_type,
            "counterparty_address_id": self.counterparty_address_id.id,
            "counterparty_tax_number_id": self.counterparty_tax_number_id.id,
            "counterparty_bank_account_id": False,
            "counterpartys_reference": self.counterpartys_reference,
            "pre_content_text": self.pre_content_text,
            "post_content_text": self.post_content_text,
            "issued_by_name_id": self.issued_by_name_id.id,
        }

        new_annex = self.env["kojto.contracts"].create(annex)

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.contracts",
            "res_id": new_annex.id,
            "view_mode": "form",
            "target": "current",
        }

    def copy_contract(self):
        """
        Custom method to copy a contract:
        - All fields are copied
        - Many2manys (attachments) are linked, not copied
        - Contract contents are copied (new records)
        - New subcode is created with 3-digit name
        """
        self.ensure_one()
        Contract = self
        ContractModel = self.env['kojto.contracts']
        ContentModel = self.env['kojto.contract.contents']

        # --- Subcode creation logic (same as create_contract from offer) ---
        contract_subcode = self.subcode_id
        code = contract_subcode.code_id
        if not code:
            raise UserError(_("Contract's subcode does not have a code domain."))

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
            'description': self.subject or f"Contract copy from {self.name}",
            'active': True,
        })

        # Prepare values for the new contract
        contract_vals = Contract.copy_data()[0]
        # Remove Odoo technical fields if present
        contract_vals.pop('id', None)
        contract_vals.pop('name', None)  # Let it be recomputed
        contract_vals['date_start'] = fields.Date.today()
        contract_vals['date_end'] = False  # Reset end date
        contract_vals['subcode_id'] = new_subcode.id  # Use the new subcode

        # Link many2manys (do not copy)
        # contract_vals['attachments'] = [(6, 0, Contract.attachments.ids)]

        # Remove One2manys that should be created after (content)
        contract_vals.pop('content', None)

        # Create the new contract
        new_contract = ContractModel.create(contract_vals)

        # Copy contract contents
        for content in Contract.content:
            content.copy({
                'contract_id': new_contract.id,
                'name': content.name,
                'position': content.position,
                'quantity': content.quantity,
                'unit_id': content.unit_id.id if content.unit_id else False,
                'unit_price': content.unit_price,
                'vat_rate': content.vat_rate,
            })

        return new_contract

    def action_copy_contract(self):
        self.ensure_one()
        new_contract = self.copy_contract()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Copied Contract'),
            'res_model': 'kojto.contracts',
            'res_id': new_contract.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def create_delivery(self):
        """Create a delivery document from the contract"""
        self.ensure_one()

        if not self.env["ir.model"].search([("model", "=", "kojto.deliveries")], limit=1):
            raise UserError("The 'Kojto Deliveries' module is not installed. Please install it to create deliveries.")

        # Create the delivery record
        delivery_data = {
            "subject": self.subject,
            "active": True,
            "document_in_out_type": self.document_in_out_type,
            "date_delivery": fields.Date.today(),  # Default to current date
            "currency_id": self.currency_id.id,
            "language_id": self.language_id.id,
            "incoterms_id": self.incoterms_id.id if self.incoterms_id else False,
            "incoterms_address": self.incoterms_address,

            # Company information
            "company_id": self.company_id.id,
            "company_name_id": self.company_name_id.id if self.company_name_id else False,
            "company_address_id": self.company_address_id.id if self.company_address_id else False,
            "company_bank_account_id": self.company_bank_account_id.id if self.company_bank_account_id else False,
            "company_tax_number_id": self.company_tax_number_id.id if self.company_tax_number_id else False,
            "company_phone_id": self.company_phone_id.id if self.company_phone_id else False,
            "company_email_id": self.company_email_id.id if self.company_email_id else False,

            # Counterparty information
            "counterparty_id": self.counterparty_id.id,
            "counterparty_type": self.counterparty_type,
            "counterparty_name_id": self.counterparty_name_id.id if self.counterparty_name_id else False,
            "counterparty_bank_account_id": self.counterparty_bank_account_id.id if self.counterparty_bank_account_id else False,
            "counterparty_address_id": self.counterparty_address_id.id if self.counterparty_address_id else False,
            "counterparty_tax_number_id": self.counterparty_tax_number_id.id if self.counterparty_tax_number_id else False,
            "counterparty_phone_id": self.counterparty_phone_id.id if self.counterparty_phone_id else False,
            "counterparty_email_id": self.counterparty_email_id.id if self.counterparty_email_id else False,
            "counterpartys_reference": self.counterpartys_reference,

            # Document content
            "pre_content_text": self.pre_content_text,
            "post_content_text": self.post_content_text,

            # Required field - check if contract has subcode_id, otherwise will need to be set manually
            "subcode_id": self.subcode_id.id if hasattr(self, 'subcode_id') and self.subcode_id else False,
        }

        # Create the delivery
        new_delivery = self.env["kojto.deliveries"].create(delivery_data)

        # Copy contract contents to delivery contents
        for contract_content in self.content:
            delivery_content_data = {
                "delivery_id": new_delivery.id,
                "name": contract_content.name,
                "position": contract_content.position,
                "quantity": contract_content.quantity,
                "unit_id": contract_content.unit_id.id if contract_content.unit_id else False,
                # Note: delivery contents don't have unit_price, so we skip that field
                # You might want to add additional mapping if needed
            }

            self.env["kojto.delivery.contents"].create(delivery_content_data)

        # Return action to open the created delivery
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.deliveries",
            "res_id": new_delivery.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_import_contract_content(self):
        self.ensure_one()
        header = "Position\tName\tQuantity\tUnit\tUnit Price\tVAT Rate\n"
        if self.content:
            lines = [
                f"{content.position or ''}\t{content.name or ''}\t{content.quantity or 0.0}\t{content.unit_id.name or ''}\t{content.unit_price or 0.0}\t{content.vat_rate or 0.0}"
                for content in self.content
            ]
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
            contract_content_data = header + "\n".join(data_lines) + "\n"
        else:
            contract_content_data = header

        return {
            "name": "Import Contract Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.contract.content.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.contract.content.import.wizard"].create({
                "contract_id": self.id,
                "data": contract_content_data
            }).id,
            "target": "new",
            "context": {"default_contract_id": self.id}
        }
