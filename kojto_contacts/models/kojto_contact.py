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

    @api.model
    def ensure_contact_1_exists(self):
        """
        Ensure contact with id=1 exists. Creates "Our Company" contact if it doesn't exist.
        This method is called during module installation and upgrade.
        """
        # Fixed date for create_date and write_date
        fixed_date = '2000-01-01 00:00:00'

        # Check if contact with id=1 exists
        self.env.cr.execute("SELECT id, res_company_id FROM kojto_contacts WHERE id = 1")
        existing = self.env.cr.fetchone()

        if existing:
            # Contact exists, check if res_company_id is set to anything
            res_company_id = existing[1] if existing and len(existing) > 1 else None
            if res_company_id is not None:
                # res_company_id is already set to something, do nothing
                return

            # Update the dates and res_company_id
            self.env.cr.execute("""
                UPDATE kojto_contacts
                SET create_date = %s, write_date = %s, res_company_id = 1
                WHERE id = 1
            """, (fixed_date, fixed_date))
            self.env.cr.commit()
            self.env.clear()
            return

        # Check if client_number 0 is already taken by another contact
        self.env.cr.execute("SELECT id FROM kojto_contacts WHERE client_number = 0 AND id != 1 LIMIT 1")
        conflicting = self.env.cr.fetchone()
        if conflicting:
            # Temporarily change the conflicting contact's client_number to allow us to create id=1
            # We'll use a negative number temporarily, then the admin can fix it
            temp_number = -1
            self.env.cr.execute("""
                SELECT id FROM kojto_contacts WHERE client_number = %s LIMIT 1
            """, (temp_number,))
            while self.env.cr.fetchone():
                temp_number -= 1
                self.env.cr.execute("""
                    SELECT id FROM kojto_contacts WHERE client_number = %s LIMIT 1
                """, (temp_number,))

            self.env.cr.execute("""
                UPDATE kojto_contacts
                SET client_number = %s
                WHERE id = %s
            """, (temp_number, conflicting[0]))

        # Get admin user
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        user_id = admin_user.id if admin_user else 1

        # Get default language
        lang = self.env.ref('base.lang_en', raise_if_not_found=False)
        language_id = lang.id if lang else None

        # Insert contact with id=1 using SQL with fixed dates
        if language_id:
            self.env.cr.execute("""
                INSERT INTO kojto_contacts (
                    id, contact_type, name, client_number, active, language_id, res_company_id,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    1, 'company', 'Our Company', 0, true, %s, 1,
                    %s, %s, %s, %s
                )
            """, (language_id, user_id, fixed_date, user_id, fixed_date))
        else:
            self.env.cr.execute("""
                INSERT INTO kojto_contacts (
                    id, contact_type, name, client_number, active, res_company_id,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    1, 'company', 'Our Company', 0, true, 1,
                    %s, %s, %s, %s
                )
            """, (user_id, fixed_date, user_id, fixed_date))

        # Create the name record using ORM (which will handle all relationships)
        try:
            if 'kojto.base.names' in self.env.registry:
                self.env['kojto.base.names'].create({
                    'name': 'Our Company',
                    'contact_id': 1,
                    'active': True,
                })
        except Exception:
            # If creating the name fails, we still have the contact
            pass

        # Update sequence to ensure it's at least at 2
        try:
            self.env.cr.execute("""
                SELECT setval(
                    pg_get_serial_sequence('kojto_contacts', 'id'),
                    GREATEST(1, COALESCE((SELECT MAX(id) FROM kojto_contacts), 0))
                )
            """)
        except Exception:
            # Sequence might not exist or table might use a different sequence name
            pass

        self.env.cr.commit()
        self.env.clear()  # Clear cache so the new record is available
