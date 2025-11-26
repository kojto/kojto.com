# kojto_finance/models/kojto_finance_accounting_accounts.py
from odoo import models, fields, api


class KojtoFinanceAccountingAccounts(models.Model):
    _name = "kojto.finance.accounting.accounts"
    _description = "Kojto Finance Accounting Accounts"
    _order = "name desc"
    _rec_name = "account_number"

    name = fields.Char(string="Name", required=True)
    account_number = fields.Char(string="Account Number", required=True)
    account_structure_template = fields.Char(string="Account Structure Template", default="")

    is_currency_account = fields.Boolean(string="Currency Account", default=False)
    is_catalogue_account = fields.Boolean(string="Catalogue Account", default=False)
    is_warehouse_account = fields.Boolean(string="Warehouse Account", default=False)
    is_ref_number_account = fields.Boolean(string="Ref Number Account", default=False)
