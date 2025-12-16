# kojto_finance/models/kojto_finance_single_account_balance.py
from odoo import models, fields, api
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KojtoFinanceSingleAccountBalance(models.TransientModel):
    _name = "kojto.finance.single.account.balance"
    _description = "Kojto Finance Single Account Balance"

    pad = fields.Char(string="Pad", default="")

    from_date = fields.Date(string="From Date", default=lambda self: datetime.now().replace(day=1).strftime("%Y-%m-%d"))
    to_date = fields.Date(string="To Date", default=fields.Date.today())

    bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account", required=True)
    bank_account_iban = fields.Char(related="bank_account_id.IBAN")
    bank_name = fields.Char(related="bank_account_id.bank_id.name")
    bank_account_balance_id = fields.Many2one("kojto.finance.accounts.balance.report", string="Report", ondelete="cascade")
    bank_account_description = fields.Text(related="bank_account_id.description")

    # Amounts in original account currency
    start_amount = fields.Float(string="Starting Balance", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_in = fields.Float(string="Received", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_out = fields.Float(string="Sent", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount = fields.Float(string="Ending Balance", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)

    # Converted amounts in contact id=1 currency (report currency)
    amount_contact_currency = fields.Float(string="Ending Balance in Report Currency", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_is_negative = fields.Boolean(string="Balance is negative", compute="_compute_balance_and_last_transaction_date")

    # Last transaction date
    last_transaction_date = fields.Date(string="Last Transaction Date", compute="_compute_balance_and_last_transaction_date")

    # Currency fields
    account_currency_id = fields.Many2one("res.currency", string="Account Currency", related="bank_account_id.currency_id", readonly=True)
    report_currency_id = fields.Many2one("res.currency", string="Report Currency", compute="_compute_report_currency_id", readonly=True)

    # Exchange rate (fixed: 1 EUR = 1.95583 BGN)
    exchange_rate = fields.Float(string="Exchange Rate", compute="_compute_exchange_rate", default=1.95583)

    def _get_all_transactions(self):
        return self.env["kojto.finance.cashflow"].search(
            [("bank_account_id", "=", self.bank_account_id.id), ("date_value", "<=", self.to_date)],
            order="date_value desc",
        )

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

    @api.depends("bank_account_id", "from_date", "to_date")
    def _compute_exchange_rate(self):
        """Fixed exchange rate: 1 EUR = 1.95583 BGN"""
        EUR_TO_BGN = 1.95583
        BGN_TO_EUR = 1.0 / EUR_TO_BGN

        contact = self.env['kojto.contacts'].browse(1)
        contact_currency = contact.currency_id if contact.exists() else self.env.ref("base.BGN")

        for record in self:
            bank_currency = record.bank_account_id.currency_id

            if bank_currency == contact_currency:
                record.exchange_rate = 1.0
            elif bank_currency.name == 'EUR' and contact_currency.name == 'BGN':
                record.exchange_rate = EUR_TO_BGN
            elif bank_currency.name == 'BGN' and contact_currency.name == 'EUR':
                record.exchange_rate = BGN_TO_EUR
            else:
                record.exchange_rate = 1.0

    @api.depends("from_date", "to_date", "bank_account_id", "exchange_rate")
    def _compute_balance_and_last_transaction_date(self):
        for record in self:
            all_transactions = record._get_all_transactions()

            start_amount_in = 0
            start_amount_out = 0
            amount_in = 0
            amount_out = 0
            last_date = False

            for transaction in all_transactions:
                # Track last transaction date
                if not last_date or transaction.date_value > last_date:
                    last_date = transaction.date_value

                # Keep amounts in original currency
                if transaction.transaction_direction == "incoming":
                    amount_in_orig = transaction.amount
                    amount_out_orig = 0
                else:
                    amount_in_orig = 0
                    amount_out_orig = transaction.amount

                if transaction.date_value < record.from_date:
                    start_amount_in += amount_in_orig
                    start_amount_out += amount_out_orig
                    continue

                amount_in += amount_in_orig
                amount_out += amount_out_orig

            # Calculate in original currency
            record.start_amount = start_amount_in - abs(start_amount_out)
            record.amount_in = amount_in
            record.amount_out = amount_out
            record.amount = record.start_amount + amount_in - abs(amount_out)

            # Convert ending balance to report currency
            record.amount_contact_currency = record.amount * record.exchange_rate
            record.amount_is_negative = record.amount < 0

            # Set last transaction date
            record.last_transaction_date = last_date

