# kojto_finance/models/kojto_finance_accounts_balance.py
from odoo import models, fields, api
from odoo.fields import Command
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KojtoFinanceAccountsBalanceReport(models.TransientModel):
    _name = "kojto.finance.accounts.balance.report"
    _description = "Kojto Finance Accounts Balance Report"

    from_date = fields.Date(string="From Date", default=lambda self: datetime.now().replace(day=1).strftime("%Y-%m-%d"))
    to_date = fields.Date(string="To Date", default=fields.Date.today())

    bank_account_balance_id = fields.One2many("kojto.finance.single.account.balance", "bank_account_balance_id", string="Bank Account Balance", compute="_compute_bank_account_balance_id")

    # Report currency (from contact id=1)
    report_currency_id = fields.Many2one("res.currency", string="Report Currency", compute="_compute_report_currency_id", readonly=True)

    # Amounts in contact id=1 currency
    start_amount = fields.Float(string="Starting Balance", compute="_compute_total_balance", digits=(12, 2))
    period_amount = fields.Float(string="Ending Balance", compute="_compute_total_balance", digits=(12, 2))
    period_amount_in = fields.Float(string="Received", compute="_compute_total_balance", digits=(12, 2))
    period_amount_out = fields.Float(string="Sent", compute="_compute_total_balance", digits=(12, 2))
    period_amount_is_negative = fields.Boolean(string="Balance is negative", compute="_compute_total_balance")

    def write(self, vals):
        return self

    @api.depends()
    def _compute_report_currency_id(self):
        """Get currency from contact id=1"""
        contact = self.env['kojto.contacts'].browse(1)
        for record in self:
            if contact.exists() and contact.currency_id:
                record.report_currency_id = contact.currency_id.id
            else:
                # Fallback to BGN
                record.report_currency_id = self.env.ref('base.BGN').id

    @api.depends("from_date", "to_date")
    def _compute_bank_account_balance_id(self):
        curr_company = self.env.company
        contacts_with_curr_company = self.env["kojto.contacts"].search([("res_company_id", "=", curr_company.id)])
        bank_accounts = []
        for contact in contacts_with_curr_company:
            bank_accounts.extend(filter(lambda x: x.active, contact.bank_accounts))

        for record in self:
            # Clear existing records
            record.bank_account_balance_id.unlink()

            record_ids = []
            for bank_account in bank_accounts:
                new_record = self.env["kojto.finance.single.account.balance"].create(
                    {
                        "bank_account_id": bank_account.id,
                        "bank_account_balance_id": record.id,
                        "from_date": record.from_date,
                        "to_date": record.to_date
                    },
                )
                record_ids.append(new_record.id)

            # Use Command.set to properly link the records
            record.bank_account_balance_id = [Command.set(record_ids)]

    @api.depends("bank_account_balance_id")
    def _compute_total_balance(self):
        for record in self:
            record.start_amount = 0
            record.period_amount = 0
            record.period_amount_in = 0
            record.period_amount_out = 0
            record.period_amount_is_negative = False

            for balance in record.bank_account_balance_id:
                # Sum converted amounts in report currency (contact id=1 currency)
                record.start_amount += balance.start_amount * balance.exchange_rate
                record.period_amount += balance.amount_contact_currency
                record.period_amount_in += balance.amount_in * balance.exchange_rate
                record.period_amount_out += balance.amount_out * balance.exchange_rate

            record.period_amount_is_negative = record.period_amount < 0
