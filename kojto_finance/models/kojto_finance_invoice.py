# kojto_finance/models/kojto_finance_invoice.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date as date_type, time as time_type
from deep_translator import GoogleTranslator
import calendar
from weasyprint import HTML
import tempfile
import base64
import time
import re

from .kojto_finance_vat_treatment import VAT_RATES_BY_TYPE
import logging

logger = logging.getLogger(__name__)

ODOO_TO_DEEP_TRANSLATOR_LANG = {
    'bg_BG': 'bg',
    'en_US': 'en',
    'de_DE': 'de',
    'fr_FR': 'fr',
    'es_ES': 'es',
    'it_IT': 'it',
    'ru_RU': 'ru',
    'tr_TR': 'tr',
    'ro_RO': 'ro',
    'pl_PL': 'pl',
    'uk_UA': 'uk',
    'nl_NL': 'nl',
    'pt_PT': 'pt',
    'pt_BR': 'pt',
    'cs_CZ': 'cs',
    'sk_SK': 'sk',
    'hu_HU': 'hu',
    'el_GR': 'el',
    'zh_CN': 'zh-CN',
    'ja_JP': 'ja',
    'sv_SE': 'sv',
    'fi_FI': 'fi',
    'da_DK': 'da',
    'no_NO': 'no',
    'hr_HR': 'hr',
    'sl_SI': 'sl',
    'lt_LT': 'lt',
    'lv_LV': 'lv',
    'et_EE': 'et',
    # Add more as needed
}

