from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoBaseBankAccounts(models.Model):
    _name = "kojto.base.bank.accounts"
    _description = "Kojto Base Bank Accounts"
    _rec_name = "IBAN"
    _order = "IBAN desc"

    BIC = fields.Char(related="bank_id.BIC", string="BIC", store=True)  # Required for migration
    bank_id = fields.Many2one("kojto.base.banks", string="Bank Name")
    color = fields.Char(string="Color", size=30)
    currency_id = fields.Many2one("res.currency", string="Currency")
    description = fields.Text(string="Description")
    IBAN = fields.Char(string="IBAN")
    active = fields.Boolean(string="Is Active", default=True)
    name = fields.Char(string="Name")
    ref_number = fields.Char(string="Reference Number", default="0")
    account_type = fields.Selection(selection=[("bank", "Bank"), ("cash", "Cash"),], string="Account Type", default="bank",)

    @api.constrains("IBAN")
    def _check_iban_unique(self):
        for record in self:
            if self.search_count([("IBAN", "=", record.IBAN), ("id", "!=", record.id)]):
                raise ValidationError("The IBAN is already registered.")
