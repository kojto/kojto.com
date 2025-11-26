from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
import uuid
from ..utils.kojto_warehouses_name_generator import get_temp_name, get_final_name

class KojtoWarehousesReceipts(models.Model):
    _name = "kojto.warehouses.receipts"
    _description = "Warehouse Receipts"
    _rec_name = "name"
    _order = "id desc"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_warehouses.print_receipt"

    name = fields.Char(string="Name", required=True, copy=False, default=lambda self: 'RCP.000000')
    active = fields.Boolean(string="Is Active", default=True)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env["res.lang"].search([("code", "=", self.env.user.lang)], limit=1))
    to_from_store = fields.Selection(selection=[('to_store', "To Store"), ('from_store', "From Store")], string="Direction", compute="_compute_to_from_store", store=True)
    store_id = fields.Many2one("kojto.base.stores", string="Store", required=True, domain="[('active', '=', True)]")
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today)
    issued_by = fields.Many2one("kojto.hr.employees", string="Issued By", default=lambda self: self.env.user.employee, readonly=True)
    issued_to = fields.Char(string="Issued To", required=True)
    transaction_ids = fields.Many2many("kojto.warehouses.transactions", string="Transactions", domain="[('receipt_id', '=', False), '|', ('to_from_store', '=', to_from_store), ('to_from_store', 'in', ['to_store', 'from_store'])]")
    description = fields.Text(string="Description")
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment", copy=False)

    # Company Information
    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True)
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', company_id)]")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', company_id)]")
    company_phone_id = fields.Many2one("kojto.base.phones", string="Phone", domain="[('contact_id', '=', company_id)]")
    company_email_id = fields.Many2one("kojto.base.emails", string="Emails", domain="[('contact_id', '=', company_id)]")

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    @api.onchange("company_id")
    def onchange_company(self):
        fields_to_reset = {
            "company_name_id": "company_id",
            "company_address_id": "company_id",
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
                ("kojto.base.phones", "company_phone_id"),
                ("kojto.base.emails", "company_email_id"),
            ]:
                record = self.env[model].search([("contact_id", "=", company.id), ("active", "=", True)], limit=1)
                if record:
                    setattr(self, field, record.id)

    @api.depends('transaction_ids', 'transaction_ids.to_from_store')
    def _compute_to_from_store(self):
        for record in self:
            if record.transaction_ids:
                # Use the to_from_store of the first transaction
                record.to_from_store = record.transaction_ids[0].to_from_store
            else:
                # When no transactions, set to null
                record.to_from_store = False
                if not record.name or not record.name.startswith('RCP.'):
                    record.name = 'RCP.000000'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'transaction_ids' in vals:
                transaction_ids = []
                for cmd in vals.get('transaction_ids', []):
                    if cmd[0] in (1, 4):
                        transaction_ids.append(cmd[1])
                    elif cmd[0] == 6:
                        transaction_ids.extend(cmd[2])
                if transaction_ids:
                    # Check for already linked transactions
                    invalid = self.env['kojto.warehouses.transactions'].browse(transaction_ids).filtered(lambda t: t.receipt_id)
                    if invalid:
                        raise UserError(_("Cannot create receipt. Transactions already linked: %s") % ", ".join(f"{t.name} (to {t.receipt_id.name})" for t in invalid))

                    # Check transaction types
                    transactions = self.env['kojto.warehouses.transactions'].browse(transaction_ids)
                    types = set(transactions.mapped('to_from_store'))
                    if len(types) > 1:
                        raise UserError(_("All transactions must be of the same type (To Store or From Store)."))

        with self.env.cr.savepoint():
            records = super().create(vals_list)
            for record in records:
                if not record.name or not record.name.startswith('RCP.'):
                    record.write({'name': 'RCP.000000'})
                if record.id:
                    record.write({'name': f'RCP.{record.id:06d}'})
                    # Update transactions with receipt
                    if record.transaction_ids:
                        record.transaction_ids.write({'receipt_id': record.id})
        return records

    def write(self, vals):
        if 'transaction_ids' in vals:
            transaction_ids = []
            for cmd in vals.get('transaction_ids', []):
                if cmd[0] in (1, 4):
                    transaction_ids.append(cmd[1])
                elif cmd[0] == 6:
                    transaction_ids.extend(cmd[2])
            if transaction_ids:
                # Check for already linked transactions
                invalid = self.env['kojto.warehouses.transactions'].browse(transaction_ids).filtered(lambda t: t.receipt_id and t.receipt_id != self)
                if invalid:
                    raise UserError(_("Cannot assign transactions already linked: %s") % ", ".join(f"{t.name} (to {t.receipt_id.name})" for t in invalid))

                # Check transaction types
                transactions = self.env['kojto.warehouses.transactions'].browse(transaction_ids)
                if self.transaction_ids:
                    # If receipt has transactions, new ones must match receipt type
                    invalid_types = transactions.filtered(lambda t: t.to_from_store != self.to_from_store)
                    if invalid_types:
                        raise UserError(_("All transactions must match receipt type (%s). Invalid: %s") %
                                      (self.to_from_store, ", ".join(invalid_types.mapped('name'))))
                else:
                    # If no existing transactions, all new ones must be of the same type
                    types = set(transactions.mapped('to_from_store'))
                    if len(types) > 1:
                        raise UserError(_("All transactions must be of the same type (To Store or From Store)."))

        result = super().write(vals)

        # Update transaction receipts after write
        if 'transaction_ids' in vals:
            # Clear receipt from removed transactions
            old_transactions = self.transaction_ids - self.env['kojto.warehouses.transactions'].browse(transaction_ids)
            if old_transactions:
                old_transactions.write({'receipt_id': False})
            # Set receipt on new transactions
            new_transactions = self.env['kojto.warehouses.transactions'].browse(transaction_ids) - self.transaction_ids
            if new_transactions:
                new_transactions.write({'receipt_id': self.id})

        return result

    def unlink(self):
        # Clear receipt from transactions before unlinking
        self.transaction_ids.write({'receipt_id': False})
        return super().unlink()

    def action_print_pdf(self):
        return self.print_document_as_pdf()

    def action_add_transactions(self):
        self.ensure_one()
        domain = [('receipt_id', '=', False)]
        if self.to_from_store:
            domain.append(('to_from_store', '=', self.to_from_store))
        else:
            domain.append(('to_from_store', 'in', ['to_store', 'from_store']))

        return {
            'name': _('Add Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'default_receipt_id': [(6, 0, [self.id])],
                'create': False,
                'edit': False,
                'delete': False,
            },
            'target': 'new',
            'flags': {
                'action_buttons': True,
                'headless': True,
            },
        }

    def action_select_transactions(self):
        self.ensure_one()
        return {
            'name': _('Select Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'list,form',
            'domain': [
                ('receipt_id', '=', False),
                ('to_from_store', '=', self.to_from_store)
            ],
            'context': {
                'default_receipt_id': self.id,
                'create': False,
                'edit': False,
                'delete': False,
            },
            'target': 'current',
        }

    @api.constrains('transaction_ids', 'to_from_store')
    def _check_transaction_types(self):
        for record in self:
            if record.transaction_ids:
                invalid_transactions = record.transaction_ids.filtered(lambda t: t.to_from_store != record.to_from_store)
                if invalid_transactions:
                    raise ValidationError(_("All transactions must match receipt type (%s). Invalid: %s") %
                                        (record.to_from_store, ", ".join(invalid_transactions.mapped('name'))))

    @api.constrains('transaction_ids')
    def _check_transaction_uniqueness(self):
        for record in self:
            if record.transaction_ids:
                invalid = record.transaction_ids.filtered(lambda t: t.receipt_id and t.receipt_id != record)
                if invalid:
                    raise ValidationError(_("Transactions already linked to other receipts: %s") % ", ".join(f"{t.name} (to {t.receipt_id.name})" for t in invalid))

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if record.name:
                existing = self.search([('name', '=', record.name), ('id', '!=', record.id)], limit=1)
                if existing:
                    raise ValidationError(_("A receipt with name '%s' already exists.") % record.name)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list:
            company = self.env["kojto.contacts"].browse(1)
            if not company.exists():
                raise ValidationError(_("Company contact not found."))

            # Get the default language
            lang_id = self.env['res.lang']._lang_get(self.env.user.lang).id

            for model, field in [
                ("kojto.base.names", "company_name_id"),
                ("kojto.base.addresses", "company_address_id"),
                ("kojto.base.phones", "company_phone_id"),
                ("kojto.base.emails", "company_email_id"),
            ]:
                if field in fields_list:
                    # For names and addresses, try to find one matching the language first
                    if model in ['kojto.base.names', 'kojto.base.addresses']:
                        record = self.env[model].search([
                            ("contact_id", "=", company.id),
                            ("active", "=", True),
                            ("language_id", "=", lang_id)
                        ], limit=1)
                        if not record:
                            # If no record with matching language, get any active record
                            record = self.env[model].search([
                                ("contact_id", "=", company.id),
                                ("active", "=", True)
                            ], limit=1)
                    else:
                        # For phones and emails, just get the first active record
                        record = self.env[model].search([
                            ("contact_id", "=", company.id),
                            ("active", "=", True)
                        ], limit=1)
                    if record:
                        res[field] = record.id

        return res
