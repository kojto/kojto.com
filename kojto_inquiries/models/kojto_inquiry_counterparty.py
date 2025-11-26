from odoo import models, fields, api, _

class KojtoInquiryCounterparty(models.Model):
    _name = "kojto.inquiry.counterparty"
    _description = "Kojto Inquiry Sounterparty"
    _order = "print_number desc"
    _inherit = ["kojto.library.printable"]

    name = fields.Char(string="Name", compute="generate_inquiry_counterparty_name", store=True)

    inquiry_id = fields.Many2one("kojto.inquiries", string="Inquiry")
    is_interested = fields.Boolean(string="Is interested")
    print_number = fields.Integer(string="Print Number", readonly=True)

    # Counterparty Information
    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", ondelete="set null")
    counterparty_type = fields.Selection(related="counterparty_id.contact_type", string="Counterparty Type")
    counterparty_registration_number = fields.Char(related="counterparty_id.registration_number", string="Registration Number")
    counterparty_registration_number_type = fields.Char(related="counterparty_id.registration_number_type", string="Registration Number Type")
    counterparty_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank account")
    counterparty_name_id = fields.Many2one("kojto.base.names", string="Name on document")
    counterparty_address_id = fields.Many2one("kojto.base.addresses", string="Address")
    counterparty_tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    counterparty_phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    counterparty_email_id = fields.Many2one("kojto.base.emails", string="Email")

    language_id = fields.Many2one(related="inquiry_id.language_id", string="Language", store=False)
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")

    # Reports config for printing
    _report_ref = "kojto_inquiries.report_kojto_inquiry_counterparty"

    system_has_contracts = fields.Selection([("False", "False"), ("True", "True")], compute="compute_model_existence", string="Has Contracts")
    system_has_invoices = fields.Selection([("False", "False"), ("True", "True")], compute="compute_model_existence", string="Has Finance Invoices")
    system_has_offers = fields.Selection([("False", "False"), ("True", "True")], compute="compute_model_existence", string="Has Offers")

    @api.depends("inquiry_id", "counterparty_id")
    def generate_inquiry_counterparty_name(self):
        for record in self:
            if record.inquiry_id and record.counterparty_id:
                inquiry_name = record.inquiry_id.name or ""
                counterparty_name = record.counterparty_id.name or ""
                record.name = f"{inquiry_name} - {counterparty_name}"
            elif record.inquiry_id:
                record.name = record.inquiry_id.name or ""
            elif record.counterparty_id:
                record.name = record.counterparty_id.name or ""
            else:
                record.name = ""

    def prepare_document_data(self, document_type):
        common_data = {
            "subcode_id": self.inquiry_id.subcode_id.id,
            "subject": self.inquiry_id.subject,
            "active": True,
            "document_in_out_type": "outgoing",
            "payment_terms_id": self.inquiry_id.payment_terms_id.id if self.inquiry_id.payment_terms_id else False,
            "currency_id": self.inquiry_id.currency_id.id if self.inquiry_id.currency_id else False,
            "language_id": self.inquiry_id.language_id.id if self.inquiry_id.language_id else False,
            "incoterms_id": self.inquiry_id.incoterms_id.id if self.inquiry_id.incoterms_id else False,
            "incoterms_address": self.inquiry_id.incoterms_address or "",
            "company_id": self.inquiry_id.company_id.id if self.inquiry_id.company_id else False,
            "company_address_id": (self.inquiry_id.company_address_id.id if self.inquiry_id.company_address_id else False),
            "company_tax_number_id": (self.inquiry_id.company_tax_number_id.id if self.inquiry_id.company_tax_number_id else False),
            "company_bank_account_id": (self.inquiry_id.company_bank_account_id.id if self.inquiry_id.company_bank_account_id else False),
            "company_name_id": self.inquiry_id.company_name_id.id if self.inquiry_id.company_name_id else False,
            "counterparty_id": self.counterparty_id.id if self.counterparty_id else False,
            "counterparty_name_id": self.counterparty_name_id.id if self.counterparty_name_id else False,
            "counterparty_address_id": self.counterparty_address_id.id if self.counterparty_address_id else False,
            "counterparty_tax_number_id": (self.counterparty_tax_number_id.id if self.counterparty_tax_number_id else False),
            "counterparty_bank_account_id": (self.counterparty_bank_account_id.id if self.counterparty_bank_account_id else False),
            "counterparty_phone_id": self.counterparty_phone_id.id if self.counterparty_phone_id else False,
            "counterparty_email_id": self.counterparty_email_id.id if self.counterparty_email_id else False,
            "pre_content_text": self.inquiry_id.pre_content_text or "",
            "post_content_text": self.inquiry_id.post_content_text or "",
            "issued_by_name_id": self.inquiry_id.issued_by_name_id.id if self.inquiry_id.issued_by_name_id else False,
        }

        if document_type == "contract":
            common_data.update({"contract_type": "contract"})
        elif document_type == "invoice":
            common_data.update({
                "invoice_type": "invoice",
                "parent_invoice_id": False,
                "date_issue": self.inquiry_id.date_issue if self.inquiry_id.date_issue else fields.Date.today(),
                "date_tax_event": self.inquiry_id.date_issue if self.inquiry_id.date_issue else fields.Date.today(),
            })

        return common_data

    def create_offer_for_counterparty(self):
        offer_data = {
            "subcode_id": self.inquiry_id.subcode_id.id,
            "subject": self.inquiry_id.subject,
            "active": True,
            "document_in_out_type": "outgoing",
            "payment_terms_id": self.inquiry_id.payment_terms_id.id if self.inquiry_id.payment_terms_id else False,
            "currency_id": self.inquiry_id.currency_id.id if self.inquiry_id.currency_id else False,
            "language_id": self.inquiry_id.language_id.id if self.inquiry_id.language_id else False,
            "incoterms_id": self.inquiry_id.incoterms_id.id if self.inquiry_id.incoterms_id else False,
            "incoterms_address": self.inquiry_id.incoterms_address or "",
            "company_id": self.inquiry_id.company_id.id if self.inquiry_id.company_id else False,
            "company_address_id": (self.inquiry_id.company_address_id.id if self.inquiry_id.company_address_id else False),
            "company_tax_number_id": (self.inquiry_id.company_tax_number_id.id if self.inquiry_id.company_tax_number_id else False),
            "company_email_id": self.inquiry_id.company_email_id.id if self.inquiry_id.company_email_id else False,
            "company_bank_account_id": (self.inquiry_id.company_bank_account_id.id if self.inquiry_id.company_bank_account_id else False),
            "company_name_id": self.inquiry_id.company_name_id.id if self.inquiry_id.company_name_id else False,
            "counterparty_id": self.counterparty_id.id if self.counterparty_id else False,
            "counterparty_name_id": self.counterparty_name_id.id if self.counterparty_name_id else False,
            "counterparty_address_id": self.counterparty_address_id.id if self.counterparty_address_id else False,
            "counterparty_tax_number_id": (self.counterparty_tax_number_id.id if self.counterparty_tax_number_id else False),
            "counterparty_bank_account_id": (self.counterparty_bank_account_id.id if self.counterparty_bank_account_id else False),
            "counterparty_phone_id": self.counterparty_phone_id.id if self.counterparty_phone_id else False,
            "counterparty_email_id": self.counterparty_email_id.id if self.counterparty_email_id else False,
            "pre_content_text": self.inquiry_id.pre_content_text or "",
            "post_content_text": self.inquiry_id.post_content_text or "",
            "issued_by_name_id": self.inquiry_id.issued_by_name_id.id if self.inquiry_id.issued_by_name_id else False,
        }

        new_offer = self.inquiry_id.env["kojto.offers"].create(offer_data)

        for content in self.inquiry_id.content:
            self.inquiry_id.env["kojto.offer.contents"].create(
                {
                    "offer_id": new_offer.id,
                    "name": content.name,
                    "position": content.position,
                    "quantity": content.quantity,
                    "unit_id": content.unit_id.id if content.unit_id else False,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offers",
            "res_id": new_offer.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_contract_for_counterparty(self):
        contract_data = self.prepare_document_data("contract")
        new_contract = self.inquiry_id.env["kojto.contracts"].create(contract_data)

        for content in self.inquiry_id.content:
            self.inquiry_id.env["kojto.contract.contents"].create(
                {
                    "contract_id": new_contract.id,
                    "name": content.name,
                    "position": content.position,
                    "quantity": content.quantity,
                    "unit_id": content.unit_id.id if content.unit_id else False,
                }
            )

        new_contract.onchange_company_or_counterparty()

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.contracts",
            "res_id": new_contract.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_invoice_for_counterparty(self):
        invoice_data = self.prepare_document_data("invoice")

        default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([("vat_in_out_type", "=", "outgoing"), ("vat_treatment_type", "=", "full_vat")], limit=1)
        if not default_vat_treatment:
            default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([("vat_in_out_type", "=", "outgoing")], limit=1)

        # Calculate exchange rates based on currency
        currency_id = self.inquiry_id.currency_id if self.inquiry_id.currency_id else self.env.ref("base.EUR")
        if currency_id.name == 'EUR':
            exchange_rate_to_bgn = 1.95583
            exchange_rate_to_eur = 1.0
        elif currency_id.name == 'BGN':
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 0.51129
        else:
            # For other currencies, default to EUR rates if no exchange rate found
            exchange_rate_to_bgn = 1.95583
            exchange_rate_to_eur = 1.0

        invoice_data.update({
            "invoice_vat_treatment_id": default_vat_treatment.id if default_vat_treatment else False,
            "exchange_rate_to_bgn": exchange_rate_to_bgn,
            "exchange_rate_to_eur": exchange_rate_to_eur,
        })
        new_invoice = self.inquiry_id.env["kojto.finance.invoices"].create(invoice_data)

        for content in self.inquiry_id.content:
            self.inquiry_id.env["kojto.finance.invoice.contents"].create(
                {
                    "invoice_id": new_invoice.id,
                    "name": content.name,
                    "position": content.position,
                    "quantity": content.quantity,
                    "unit_id": content.unit_id.id if content.unit_id else False,
                    "vat_treatment_id": default_vat_treatment.id,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoices",
            "res_id": new_invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends()
    def compute_model_existence(self):
        for record in self:
            record.system_has_contracts = str(self.env["ir.model"].search([("model", "=", "kojto.contracts")], limit=1) is not None)
            record.system_has_invoices = str(self.env["ir.model"].search([("model", "=", "kojto.finance.invoices")], limit=1) is not None)
            record.system_has_offers = str(self.env["ir.model"].search([("model", "=", "kojto.offers")], limit=1) is not None)
        return {}