class KojtoFinanceInvoice(models.Model):
    _name = "kojto.finance.invoices"
    _description = "Kojto Finance Invoice"
    _inherit = ["kojto.library.printable"]
    _rec_name = "consecutive_number"
    _sort = "date_issue desc, consecutive_number desc"

    # General Information
    name = fields.Char(string="Number", compute="_generate_invoice_name", store=True)
    active = fields.Boolean(string="Is Active", default=True)
    subject = fields.Char(string="Subject")
    consecutive_number = fields.Char(string="Consecutive Number", default=lambda self: self.pick_next_consecutive_number(), required=True, copy=False)
    consecutive_number_selection = fields.Selection(selection=lambda self: self.get_next_consecutive_numbers(), store=False)

    invoice_has_invalid_redistribution = fields.Boolean(string="Invoice has invalid redistribution", compute="_compute_invoice_has_invalid_redistribution")

    # Parent Relationship
    parent_invoice_id = fields.Many2one("kojto.finance.invoices", string="Parent Invoice", index=True)
    parent_invoice_date_issue = fields.Date(related="parent_invoice_id.date_issue", string="Parent Invoice Issue Date")
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)

    # Invoice Specifics
    document_in_out_type = fields.Selection(selection=[("incoming", "In"), ("outgoing", "Out")], string="in/out:", required=True, default="outgoing", index=True)

    invoice_type = fields.Selection(selection=[("invoice", "Invoice"), ("proforma", "Proforma"), ("credit_note", "Credit Note"), ("debit_note", "Debit Note"), ("insurance_policy", "Insurance Policy"),], string="Invoice type", default="invoice", required=True, index=True,)

    # Invoice Specifics
    date_issue = fields.Date(string="Issue Date", default=lambda self: fields.Date.today(), required=True, index=True)
    date_due = fields.Date(string="Due Date", default=lambda self: fields.Date.today() + timedelta(days=7))
    date_tax_event = fields.Date(string="Tax Event Date", default=lambda self: fields.Date.today(), required=True)

    accountant_id = fields.Char(string="Accountant User ID")
    accounting_archive_number = fields.Char(string="Accounting Archive Number")
    accounting_op_date = fields.Date(string="Accounting Operation Date")
    accounting_export_date = fields.Datetime(string="Accounting Export Date")
    accounting_is_exported = fields.Boolean(string="Accounting Is Exported", compute="_compute_accounting_is_exported")

    # Financial Details
    pre_vat_total = fields.Float(string="Pre VAT total", compute="_compute_all_totals", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="_compute_all_totals", digits=(9, 2))
    vat_total = fields.Float(string="VAT", compute="_compute_all_totals", digits=(9, 2))
    custom_vat = fields.Float(string="Custom VAT", default=0, digits=(9, 2))
    invoice_vat_rate = fields.Float(string="Unified VAT Rate (in %)", digits=(9, 2), default=0)
    invoice_vat_treatment_id = fields.Many2one("kojto.finance.vat.treatment", string="Unified VAT Treatment", required=True, default=False, domain="[('vat_in_out_type', '=', document_in_out_type)]")
    invoice_acc_template_id = fields.Many2one("kojto.finance.accounting.templates", string="Unified Accounting Template")
    invoice_acc_template_domain = fields.Char(string="Unified Accounting Template Domain", compute="_compute_invoice_acc_template_domain", store=False)
    invoice_acc_subtype_id = fields.Many2one("kojto.finance.accounting.subtypes", string="Unified Accounting Subtype")
    invoice_acc_subtype_domain = fields.Char(string="Unified Accounting Subtype Domain", compute="_compute_invoice_acc_subtype_domain", store=False)

    # Nomenclature
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.EUR").id, required=True, index=True)
    exchange_rate_to_bgn = fields.Float(string="Exchange Rate to BGN", default=1.0, digits=(9, 5), required=True)
    exchange_rate_to_eur = fields.Float(string="Exchange Rate to EUR", default=1.0, digits=(9, 5), required=True)

    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)

    payment_terms_id = fields.Many2one("kojto.base.payment.terms", string="Payment Terms")
    incoterms_id = fields.Many2one("kojto.base.incoterms", "Incoterms")
    incoterms_address = fields.Char("Incoterms Address")

    # Company Information
    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True,)
    company_registration_number = fields.Char(related="company_id.registration_number", string="Registration Number")
    company_registration_number_type = fields.Char(related="company_id.registration_number_type", string="Registration Number Type")
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    company_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account")
    company_bank_account_type = fields.Selection(related="company_bank_account_id.account_type", string="Bank Account Type")
    company_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    company_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    company_email_id = fields.Many2one("kojto.base.emails", string="Emails")

    # Counterparty Information
    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", required=True, index=True)
    counterparty_type = fields.Selection(related="counterparty_id.contact_type", string="Counterparty Type")
    counterparty_registration_number = fields.Char(related="counterparty_id.registration_number", string="Registration Number")
    counterparty_registration_number_type = fields.Char(related="counterparty_id.registration_number_type", string="Registration Number Type",)
    counterparty_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    counterparty_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank account")
    counterparty_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    counterparty_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    counterparty_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    counterparty_email_id = fields.Many2one("kojto.base.emails", string="Email")
    counterpartys_reference = fields.Char(string="Your Reference")

    # Document Content
    pre_content_text = fields.Text(string="Pre content comment")
    post_content_text = fields.Text(string="Post content comment")
    pre_content_text_translation = fields.Text(string="Pre content translated comment")
    post_content_text_translation = fields.Text(string="Post content translated comment")
    pdf_notes = fields.Text(string="Notes")

    content = fields.One2many("kojto.finance.invoice.contents", "invoice_id", string="Contents")
    content_is_redistribution = fields.One2many("kojto.finance.invoice.contents", "invoice_id", string="Redistribution Contents", domain=[("is_redistribution", "=", True)])
    content_not_redistribution = fields.One2many("kojto.finance.invoice.contents", "invoice_id", string="Non-Redistribution Contents", domain=[("is_redistribution", "=", False)])
    transaction_allocation_ids = fields.One2many("kojto.finance.cashflow.allocation", "invoice_id", string="Transaction Allocation")

    # Additional Invoice Details
    insured = fields.Boolean(string="Insured")
    force_paid_status = fields.Boolean(string="Force Paid Status", default=False)
    paid = fields.Boolean(string="Paid", compute="_compute_paid", store=True)
    locked = fields.Boolean(string="Locked", default=False)

    # Attachments
    issued_by_name_id = fields.Many2one("kojto.hr.employees", string="Issued By Name")

    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.finance.invoices'), ('res_id', '=', id)]")
    attachments_for_preview = fields.Integer(string="Attachments for preview", compute="_compute_attachments_for_preview", store=False)

    attachment_1_outgoing_pdf = fields.Binary(string="Attachment 1", compute="_compute_outgoing_attachment_1_pdf", store=False)
    attachment_1_outgoing_pdf_bgn = fields.Binary(string="Attachment 1 BGN", compute="_compute_outgoing_attachment_1_pdf_bgn", store=False)

    attachment_1_incoming_pdf = fields.Binary(string="Attachment 1", compute="_compute_incoming_attachment_1_pdf", store=False)
    attachment_2_incoming_pdf = fields.Binary(string="Attachment 2", compute="_compute_incoming_attachment_2_pdf", store=False)
    attachment_3_incoming_pdf = fields.Binary(string="Attachment 3", compute="_compute_incoming_attachment_3_pdf", store=False)
    attachment_4_incoming_pdf = fields.Binary(string="Attachment 4", compute="_compute_incoming_attachment_4_pdf", store=False)
    attachment_5_incoming_pdf = fields.Binary(string="Attachment 5", compute="_compute_incoming_attachment_5_pdf", store=False)

    repr_attachments = fields.Char(string="Attachments", compute="_compute_single_attachment")

    # Reports config for printing
    _report_ref = "kojto_finance.report_kojto_invoices"
    _report_company_lang_ref = "kojto_finance.report_kojto_invoices_company_lang"
    _report_css_ref = "kojto_pdf_main_document_header.css"

    # Computed field to check if document language matches company language
    invoice_is_in_company_language = fields.Boolean(string="Is Company Language", compute="_compute_invoice_is_in_company_language")

    child_document_ids = fields.One2many(comodel_name="kojto.finance.invoices", inverse_name="parent_invoice_id", string="Credit/Debit Notes", compute="_compute_child_document_ids", help="Credit and debit notes linked to this invoice.")
    child_document_sum_all_totals = fields.Float(string="Child Doc. Totals", compute="_compute_child_document_sum_all_totals", digits=(9, 2))
    payable_amount = fields.Float(string="Payable Amount", compute="_compute_payable_amount", digits=(9, 2))
    paid_amount = fields.Float(string="Paid Amount", compute="_compute_paid_amount", digits=(9, 2))
    open_amount = fields.Float(string="Open Amount", compute="_compute_open_amount", digits=(9, 2))
    base_currency_id = fields.Many2one("res.currency", string="Converted Currency", compute="_compute_base_currency_id")
    total_price_base_currency = fields.Float(string="Total Price Base Currency", compute="_compute_total_price_base_currency", digits=(9, 2))

    @api.depends("force_paid_status", "open_amount")
    def _compute_paid(self):
        for invoice in self:
            invoice.paid = invoice.force_paid_status or invoice.open_amount == 0.0

    @api.depends("transaction_allocation_ids.amount", "transaction_allocation_ids.transaction_direction", "transaction_allocation_ids.transaction_id.exchange_rate_to_bgn", "transaction_allocation_ids.transaction_id.exchange_rate_to_eur", "document_in_out_type", "base_currency_id")
    def _compute_paid_amount(self):
        for invoice in self:
            if invoice.base_currency_id and invoice.base_currency_id.name == 'BGN':
                sum_incoming = sum(
                    a.amount * (a.transaction_id.exchange_rate_to_bgn or 1.0)
                    for a in invoice.transaction_allocation_ids if a.transaction_direction == "incoming"
                )
                sum_outgoing = sum(
                    a.amount * (a.transaction_id.exchange_rate_to_bgn or 1.0)
                    for a in invoice.transaction_allocation_ids if a.transaction_direction == "outgoing"
                )
            else:
                sum_incoming = sum(
                    a.amount * (a.transaction_id.exchange_rate_to_eur or 1.0)
                    for a in invoice.transaction_allocation_ids if a.transaction_direction == "incoming"
                )
                sum_outgoing = sum(
                    a.amount * (a.transaction_id.exchange_rate_to_eur or 1.0)
                    for a in invoice.transaction_allocation_ids if a.transaction_direction == "outgoing"
                )
            if invoice.document_in_out_type == "outgoing":
                invoice.paid_amount = sum_incoming - sum_outgoing
            else:  # incoming
                invoice.paid_amount = sum_outgoing - sum_incoming

    @api.depends("parent_invoice_id", "invoice_type")
    def _compute_child_document_ids(self):
        for record in self:
            children = self.env["kojto.finance.invoices"].search([
                ("parent_invoice_id", "=", record.id),
                ("invoice_type", "in", ["credit_note", "debit_note"])
            ])
            record.child_document_ids = children

    def _get_target_currency_and_rate(self):
        contact = self.env['kojto.contacts'].browse(1)
        if contact.exists() and contact.currency_id and contact.currency_id.name == 'BGN':
            return 'BGN', lambda rec: rec.exchange_rate_to_bgn or 1.0
        else:
            return 'EUR', lambda rec: rec.exchange_rate_to_eur or 1.0

    @api.depends("child_document_ids", "child_document_ids.total_price", "base_currency_id")
    def _compute_child_document_sum_all_totals(self):
        for record in self:
            if record.base_currency_id and record.base_currency_id.name == 'BGN':
                total = sum(child.total_price * (child.exchange_rate_to_bgn or 1.0) for child in record.child_document_ids)
            else:
                total = sum(child.total_price * (child.exchange_rate_to_eur or 1.0) for child in record.child_document_ids)
            record.child_document_sum_all_totals = total

    def write(self, vals):
        for record in self:
            updated_fields = set(vals.keys())
            allowed_fields = set(["locked", "accounting_op_date", "accountant_id", "accounting_export_date", "force_paid_status", "paid", "payable_amount", "paid_amount", "open_amount"])

            if record.locked and not updated_fields.issubset(allowed_fields):
                raise ValidationError("This document is locked and cannot be updated. Contact accounting department for more information.")

            if "content_not_redistribution" not in updated_fields and "subcode_id" not in updated_fields:
                return super(KojtoFinanceInvoice, self).write(vals)

            content_subcodes = {}
            main_subcode = vals.get("subcode_id", record.subcode_id.id)

            for row in record.content:
                content_subcodes[row.id] = row.subcode_id.id

            for row in vals.get("content_not_redistribution", []):
                if row[0] in [0, 1] and "subcode_id" in row[2]:
                    content_subcodes[row[1]] = row[2]["subcode_id"]

            if main_subcode not in content_subcodes.values():
                raise ValidationError(f"The subcode of the invoice must match at least one subcode in the content.")

        return super(KojtoFinanceInvoice, self).write(vals)

    def unlink(self):
        for record in self:
            if record.locked:
                raise ValidationError("This document is locked and cannot be deleted. Contact accounting department for more information.")
        return super(KojtoFinanceInvoice, self).unlink()

    @api.constrains("consecutive_number")
    def _check_consecutive_number(self):
        for record in self:
            if record.document_in_out_type != "outgoing":
                continue

            if record.invoice_type in  ["insurance_policy"]:
                raise ValidationError("Our company cannot issue insurance policies. Please contact support.")

            num = record.consecutive_number.strip()
            if not (num and num.isdigit() and len(num) == 10):
                raise ValidationError("The consecutive number must be a 10-digit number.")

            invoice_type_filter = ["invoice", "credit_note", "debit_note", "insurance_policy"]
            if record.invoice_type == "proforma":
                invoice_type_filter = ["proforma"]

            # Last invoice with consecutive number from the same group/prefix, including inactive
            last_invoice = self.with_context(active_test=False).search(
                [
                    ("document_in_out_type", "=", "outgoing"),
                    ("invoice_type", "in", invoice_type_filter),
                    ("id", "!=", record.id),
                    ("consecutive_number", "=like", f"{num[:1]}%"),
                    ("company_id", "=", record.company_id.id),
                ],
                order="consecutive_number desc", limit=1)

            num_start = num[:1]
            num_int = int(num)

            if not last_invoice:
                continue

            prev_num_str = last_invoice.consecutive_number.strip()
            prev_num = int(prev_num_str)
            diff = num_int - prev_num

            # Find the max consecutive number in the database for this prefix
            self.env.cr.execute(
                f"""
                SELECT MAX(consecutive_number) FROM {self._table}
                WHERE document_in_out_type = 'outgoing'
                  AND invoice_type IN %s
                  AND LEFT(consecutive_number, 1) = %s
                  AND consecutive_number ~ '^\\d{{10}}$'
                  AND company_id = %s
                """,
                (tuple(invoice_type_filter), num_start, record.company_id.id)
            )
            max_db_num_str = self.env.cr.fetchone()[0]
            max_db_num = int(max_db_num_str) if max_db_num_str and max_db_num_str.isdigit() else None

            if (diff != 1):
                raise ValidationError(
                    f"Consecutive number difference must be 1.\n"
                    f"Proposed: {num} (int: {num_int})\n"
                    f"Previous: {prev_num_str} (int: {prev_num}) [id={last_invoice.id}, type={last_invoice.invoice_type}, active={last_invoice.active}]\n"
                    f"Difference: {diff}\n"
                    f"Max in DB for prefix '{num_start}': {max_db_num_str} (int: {max_db_num})\n"
                    f"Invoice type filter: {invoice_type_filter}\n"
                    f"Current record id: {record.id}\n"
                    f"Company id: {getattr(record, 'company_id', None)}\n"
                )

    @api.constrains("date_issue", "invoice_type", "consecutive_number", "document_in_out_type")
    def _check_date_issue(self):
        for record in self:
            if record.document_in_out_type != "outgoing":
                continue

            num = record.consecutive_number.strip()

            invoice_type_filter = ["invoice", "credit_note", "debit_note", "insurance_policy"]
            if record.invoice_type == "proforma":
                invoice_type_filter = ["proforma"]

            inv_filter = [
                ("document_in_out_type", "=", "outgoing"),
                ("invoice_type", "in", invoice_type_filter),
                ("id", "!=", record.id),
                ("consecutive_number", "=like", f"{num[:1]}%"),
                ("consecutive_number", ">", record.consecutive_number)
            ]
            next_invoice = self.search(inv_filter, order="consecutive_number asc", limit=1)

            inv_filter[4] = ("consecutive_number", "<", record.consecutive_number)
            prev_invoice = self.search(inv_filter, order="consecutive_number desc", limit=1)

            if next_invoice and record.date_issue > next_invoice.date_issue:
                raise ValidationError(f"{record.invoice_type.capitalize()} {record.consecutive_number} cannot be issued after {next_invoice.date_issue.strftime('%Y-%m-%d')} ({next_invoice.invoice_type.capitalize()} {next_invoice.consecutive_number})")

            if prev_invoice and record.date_issue < prev_invoice.date_issue:
                raise ValidationError(f"{record.invoice_type.capitalize()} {record.consecutive_number} cannot be issued before {prev_invoice.date_issue.strftime('%Y-%m-%d')} ({prev_invoice.invoice_type.capitalize()} {prev_invoice.consecutive_number})")

    @api.constrains("content")
    def _check_content_units(self):
        for record in self:
            for content in record.content:
                if not content.identifier_id:
                    continue

                if content.unit_id != content.identifier_id.unit_id:
                    raise ValidationError(f"The unit for '{content.name}' must be the same as the unit for identifier '{content.identifier_id.display_name}'.")

    @api.constrains("document_in_out_type", "company_bank_account_id")
    def _check_bank_account_for_outgoing(self):
        for record in self:
            if record.document_in_out_type == "outgoing" and not record.company_bank_account_id:
                raise ValidationError("A bank account must be selected for outgoing invoices.")

    @api.constrains("exchange_rate_to_bgn", "exchange_rate_to_eur")
    def _check_exchange_rates(self):
        for record in self:
            if record.exchange_rate_to_bgn <= 0 or record.exchange_rate_to_eur <= 0:
                raise ValidationError("Exchange rate to BGN and to EUR must be greater than zero!")

    @api.constrains("name")
    def _check_unique_invoice_name(self):
        for record in self:
            if record.name:
                # Check for duplicate names excluding the current record
                duplicate = self.search([
                    ("name", "=", record.name),
                    ("id", "!=", record.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(f"Invoice name '{record.name}' already exists. Please try again or contact support if this error persists.")

    @api.constrains("consecutive_number", "counterparty_id", "document_in_out_type")
    def _check_incoming_consecutive_number_uniqueness(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                continue

            if not record.consecutive_number or not record.counterparty_id:
                continue

            # Check if there's already an incoming invoice with the same consecutive number and counterparty
            duplicate = self.search([
                ("document_in_out_type", "=", "incoming"),
                ("consecutive_number", "=", record.consecutive_number),
                ("counterparty_id", "=", record.counterparty_id.id),
                ("id", "!=", record.id)
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    f"For incoming invoices, the combination of consecutive number '{record.consecutive_number}' "
                    f"and counterparty '{record.counterparty_id.name}' must be unique. "
                    f"Another invoice with the same consecutive number already exists for this counterparty."
                )

    @api.constrains("parent_invoice_id", "subcode_id", "language_id", "currency_id", "counterparty_id")
    def _check_parent_invoice_consistency(self):
        """Validate that parent invoice properties match credit/debit note properties"""
        for record in self:
            if record.invoice_type not in ['credit_note', 'debit_note'] or not record.parent_invoice_id:
                continue

            parent = record.parent_invoice_id
            errors = []

            # Check subcode consistency
            if record.subcode_id and parent.subcode_id and record.subcode_id.id != parent.subcode_id.id:
                errors.append(f"Subcode must match parent invoice subcode ({parent.subcode_id.display_name})")

            # Check language consistency
            if record.language_id and parent.language_id and record.language_id.id != parent.language_id.id:
                errors.append(f"Language must match parent invoice language ({parent.language_id.name})")

            # Check currency consistency
            if record.currency_id and parent.currency_id and record.currency_id.id != parent.currency_id.id:
                errors.append(f"Currency must match parent invoice currency ({parent.currency_id.name})")

            # Check counterparty consistency
            if record.counterparty_id and parent.counterparty_id and record.counterparty_id.id != parent.counterparty_id.id:
                errors.append(f"Counterparty must match parent invoice counterparty ({parent.counterparty_id.name})")

            if errors:
                raise ValidationError(
                    f"For {record.invoice_type.replace('_', ' ').title()}, the following properties must match the parent invoice:\n" +
                    "\n".join(f"• {error}" for error in errors)
                )

    @api.onchange("subcode_id")
    def _onchange_subcode_id(self):
        for line in self.content:
            line.subcode_id = self.subcode_id

    @api.onchange("invoice_vat_rate")
    def _onchange_invoice_vat_rate(self):
        for line in self.content:
            line.vat_rate = self.invoice_vat_rate or 0.0

    @api.onchange("invoice_vat_treatment_id")
    def _onchange_invoice_vat_treatment_id(self):
        self.invoice_vat_rate = 0.0

        if self.invoice_vat_treatment_id and VAT_RATES_BY_TYPE:
            self.invoice_vat_rate = VAT_RATES_BY_TYPE.get(self.invoice_vat_treatment_id.vat_treatment_type, 0)

        for line in self.content:
            line.vat_treatment_id = self.invoice_vat_treatment_id
            line.vat_rate = self.invoice_vat_rate or 0.0

    @api.onchange("invoice_acc_template_id")
    def _onchange_invoice_acc_template_id(self):
        self.invoice_acc_subtype_id = False
        for line in self.content:
            line.accounting_template_id = self.invoice_acc_template_id
            line.subtype_id =  False
            line.identifier_id = False

    @api.onchange("invoice_acc_subtype_id")
    def _onchange_invoice_acc_subtype_id(self):
        for line in self.content:
            line.subtype_id = self.invoice_acc_subtype_id

    @api.onchange("parent_invoice_id")
    def _onchange_parent_invoice_id(self):
        """Copy data from parent invoice when creating credit note or debit note"""
        if not self.parent_invoice_id or self.invoice_type not in ['credit_note', 'debit_note']:
            return

        parent = self.parent_invoice_id

        # Copy basic invoice data
        self.subcode_id = parent.subcode_id
        self.language_id = parent.language_id
        self.currency_id = parent.currency_id
        self.exchange_rate_to_bgn = parent.exchange_rate_to_bgn
        self.exchange_rate_to_eur = parent.exchange_rate_to_eur
        self.company_bank_account_id = parent.company_bank_account_id

        # Copy counterparty data
        self.counterparty_id = parent.counterparty_id
        self.counterparty_name_id = parent.counterparty_name_id
        self.counterparty_address_id = parent.counterparty_address_id
        self.counterparty_tax_number_id = parent.counterparty_tax_number_id
        self.counterparty_phone_id = parent.counterparty_phone_id
        self.counterparty_email_id = parent.counterparty_email_id
        self.counterparty_bank_account_id = parent.counterparty_bank_account_id
        self.counterpartys_reference = parent.counterpartys_reference

    @api.onchange("document_in_out_type")
    def _reset_vat_treatment_id(self):
        for record in self:
            self.invoice_vat_treatment_id = False

    @api.onchange("payment_terms_id")
    def _onchange_payment_terms_id(self):
        """Calculate due date based on payment terms description"""
        if not self.payment_terms_id or not self.payment_terms_id.description:
            return

        # Only proceed if description contains the required marker and extract days
        description = self.payment_terms_id.description
        if "ToP_Net" not in description:
            return
        match = re.search(r'ToP_Net(\d+)', description)

        if match:
            days = int(match.group(1))
            if self.date_issue:
                self.date_due = self.date_issue + timedelta(days=days)
            else:
                # If no issue date, use current date
                self.date_due = fields.Date.today() + timedelta(days=days)

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    @api.depends("subcode_id", "document_in_out_type", "consecutive_number", "date_issue", "invoice_type")
    def _generate_invoice_name(self):
        for record in self:
            if not (record.subcode_id and record.subcode_id.code_id and record.subcode_id.maincode_id):
                record.name = f"{record.consecutive_number}"
                continue

            suffix = record.document_in_out_type[0].upper() if record.document_in_out_type else "O"
            base_name_pattern = f"{record.subcode_id.maincode_id.maincode}.{record.subcode_id.code_id.code}.{record.subcode_id.subcode}"

            doc_suffix = "INV"
            if record.invoice_type == "credit_note":
                doc_suffix = "CN"
            elif record.invoice_type == "debit_note":
                doc_suffix = "DN"
            elif record.invoice_type == "proforma":
                doc_suffix = "PF"
            elif record.invoice_type == "insurance_policy":
                doc_suffix = "INSP"

            # Regex to extract the extension from the name
            name_regex = re.compile(rf"^{re.escape(base_name_pattern)}\\.{doc_suffix}\\.{suffix}\\.(\\d+)$")

            # Search for all existing names with the same pattern (use SQL for accuracy)
            sql = f"""
                SELECT name FROM kojto_finance_invoices
                WHERE name LIKE %s
            """
            like_pattern = f"{base_name_pattern}.{doc_suffix}.{suffix}.%"
            self.env.cr.execute(sql, (like_pattern,))
            existing_names = [row[0] for row in self.env.cr.fetchall()]
            used_exts = set()
            for name in existing_names:
                m = name_regex.match(name or "")
                if m:
                    try:
                        used_exts.add(int(m.group(1)))
                    except Exception:
                        pass

            # Find the next available extension
            next_ext = 1
            if used_exts:
                next_ext = max(used_exts) + 1

            # Loop until a unique name is found (using SQL to check)
            while True:
                ext = str(next_ext).zfill(3)
                proposed_name = f"{base_name_pattern}.{doc_suffix}.{suffix}.{ext}"
                self.env.cr.execute(
                    "SELECT 1 FROM kojto_finance_invoices WHERE name = %s LIMIT 1", (proposed_name,)
                )
                if not self.env.cr.fetchone():
                    record.name = proposed_name
                    break
                next_ext += 1
                if next_ext > 3000:
                    import time
                    ext = str(int(time.time()))
                    proposed_name = f"{base_name_pattern}.{doc_suffix}.{suffix}.{ext}"
                    self.env.cr.execute(
                        "SELECT 1 FROM kojto_finance_invoices WHERE name = %s LIMIT 1", (proposed_name,)
                    )
                    if not self.env.cr.fetchone():
                        record.name = proposed_name
                        break
            # If for some reason the loop fails, fallback (should never happen)
            if not record.name:
                record.name = f"{base_name_pattern}.{doc_suffix}.{suffix}.{str(int(time.time()))}"
        return {}

    @api.depends("invoice_acc_template_id")
    def _compute_invoice_acc_subtype_domain(self):
        for record in self:
            if not record.invoice_acc_template_id:
                record.invoice_acc_subtype_domain = "[]"
                continue

            record.invoice_acc_subtype_domain = f"[('template_type_ids', 'in', {record.invoice_acc_template_id.template_type_id.id})]"
        return {}

    @api.depends("document_in_out_type")
    def _compute_invoice_acc_template_domain(self):
        for record in self:
            if not record.document_in_out_type:
                record.invoice_acc_template_domain = "[]"
                continue

            # Map document_in_out_type to primary_type
            primary_type = "purchase" if record.document_in_out_type == "incoming" else "sale"
            record.invoice_acc_template_domain = f"[('template_type_id.primary_type', '=', '{primary_type}')]"
        return {}

    @api.depends("content", "content.pre_vat_total", "content.vat_total", "content.vat_rate")
    def _compute_all_totals(self):
        for record in self:
            pre_vat_total = 0
            vat_total = 0
            for content in record.content.filtered(lambda c: not c.is_redistribution):
                pre_vat_total += content.pre_vat_total
                vat_total += content.vat_total
            record.pre_vat_total = pre_vat_total
            record.vat_total = vat_total
            vat = record.custom_vat if record.custom_vat != 0 else record.vat_total
            record.total_price = record.pre_vat_total + vat
        return {}

    def _get_exchange_rate_by_currency(self, currency_id, date_issue):
        """Helper method to get exchange rates based on currency logic"""
        if currency_id and currency_id.name == 'EUR':
            return 1.95583, 1.0
        elif currency_id and currency_id.name == 'BGN':
            return 1.0, 0.51129
        else:
            # For other currencies, use the existing get_exchange_rate method
            rate_to_bgn = self.get_exchange_rate(currency_id, self.env.ref("base.BGN"), date_issue)
            rate_to_eur = self.get_exchange_rate(currency_id, self.env.ref("base.EUR"), date_issue)
            return rate_to_bgn, rate_to_eur

    @api.onchange("currency_id", "date_issue")
    def _compute_exchange_rate_to_acc_currency(self):
        rate_to_bgn, rate_to_eur = self._get_exchange_rate_by_currency(self.currency_id, self.date_issue)
        self.exchange_rate_to_bgn = rate_to_bgn
        self.exchange_rate_to_eur = rate_to_eur

    def get_exchange_rate(self, from_currency, to_currency, date):
        if from_currency == to_currency:
            return 1.0

        if not date or not from_currency or not to_currency:
            return 0.0

        # Convert date to datetime if it's a date object or string
        if isinstance(date, str):
            date = fields.Date.from_string(date)

        # Convert date to datetime for comparison
        if isinstance(date, date_type) and not isinstance(date, datetime):
            date_start = datetime.combine(date, time_type.min)
            date_end = datetime.combine(date, time_type.max)
        elif isinstance(date, datetime):
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            return 0.0

        exchange_rate = self.env["kojto.base.currency.exchange"].search(
            [
                ("base_currency_id", "=", from_currency.id),
                ("target_currency_id", "=", to_currency.id),
                ("datetime", ">=", date_start),
                ("datetime", "<=", date_end),
            ],
            order="datetime DESC",
            limit=1,
        )

        if exchange_rate:
            return exchange_rate.exchange_rate

        return 0.0

    @api.depends("transaction_allocation_ids", "total_price", "custom_vat", "vat_total", "payable_amount", "paid_amount", "base_currency_id", "child_document_ids", "child_document_ids.total_price", "force_paid_status")
    def _compute_open_amount(self):
        for invoice in self:
            if invoice.invoice_type in ["credit_note", "debit_note"]:
                invoice.open_amount = 0.0
                continue
            # If marked as force paid, open_amount is 0
            if invoice.force_paid_status:
                invoice.open_amount = 0.0
            else:
                invoice.open_amount = invoice.payable_amount - invoice.paid_amount
        return {}

    @api.onchange("date_issue")
    def _compute_accounting_op_date(self):
        if not self.date_issue:
            return

        # if self.accounting_op_date:
        #     return

        last_day = calendar.monthrange(self.date_issue.year, self.date_issue.month)[1]
        self.accounting_op_date = fields.Date.from_string(f"{self.date_issue.year}-{self.date_issue.month:02d}-{last_day:02d}")

        return {}

    def _compute_accounting_is_exported(self):
        for record in self:
            record.accounting_is_exported = record.accounting_export_date is not False
        return {}

    @api.depends("attachments")
    def _compute_single_attachment(self):
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

    @api.onchange("document_in_out_type", "invoice_type")
    def onchange_document_in_out_type(self):
        if self.document_in_out_type not in ["incoming", "outgoing"]:
            self.consecutive_number = ""
            return

        if self._origin and self._origin.document_in_out_type == self.document_in_out_type:
            if self.consecutive_number:
                return

        nextnums = self.get_next_consecutive_numbers()
        self.consecutive_number = nextnums[0][0] if nextnums else ""

    @api.onchange("document_in_out_type", "consecutive_number")
    def onchange_document_in_out_type_and_consecutive_number(self):
        if self.document_in_out_type == "incoming":
            try:
                int(self.consecutive_number)
                self.consecutive_number = self.consecutive_number.zfill(10)
            except (ValueError, TypeError):
                pass

        return

    @api.onchange("consecutive_number_selection")
    def onchange_consecutive_number_selection(self):
        if not self.consecutive_number_selection:
            return
        self.consecutive_number = self.consecutive_number_selection
        self.consecutive_number_selection = ""

    @api.depends("invoice_type")
    def _compute_consecutive_number_selection(self):
        for record in self:
            record.consecutive_number_selection = self.get_next_consecutive_numbers()
        return {}

    def get_next_consecutive_numbers(self):
        if self.document_in_out_type == "incoming":
            return []

        invoice_type_filter = "'invoice', 'credit_note', 'debit_note', 'insurance_policy'"
        if self.invoice_type == "proforma":
            invoice_type_filter = "'proforma'"

        sql = f"""
        SELECT
            MAX(consecutive_number), LEFT(CAST(consecutive_number AS TEXT), 1) as prefix, COUNT(*) as cnt
        FROM
            {self._table}
        WHERE
            document_in_out_type = 'outgoing'
            AND invoice_type IN ({invoice_type_filter})
            AND LEFT(CAST(consecutive_number AS TEXT), 1) IN ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0')
        GROUP BY
            prefix
        ORDER BY
            cnt desc,
            prefix desc
        """

        try:
            self.env.cr.execute(sql)
            result = self.env.cr.fetchall()

            if not result:
                invnum = "1".zfill(10)
                return [(invnum, invnum)]

            nextnums = []
            for row in result:
                try:
                    nextnum = int(row[0]) + 1
                    nextnums.append((str(nextnum).zfill(10), str(nextnum).zfill(10)))
                except (ValueError, TypeError):
                    nextnums.append((row[0], row[0]))
            return nextnums
        except Exception as e:
            raise ValueError(f"Failed to generate next invoice number: {str(e)}")

    def pick_next_consecutive_number(self):
        numbers = self.get_next_consecutive_numbers()
        return numbers[0][0] if numbers else ""

    def get_last_day_of_issue_month(self):
        date_issue = self.date_issue or fields.Date.context_today(self)
        if isinstance(date_issue, str):
            date_issue = fields.Date.from_string(date_issue)
        last_day = calendar.monthrange(date_issue.year, date_issue.month)[1]
        return fields.Date.to_string(fields.Date.from_string(f"{date_issue.year}-{date_issue.month:02d}-{last_day:02d}"))

    def refresh_compute_totals(self):
        for content in self.content:
            content.refresh_compute_totals()

        self._compute_all_totals()
        self._compute_open_amount()
        return {}

    def dropdown_empty(self):
        return []

    def action_translate_invoice(self):
        for record in self:
            # Get company language from company_id.language_id
            odoo_lang = record.company_id.language_id.code if record.company_id and record.company_id.language_id else 'en'
            company_lang = ODOO_TO_DEEP_TRANSLATOR_LANG.get(odoo_lang, 'en')

            # Skip if company language is English or not set
            if not company_lang or company_lang == "en":
                continue

            if record.pre_content_text and not record.pre_content_text_translation:
                try:
                    record.pre_content_text_translation = GoogleTranslator(target=company_lang).translate(record.pre_content_text)
                except Exception as e:
                    raise UserError(f"Failed to translate pre-content text: {str(e)}")

            if record.post_content_text and not record.post_content_text_translation:
                try:
                    record.post_content_text_translation = GoogleTranslator(target=company_lang).translate(record.post_content_text)
                except Exception as e:
                    raise UserError(f"Failed to translate post-content text: {str(e)}")

            for content in record.content:
                if content.name and not content.name_translation:
                    try:
                        content.name_translation = GoogleTranslator(target=company_lang).translate(content.name)
                    except Exception as e:
                        raise UserError(f"Failed to translate content '{content.name}': {str(e)}")

    def generate_original_copy_report_html(self, html, language_code='en_US'):
        """Generate HTML with both original and copy versions of the invoice.
        The original version comes first, followed by a page break and then the copy version.
        Each version is clearly labeled as 'Original' or 'Copy' (or Bulgarian equivalents).
        """
        # Define labels based on language
        if language_code == 'bg_BG':
            original_label = "Оригинал"
            copy_label = "Копие"
        else:
            original_label = "Original"
            copy_label = "Copy"

        # Split the HTML at the page div to insert our content
        parts = html.split('<div class="page">')
        if len(parts) != 2:
            return html  # Return original if we can't properly split the content

        # Create the original version
        original_html = f"""
        <div class="page">
            <div class="copy_original_indicator" style="position: absolute; top: 20px; right: 20px; font-weight: bold; color: #666;">
                {original_label}
            </div>
            {parts[1]}
        </div>
        """

        # Create the copy version
        copy_html = f"""
        <div style="page-break-before: always;"></div>
        <div class="page">
            <div class="copy_original_indicator" style="position: absolute; top: 20px; right: 20px; font-weight: bold; color: #666;">
                {copy_label}
            </div>
            {parts[1]}
        </div>
        """

        # Combine both versions
        return parts[0] + original_html + copy_html

    def generate_notes_report_html(self, html, pdf_notes):
        """Generate HTML for the notes section of the invoice.
        The notes are added on a new page after the invoice content.
        """
        if not pdf_notes:
            return html

        # Create a new page for notes with proper styling
        notes_html = f"""
        <div style="page-break-before: always;"></div>
        <div class="page">
            <div class="notes-section" style="padding: 20px;">
                <h2 style="color: #333; margin-bottom: 15px; border-bottom: 1px solid #ddd; padding-bottom: 10px;">
                    Notes
                </h2>
                <div class="notes-content" style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; border: 1px solid #eee;">
                    {pdf_notes}
                </div>
            </div>
        </div>
        """
        return html + notes_html

    def _generate_pdf_attachment_in_lang_and_currency(self, invoice, target_lang, target_currency_id):
        if invoice.invoice_has_invalid_redistribution:
            raise UserError(_("Cannot print invoice: Redistribution total is not valid. Please check the redistribution items."))

        exchange_rate = 1.0
        if target_currency_id != invoice.currency_id:
            if target_currency_id == self.env.ref("base.BGN"):
                exchange_rate = invoice.exchange_rate_to_bgn
            elif target_currency_id == self.env.ref("base.EUR"):
                exchange_rate = invoice.exchange_rate_to_eur
            else:
                exchange_rate = self.get_exchange_rate(invoice.currency_id, target_currency_id, invoice.date_issue)

        # Get company name and address based on company language
        company_name_id = invoice.company_name_id
        company_address_id = invoice.company_address_id

        if target_lang != invoice.language_id.code:
            # Find company name in the company language
            company_name = self.env['kojto.base.names'].search([
                ('contact_id', '=', invoice.company_id.id),
                ('language_id.code', '=', target_lang),
                ('active', '=', True)
            ], limit=1)

            # Find company address in the company language
            company_address = self.env['kojto.base.addresses'].search([
                ('contact_id', '=', invoice.company_id.id),
                ('language_id.code', '=', target_lang),
                ('active', '=', True)
            ], limit=1)

            # Use translated company info if found
            if company_name:
                company_name_id = company_name
            if company_address:
                company_address_id = company_address

        # Create content data with currency conversion and filtering
        content_data = []
        for content in invoice.content.filtered(lambda c: not c.is_redistribution):
            content_dict = {
                'position': content.position,
                'name': content.name,
                'name_translation': content.name_translation,
                'quantity': content.quantity,
                'unit_id': content.unit_id,
                'unit_price': content.unit_price * exchange_rate,
                'pre_vat_total': content.pre_vat_total * exchange_rate,
                'vat_total': content.vat_total * exchange_rate,
                'total_price': content.total_price * exchange_rate,
                'custom_vat': content.custom_vat * exchange_rate if content.custom_vat else 0.0,
                'vat_treatment_id': content.vat_treatment_id,
                'vat_rate': content.vat_rate,
            }
            content_data.append(content_dict)

        # !!!IMPORTANT!!!  all overrides should be used as string with t-out in the template.
        # All overrides used with t-field will fallback to the original invoice's attribute (check the InvoiceWrapper from _create_invoice_for_pdf()).
        # TODO: find a way to use t-field for all overrides.

        # Create invoice data structure for PDF generation
        invoice_data = {
            # Basic invoice info
            "invoice_type": invoice.invoice_type,
            "consecutive_number": invoice.consecutive_number,
            "document_in_out_type": invoice.document_in_out_type,
            "name": invoice.name,
            "counterpartys_reference": invoice.counterpartys_reference,
            # Company info (may be translated)
            # should be used with t-out
            "company_name_id": company_name_id.name,
            # should be used with t-out
            "company_address_id": company_address_id.name,
            "company_tax_number_id": invoice.company_tax_number_id,
            "company_registration_number": invoice.company_registration_number,
            "company_bank_account_id": invoice.company_bank_account_id,
            # Counterparty info
            "counterparty_id": invoice.counterparty_id,
            "counterparty_address_id": invoice.counterparty_address_id,
            "counterparty_tax_number_id": invoice.counterparty_tax_number_id,
            "counterparty_registration_number": invoice.counterparty_registration_number,
            "counterparty_bank_account_id": invoice.counterparty_bank_account_id,
            # Invoice specific info
            "issued_by_name_id": invoice.issued_by_name_id,
            "payment_terms_id": invoice.payment_terms_id,
            # Dates
            "date_issue": invoice.date_issue,
            "date_due": invoice.date_due,
            "date_tax_event": invoice.date_tax_event,
            "parent_invoice_id": invoice.parent_invoice_id,
            "parent_invoice_date_issue": invoice.parent_invoice_date_issue,
            # Monetary values (converted to company currency)
            "currency_id": target_currency_id,
            "pre_vat_total": invoice.pre_vat_total * exchange_rate,
            "vat_total": invoice.vat_total * exchange_rate if invoice.custom_vat == 0 else invoice.custom_vat * exchange_rate,
            "total_price": invoice.total_price * exchange_rate,
            "custom_vat": invoice.custom_vat * exchange_rate if invoice.custom_vat else 0.0,
            # Content and text (content is handled specially in wrapper)
            "pre_content_text": invoice.pre_content_text,
            "pre_content_text_translation": invoice.pre_content_text_translation,
            "post_content_text": invoice.post_content_text,
            "post_content_text_translation": invoice.post_content_text_translation,
        }

        # Create invoice object for template rendering using original invoice structure
        invoice_for_pdf = self._create_invoice_for_pdf(invoice, invoice_data, content_data, target_lang)

        try:
            report_ref = self._report_ref
            suffix = ""

            if invoice.language_id.code != target_lang:
                report_ref = self._report_company_lang_ref
                suffix = "_CL"

            # Generate the base HTML using the company language report template
            report = self.env.ref(report_ref)
            html = report.with_context(lang=target_lang)._render_template(report_ref, {'docs': invoice_for_pdf})

            # Add original/copy versions and notes
            html = self.generate_original_copy_report_html(str(html), target_lang)
            html = self.generate_notes_report_html(html, invoice.pdf_notes)

            # Inject CSS styles
            html = self.inject_report_css(html)

            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp_file:
                # Generate PDF using WeasyPrint
                HTML(string=html).write_pdf(tmp_file.name)

                # Read the generated PDF
                with open(tmp_file.name, 'rb') as f:
                    pdf_content = f.read()

            # Create the PDF attachment with correct naming convention
            fname = f"{invoice.consecutive_number}_{invoice.subcode_id.maincode_id.maincode if invoice.subcode_id and invoice.subcode_id.maincode_id else 'NOMAIN'}.{invoice.subcode_id.code_id.code if invoice.subcode_id and invoice.subcode_id.code_id else 'NOCODE'}_{invoice.date_issue.strftime('%Y.%m.%d') if invoice.date_issue else 'NODATE'}_{invoice.counterparty_id.name or 'Unknown'}{suffix}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': fname,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': invoice._name,
                'res_id': invoice.id,
                'mimetype': 'application/pdf',
            })

            return attachment

        except Exception as e:
            raise UserError(_("Failed to generate PDF: %s") % str(e))

    def _create_invoice_for_pdf(self, original_invoice, invoice_data, content_data, company_lang):
        """Create an invoice object for PDF generation without modifying the original"""
        # Use with_context to create a copy that won't affect the original
        invoice_copy = original_invoice.with_context(lang=company_lang)

        # Create a custom wrapper that overrides field access
        class InvoiceWrapper:
            def __init__(self, invoice, data_overrides, content_overrides):
                self._invoice = invoice
                self._data_overrides = data_overrides
                self._content_overrides = content_overrides

            def __getattr__(self, name):
                # If we have an override for this field, use it

                if name in self._data_overrides:
                    return self._data_overrides[name]
                elif name == 'content':
                    return self._create_content_wrapper()
                else:
                    # Otherwise, use the original invoice's attribute
                    return getattr(self._invoice, name)

            def _create_content_wrapper(self):
                """Create wrapper for content items with overridden values"""
                content_wrappers = []
                filtered_content = self._invoice.content.filtered(lambda c: not c.is_redistribution)

                for i, content_override in enumerate(self._content_overrides):
                    # Get original content item (if available)
                    original_content = None
                    if i < len(filtered_content):
                        original_content = filtered_content[i]

                    # Create wrapper regardless of whether we have original content
                    content_wrapper = ContentWrapper(original_content, content_override)
                    content_wrappers.append(content_wrapper)

                return MockRecordset(content_wrappers)

            def filtered(self, func):
                """Support filtering for template compatibility"""
                return [self] if func(self) else []

        class ContentWrapper:
            def __init__(self, original_content, data_overrides):
                self._content = original_content
                self._data_overrides = data_overrides

            def __getattr__(self, name):
                # Avoid infinite recursion for private attributes
                if name.startswith('_'):
                    raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

                # First check if we have an override for this field
                if name in self._data_overrides:
                    return self._data_overrides[name]
                # Then check the original content if it exists
                elif self._content and hasattr(self._content, name):
                    return getattr(self._content, name)
                # For missing attributes, return appropriate defaults
                else:
                    # Common defaults for missing attributes
                    defaults = {
                        'id': 1,
                        'position': '',
                        'name': '',
                        'name_translation': '',
                        'quantity': 0.0,
                        'unit_price': 0.0,
                        'pre_vat_total': 0.0,
                        'vat_total': 0.0,
                        'total_price': 0.0,
                        'custom_vat': 0.0,
                        'vat_rate': 0.0,
                    }
                    return defaults.get(name, '')

        class MockRecordset:
            def __init__(self, items):
                self._items = items

            def __iter__(self):
                return iter(self._items)

            def __len__(self):
                return len(self._items)

            def __getitem__(self, index):
                return self._items[index]

            def __bool__(self):
                return bool(self._items)

            def filtered(self, func):
                return MockRecordset([item for item in self._items if func(item)])

            def exists(self):
                return bool(self._items)

        # Create the wrapper
        wrapper = InvoiceWrapper(invoice_copy, invoice_data, content_data)

        # Return as a list since the template expects 'docs' to be iterable
        return [wrapper]

    def export_to_ajur(self):
        exporter = self.env["kojto.finance.invoices.exportselectiontoajur"].with_context(selected_invoices=[self.id])
        return exporter.action_export_to_ajur()

    def print_document_as_pdf(self):
        """Generate a PDF document for the invoice using WeasyPrint.
        The PDF includes both original and copy versions, and notes if present.
        """
        for record in self:
            try:
                if record.document_in_out_type == "outgoing":
                    attachment = self._generate_pdf_attachment_in_lang_and_currency(record, target_lang=record.language_id.code, target_currency_id=record.currency_id)
                elif record.attachments:
                    attachment = record.attachments[0]
                if not attachment:
                    raise UserError(_("No PDF attachment found for the invoice."))

                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{attachment.id}?download=true',
                    'target': 'new',
                }
            except Exception as e:
                raise UserError(_("Failed to generate PDF: %s") % str(e))

    def print_document_as_pdf_company_language(self):
        """Generate a PDF document for the invoice in the company's default language.
        The PDF includes both original and copy versions, and notes if present.
        Uses company language template with translation fields.
        """
        for record in self:
            try:
                company_lang = record.company_id.language_id.code if record.company_id and record.company_id.language_id else 'en_US'
                company_currency = record.company_id.currency_id if record.company_id and record.company_id.currency_id else record.currency_id
                attachment = record._generate_pdf_attachment_in_lang_and_currency(record, target_lang=company_lang, target_currency_id=company_currency)
                # Return action to download the PDF
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{attachment.id}?download=true',
                    'target': 'new',
                }
            except Exception as e:
                raise UserError(_("Failed to generate PDF: %s") % str(e))

    def action_open_popup_pdf(self):
        return {
            "name": _("Invoice PDF"),
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoices",
            "view_mode": "form",
            "view_id": self.env.ref("kojto_finance.view_kojto_invoices_form_popup_pdf").id,
            "res_id": self.id,
            "target": "new"
        }

    @api.depends('attachments')
    def _compute_attachments_for_preview(self):
        for record in self:
            if record.document_in_out_type == "outgoing":
                record.attachments_for_preview = 1
                continue

            record.attachments_for_preview = len(record.attachments.filtered(lambda r: r.mimetype == 'application/pdf'))
        return {}

    @api.depends("attachments")
    def _compute_outgoing_attachment_1_pdf_bgn(self):
        for record in self:
            if record.document_in_out_type != "outgoing":
                record.attachment_1_outgoing_pdf_bgn = False
                continue
            record.attachment_1_outgoing_pdf_bgn = self._compute_outgoing_attachment_pdf(record, target_lang="bg_BG", target_currency_id=self.env.ref("base.BGN"))
        return {}

    @api.depends("attachments")
    def _compute_outgoing_attachment_1_pdf(self):
        for record in self:
            if record.document_in_out_type != "outgoing":
                record.attachment_1_outgoing_pdf = False
                continue
            record.attachment_1_outgoing_pdf = self._compute_outgoing_attachment_pdf(record, target_lang=record.language_id.code, target_currency_id=record.currency_id)
        return {}

    @api.depends('attachments')
    def _compute_incoming_attachment_1_pdf(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                record.attachment_1_incoming_pdf = False
                continue
            record.attachment_1_incoming_pdf = self._compute_incoming_attachment_pdf(record.attachments, 1)
        return {}

    @api.depends("attachments")
    def _compute_incoming_attachment_2_pdf(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                record.attachment_2_incoming_pdf = False
                continue
            record.attachment_2_incoming_pdf = self._compute_incoming_attachment_pdf(record.attachments, 2)
        return {}

    @api.depends("attachments")
    def _compute_incoming_attachment_3_pdf(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                record.attachment_3_incoming_pdf = False
                continue
            record.attachment_3_incoming_pdf = self._compute_incoming_attachment_pdf(record.attachments, 3)
        return {}

    @api.depends("attachments")
    def _compute_incoming_attachment_4_pdf(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                record.attachment_4_incoming_pdf = False
                continue
            record.attachment_4_incoming_pdf = self._compute_incoming_attachment_pdf(record.attachments, 4)
        return {}

    @api.depends("attachments")
    def _compute_incoming_attachment_5_pdf(self):
        for record in self:
            if record.document_in_out_type != "incoming":
                record.attachment_5_incoming_pdf = False
                continue
            record.attachment_5_incoming_pdf = self._compute_incoming_attachment_pdf(record.attachments, 5)
        return {}

    def _compute_incoming_attachment_pdf(self, attachments, index):
        pdf_attachments = attachments.filtered(lambda r: r.mimetype == "application/pdf")
        if len(pdf_attachments) < index:
            return False

        pdf_attachments = pdf_attachments.sorted("id", reverse=False)
        return pdf_attachments[index-1].datas

    def _compute_outgoing_attachment_pdf(self, invoice, target_lang, target_currency_id):
        return self._generate_pdf_attachment_in_lang_and_currency(invoice, target_lang=target_lang, target_currency_id=target_currency_id).datas

    @api.depends("content.pre_vat_total", "content.is_redistribution")
    def _compute_invoice_has_invalid_redistribution(self):
        for record in self:
            # Get all redistribution content items and sum their pre VAT totals
            redistribution_total = sum(
                record.content.filtered(lambda c: c.is_redistribution).mapped('pre_vat_total')
            )
            # Set the boolean to True if the redistribution total is not zero
            record.invoice_has_invalid_redistribution = redistribution_total != 0

    def copy_invoice(self):
        """Create a complete copy of the invoice including all contents and attachments"""
        self.ensure_one()
        if self.document_in_out_type == "incoming":
            words = self.consecutive_number.split(" ")
            new_consecutive_number = f"{words[0]} copy"
        else:
            new_consecutive_number = self.pick_next_consecutive_number()

        # Prepare default values for the new invoice
        default_values = {
            'consecutive_number': new_consecutive_number,
            'date_issue': fields.Date.today(),
            'date_due': fields.Date.today() + timedelta(days=7),
            'date_tax_event': fields.Date.today(),  # Set tax event date to today
            'accounting_op_date': False,
            'accounting_archive_number': False,
            'accounting_export_date': False,
            'accountant_id': False,
            'force_paid_status': False,
            'locked': False,
            'parent_invoice_id': False,
            'active': True,
            'custom_vat': 0.0,  # Ensure custom_vat is not copied
            'transaction_allocation_ids': [],  # Ensure allocations are not copied
        }

        # Create the new invoice
        new_invoice = self.copy(default_values)

        # Clear attachments to ensure they are not copied
        new_invoice.attachments = [(5, 0, 0)]

        # Copy all invoice contents
        for content in self.content:
            content_values = {
                'invoice_id': new_invoice.id,
                'name': content.name,
                'name_translation': content.name_translation,
                'position': content.position,
                'quantity': content.quantity,
                'unit_id': content.unit_id.id if content.unit_id else False,
                'unit_price': content.unit_price,
                'pre_vat_total': content.pre_vat_total,
                'vat_rate': content.vat_rate,
                'vat_treatment_id': content.vat_treatment_id.id if content.vat_treatment_id else False,
                'subcode_id': content.subcode_id.id if content.subcode_id else False,
                'accounting_template_id': content.accounting_template_id.id if content.accounting_template_id else False,
                'is_redistribution': content.is_redistribution,
                'identifier_id': content.identifier_id.id if content.identifier_id else False,
                'subtype_id': content.subtype_id.id if content.subtype_id else False,
            }
            self.env['kojto.finance.invoice.contents'].create(content_values)

        # Return action to open the new invoice
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.finance.invoices',
            'res_id': new_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends("language_id", "company_id")
    def _compute_invoice_is_in_company_language(self):
        for record in self:
            # Return False if company or company language is not set
            if not record.company_id or not record.company_id.language_id:
                record.invoice_is_in_company_language = False
            else:
                record.invoice_is_in_company_language = record.language_id.code == record.company_id.language_id.code
        return {}

    def compute_custom_vat_for_small_open_amounts(self):
        """
        Compute and insert custom VAT for the current invoice if it has a small open amount.
        The custom_vat is calculated as: custom_vat = vat_total - open_amount
        This helps balance small discrepancies in invoice amounts.
        """
        for invoice in self:
            # Check if this invoice has a small open amount
            if not (-0.05 <= invoice.open_amount <= 0.05) or invoice.open_amount == 0.0:
                continue

            if invoice.custom_vat != 0.0:
                continue

            if invoice.invoice_type not in ['invoice', 'proforma']:
                continue

            try:
                # Calculate custom VAT: custom_vat = vat_total - open_amount
                custom_vat = invoice.vat_total - invoice.open_amount

                # Update the invoice with the calculated custom VAT
                invoice.write({
                    'custom_vat': custom_vat
                })

            except Exception as e:
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Custom VAT Computation',
                'message': f'Custom VAT computation completed for the selected invoice(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.depends("total_price", "child_document_sum_all_totals", "base_currency_id")
    def _compute_payable_amount(self):
        for record in self:
            if record.base_currency_id and record.base_currency_id.name == 'BGN':
                total_price = record.total_price * (record.exchange_rate_to_bgn or 1.0)
            else:
                total_price = record.total_price * (record.exchange_rate_to_eur or 1.0)
            child_total = record.child_document_sum_all_totals  # Already in base currency
            record.payable_amount = total_price + child_total

    @api.depends("total_price", "base_currency_id", "exchange_rate_to_bgn", "exchange_rate_to_eur")
    def _compute_total_price_base_currency(self):
        for record in self:
            if record.base_currency_id and record.base_currency_id.name == 'BGN':
                record.total_price_base_currency = record.total_price * (record.exchange_rate_to_bgn or 1.0)
            elif record.base_currency_id and record.base_currency_id.name == 'EUR':
                record.total_price_base_currency = record.total_price * (record.exchange_rate_to_eur or 1.0)
            else:
                record.total_price_base_currency = 0.0

    @api.depends()
    def _compute_base_currency_id(self):
        contact = self.env['kojto.contacts'].browse(1)
        currency = contact.currency_id if contact.exists() and contact.currency_id else False
        for record in self:
            record.base_currency_id = currency

    def action_import_invoice_content(self):
        self.ensure_one()
        header = "Position\tName\tQuantity\tUnit\tUnit Price\tVAT Rate\tSubcode\n"
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

                subcode_name = content.subcode_id.name or '' if content.subcode_id else ''

                lines.append(
                    f"{position}\t{name}\t{content.quantity or 0.0}\t{content.unit_id.name or ''}\t{content.unit_price or 0.0}\t{content.vat_rate or 0.0}\t{subcode_name}"
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
            invoice_content_data = header + "\n".join(data_lines) + "\n"
        else:
            invoice_content_data = header

        return {
            "name": "Import Invoice Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoice.content.import.wizard",
            "view_mode": "form",
            "res_id": self.env["kojto.finance.invoice.content.import.wizard"].create({
                "invoice_id": self.id,
                "data": invoice_content_data
            }).id,
            "target": "new",
            "context": {"default_invoice_id": self.id}
        }

    def generate_cash_transaction(self):
        for invoice in self:
            if invoice.invoice_type != 'invoice':
                continue

            if not invoice.company_bank_account_id or invoice.company_bank_account_id.account_type.lower() != 'cash':
                continue

            transaction_direction = 'incoming' if invoice.document_in_out_type == 'outgoing' else 'outgoing'

            if invoice.document_in_out_type == 'outgoing':
                description = _("Payment received in cash account for invoice No. %s") % invoice.consecutive_number

            if invoice.document_in_out_type == 'incoming':
                description = _("Paid from cash account for invoice No. %s") % invoice.consecutive_number

            else:
                description = _("Payment received in cash account for invoice No. %s") % invoice.consecutive_number

            cashflow = self.env['kojto.finance.cashflow'].create({
                'bank_account_id': invoice.company_bank_account_id.id,
                'date_value': invoice.date_issue,
                'date_entry': fields.Date.today(),
                'transaction_direction': transaction_direction,
                'amount': invoice.total_price,
                'description': description,
                'counterparty_id': invoice.counterparty_id.id,
                'currency_id': invoice.currency_id.id,
                'exchange_rate_to_bgn': invoice.exchange_rate_to_bgn,
                'exchange_rate_to_eur': invoice.exchange_rate_to_eur,
                'creator_id': self.env.user.id,
            })

            existing_allocation = self.env['kojto.finance.cashflow.allocation'].search([
                ('transaction_id', '=', cashflow.id),
                ('invoice_id', '=', invoice.id)
            ], limit=1)

            if not existing_allocation:
                allocation_vals = {
                    'transaction_id': cashflow.id,
                    'invoice_id': invoice.id,
                    'subcode_id': invoice.subcode_id.id,
                    'amount': invoice.total_price,
                    'amount_base': invoice.total_price,
                    'description': f"Allocation for invoice {invoice.consecutive_number}",
                    'auto_allocated': True,
                }

                if invoice.invoice_acc_template_id:
                    allocation_vals['accounting_template_id'] = invoice.invoice_acc_template_id.id
                if invoice.invoice_acc_subtype_id:
                    allocation_vals['subtype_id'] = invoice.invoice_acc_subtype_id.id

                self.env['kojto.finance.cashflow.allocation'].create(allocation_vals)

            invoice._compute_paid()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def recompute_paid(self):
        """Recompute the paid field for selected invoices"""
        # Recompute dependencies in order: payable_amount -> paid_amount -> open_amount -> paid
        self._compute_payable_amount()
        self._compute_paid_amount()
        self._compute_open_amount()
        self._compute_paid()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Recomputed paid status for {len(self)} invoice(s).',
                'type': 'success',
                'sticky': False,
            }
        }
