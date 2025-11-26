# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import re


class KojtoContacts(models.Model):
    _name = "kojto.contacts"
    _description = "Kojto Contacts"
    _rec_name = "name"
    _order = "name desc"
    _sql_constraints = [("client_number_unique", "UNIQUE(client_number)", "Client number must be unique.")]

    contact_type = fields.Selection(selection=[("person", "Person"), ("company", "Company")], string="Contact Type", default="company", required=True)
    name = fields.Char(string="Name", required=True)
    title = fields.Char(string="Title")
    comment = fields.Char(string="Comment")

    currency_id = fields.Many2one("res.currency", string="Currency")

    registration_number = fields.Char(string="Registration number")
    registration_number_type = fields.Char(string="Registration number type")
    client_number = fields.Integer(string="Client Number", default=lambda self: self._get_default_client_number(), required=True)
    website = fields.Char(string="Website")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    res_company_id = fields.Many2one("res.company", string="Res Company ID", ondelete="set null")
    company_logo = fields.Binary(string="Company Logo", attachment=True)
    company_logo_filename = fields.Char(string="Logo Filename")
    company_logo_base64 = fields.Text(string="Company Logo (Base64)")  # No default

    contact_tax_number_summary = fields.Text(string="Tax Number(s)", compute="_compute_contact_tax_number_summary")

    @api.onchange("company_logo")
    def compute_company_logo_base64(self):
        for record in self:
            if record.company_logo:
                decoded_image = base64.b64decode(record.company_logo)
                record.company_logo_base64 = (
                    "data:image/svg;base64," + base64.b64encode(decoded_image).decode("utf-8")
                )
            else:
                record.company_logo_base64 = False

    @api.depends('tax_numbers', 'tax_numbers.tax_number')
    def _compute_contact_tax_number_summary(self):
        for contact in self:
            tax_numbers = contact.tax_numbers.mapped('tax_number')
            contact.contact_tax_number_summary = '\n'.join(filter(None, tax_numbers))

    @api.constrains("company_id")
    def check_unique_company_id(self):
        for contact in self:
            if contact.company_id:
                existing_contact = self.env["kojto.contacts"].search(
                    [("company_id", "=", contact.company_id.id), ("id", "!=", contact.id)],
                    limit=1
                )
                if existing_contact:
                    raise ValidationError(
                        "A user can only be associated with one contact. "
                        "User (ID: %s) is already associated with contact (ID: %s)."
                        % (contact.company_id.name, existing_contact.name)
                    )

    @api.constrains("client_number")
    def _check_unique_client_number(self):
        for record in self:
            if record.client_number:
                existing = self.env["kojto.contacts"].search([
                    ("client_number", "=", record.client_number),
                    ("id", "!=", record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Client number must be unique."))

    names = fields.One2many("kojto.base.names", "contact_id", string="Names", context={'active_test': False})
    addresses = fields.One2many("kojto.base.addresses", "contact_id", string="Addresses", context={'active_test': False})
    emails = fields.One2many("kojto.base.emails", "contact_id", string="Emails", context={'active_test': False})
    phones = fields.One2many("kojto.base.phones", "contact_id", string="Phones", context={'active_test': False})
    bank_accounts = fields.One2many("kojto.base.bank.accounts", "contact_id", string="Bank accounts", context={'active_test': False})
    tax_numbers = fields.One2many("kojto.base.tax.numbers", "contact_id", string="Tax numbers", context={'active_test': False})
    certificates = fields.One2many("kojto.base.certificates", "contact_id", string="Certificates", context={'active_test': False})
    company_rel_ids = fields.One2many("kojto.contacts.positions", "person_id", string="Related people")
    people_rel_ids = fields.One2many("kojto.contacts.positions", "company_id", string="Related companies")
    active = fields.Boolean(string="Active", default=True)
    is_non_EU = fields.Boolean(string="Non EU based", default=False)

    credit_limit = fields.One2many("kojto.contacts.credit.limit", "contact_id", string="Credit Limits")
    current_credit_limit = fields.Char(string="Current Credit Limit", compute="_compute_current_credit_limit", store=True)

    # AI Configuration Fields (only visible for first contact)
    ai_api_url = fields.Char(string="AI API URL")
    ai_api_key = fields.Char(string="AI API Key")

    @api.depends(
        "credit_limit",
        "credit_limit.credit_limit",
        "credit_limit.currency_id",
        "credit_limit.datetime_start",
        "credit_limit.datetime_end"
    )
    def _compute_current_credit_limit(self):
        current_datetime = fields.Datetime.now()
        for contact in self:
            valid_credit_limits = contact.credit_limit.filtered(
                lambda cl: cl.datetime_start <= current_datetime
                and (not cl.datetime_end or cl.datetime_end >= current_datetime)
            )
            if valid_credit_limits:
                current_limit = valid_credit_limits.sorted(
                    key=lambda x: x.datetime_start, reverse=True
                )[:1]
                if current_limit:
                    amount = current_limit.credit_limit
                    currency = current_limit.currency_id.name or ""
                    contact.current_credit_limit = f"{amount} {currency}"
                else:
                    contact.current_credit_limit = "-"
            else:
                contact.current_credit_limit = "-"

    def create(self, vals):
        contact = super(KojtoContacts, self).create(vals)
        if "name" in vals and vals["name"]:
            self.env["kojto.base.names"].create(
                {"name": vals["name"], "contact_id": contact.id, "active": True}
            )
        return contact

    def write(self, vals):
        result = super(KojtoContacts, self).write(vals)
        if "name" in vals and vals["name"]:
            for record in self:
                name_record = self.env["kojto.base.names"].search(
                    [("contact_id", "=", record.id)], limit=1
                )
                if name_record:
                    name_record.write({"name": vals["name"]})
                else:
                    self.env["kojto.base.names"].create(
                        {"name": vals["name"], "contact_id": record.id, "active": True}
                    )
        return result

    def _get_default_client_number(self):
        max_number = 999999999  # 9 digits max
        latest_contact = self.env["kojto.contacts"].search(
            [],
            order="client_number DESC",
            limit=1
        )
        if latest_contact and latest_contact.client_number:
            latest_number = latest_contact.client_number
        else:
            latest_number = 0
        new_number = latest_number + 1
        if new_number > max_number:
            raise ValidationError(
                _("Client number cannot exceed 9 digits (999,999,999).")
            )
        return new_number

    def update_cyrillic_names_language(self):
        bg_lang = self.env.ref('base.lang_bg')
        for name in self.env['kojto.base.names'].search([]):
            if name.name and re.search(r'[\u0400-\u04FF]', name.name):
                name.language_id = bg_lang

    @api.model
    def get_ai_config(self):
        """
        Get AI configuration from the first contact (ID=1).
        Returns a dict with 'api_url' and 'api_key', or defaults if first contact doesn't exist.
        """
        first_contact = self.env['kojto.contacts'].browse(1)
        if first_contact.exists():
            return {
                'api_url': first_contact.ai_api_url or "https://ai.prototyp.bg:443/v1",
                'api_key': first_contact.ai_api_key or "ollama"
            }
        return {
            'api_url': "https://ai.prototyp.bg:443/v1",
            'api_key': "ollama"
        }
