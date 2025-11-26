# kojto_finance/models/kojto_finance_accounts_balance.py
from odoo import models, fields, api
from datetime import timedelta, datetime, date, time
from odoo.exceptions import ValidationError, UserError
import logging

logger = logging.getLogger(__name__)


class KojtoFinanceAccountsBalanceReport(models.TransientModel):
    _name = "kojto.finance.accounts.balance.report"
    _description = "Kojto Finance Accounts Balance Report"

    from_date = fields.Date(string="From Date", default=lambda self: datetime.now().replace(day=1).strftime("%Y-%m-%d"))
    to_date = fields.Date(string="To Date", default=fields.Date.today())

    bank_account_balance_id = fields.One2many("kojto.finance.single.account.balance", "bank_account_balance_id", string="Bank Account Balance", compute="_compute_bank_account_balance_id")


    start_amount_bgn = fields.Float(string="Starting Balance", compute="_compute_total_balance", digits=(12, 2))
    period_amount_bgn = fields.Float(string="Balance", compute="_compute_total_balance", digits=(12, 2))
    period_amount_in_bgn = fields.Float(string="Received", compute="_compute_total_balance", digits=(12, 2))
    period_amount_out_bgn = fields.Float(string="Sent", compute="_compute_total_balance", digits=(12, 2))
    period_amount_is_negative = fields.Boolean(string="Balance is negative", compute="_compute_total_balance_preview")

    start_amount_preview = fields.Html(string="Starting Balance", compute="_compute_total_balance_preview")
    period_amount_preview = fields.Html(string="Balance", compute="_compute_total_balance_preview")
    period_amount_in_preview = fields.Html(string="Received", compute="_compute_total_balance_preview")
    period_amount_out_preview = fields.Html(string="Sent", compute="_compute_total_balance_preview")

    def write(self, vals):
        return self

    @api.depends("from_date", "to_date")
    def _compute_total_balance_preview(self):
        for record in self:
            record.start_amount_preview = f"BGN {record.start_amount_bgn:,.2f}"
            record.period_amount_preview = f"BGN {record.period_amount_bgn:,.2f}"
            record.period_amount_in_preview = f"BGN {record.period_amount_in_bgn:,.2f}"
            record.period_amount_out_preview = f"BGN {record.period_amount_out_bgn:,.2f}"

    @api.depends("from_date", "to_date")
    def _compute_bank_account_balance_id(self):
        curr_company = self.env.company
        contacts_with_curr_company = self.env["kojto.contacts"].search([("res_company_id", "=", curr_company.id)])
        bank_accounts = []
        for contact in contacts_with_curr_company:
            bank_accounts.extend(filter(lambda x: x.active, contact.bank_accounts))

        for record in self:
            records = []
            for bank_account in bank_accounts:
                records.append(
                    self.env["kojto.finance.single.account.balance"].create(
                        {"bank_account_id": bank_account.id, "from_date": record.from_date, "to_date": record.to_date},
                    ),
                )
            record.bank_account_balance_id = self.env["kojto.finance.single.account.balance"].search([("id", "in", [r.id for r in records])])

    @api.depends("bank_account_balance_id")
    def _compute_total_balance(self):
        for record in self:
            record.start_amount_bgn = 0
            record.period_amount_bgn = 0
            record.period_amount_in_bgn = 0
            record.period_amount_out_bgn = 0
            record.period_amount_is_negative = False

            for balance in record.bank_account_balance_id:
                record.start_amount_bgn += balance.start_amount_bgn
                record.period_amount_bgn += balance.amount_bgn
                record.period_amount_in_bgn += balance.amount_in_bgn
                record.period_amount_out_bgn += balance.amount_out_bgn
                record.period_amount_is_negative = record.period_amount_bgn < 0


class KojtoFinanceSingleAccountBalance(models.TransientModel):
    _name = "kojto.finance.single.account.balance"
    _description = "Kojto Finance Single Account Balance"

    pad = fields.Char(string="Pad", default="")

    from_date = fields.Date(string="From Date", default=lambda self: datetime.now().replace(day=1).strftime("%Y-%m-%d"))
    to_date = fields.Date(string="To Date", default=fields.Date.today())

    bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account", required=True)
    bank_account_iban = fields.Char(related="bank_account_id.IBAN")
    bank_name = fields.Char(related="bank_account_id.bank_id.name")
    bank_currency = fields.Char(related="bank_account_id.currency_id.name")
    bank_account_balance_id = fields.Many2one("kojto.finance.single.account.balance", string="Bank Account Balance")
    bank_account_description = fields.Text(related="bank_account_id.description")

    start_amount_in = fields.Float(string="Starting Balance In", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    start_amount_out = fields.Float(string="Starting Balance Out", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    start_amount = fields.Float(string="Starting Balance", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)

    start_amount_in_bgn = fields.Float(string="Starting Balance In BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    start_amount_out_bgn = fields.Float(string="Starting Balance Out BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    start_amount_bgn = fields.Float(string="Starting Balance BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)

    amount_in = fields.Float(string="Amount In", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_out = fields.Float(string="Amount Out", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount = fields.Float(string="Balance", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_is_negative = fields.Boolean(string="Balance is negative", compute="_compute_balance_and_last_transaction_date")

    amount_in_bgn = fields.Float(string="Amoint In BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_out_bgn = fields.Float(string="Amount Out BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)
    amount_bgn = fields.Float(string="Balance BGN", compute="_compute_balance_and_last_transaction_date", digits=(12, 2), default=0)

    amount_in_preview = fields.Html(string="Received", compute="_compute_amount_preview", default=0)
    amount_out_preview = fields.Html(string="Sent", compute="_compute_amount_preview", default=0)
    amount_preview = fields.Html(string="Balance", compute="_compute_amount_preview", default=0)
    start_amount_preview = fields.Html(string="Starting Balance", compute="_compute_amount_preview", default=0)

    exchange_rate_to_bgn = fields.Float(string="Rate to BGN", compute="_compute_exchange_rate_to_bgn", default=0)

    def _get_all_transactions(self):
        return self.env["kojto.finance.cashflow"].search(
            [("bank_account_id", "=", self.bank_account_id.id), ("date_value", "<=", self.to_date)],
            order="date_value desc",
        )

    @api.depends("bank_account_id")
    def _compute_bank_description(self):
        for record in self:
            record.bank_description = f"{record.bank_account_id.description}/{record.bank_account_id.bank_id.name}/{record.bank_account_id.IBAN} - {record.bank_account_id.currency_id.name}"

    @api.depends("bank_account_id", "to_date", "from_date")
    def _compute_exchange_rate_to_bgn(self):
        to_currency = self.env.ref("base.BGN")
        for record in self:
            if record.bank_account_id.currency_id == to_currency:
                record.exchange_rate_to_bgn = 1.0
                continue

            exchange_rate = self.env["kojto.base.currency.exchange"].search(
                [
                    ("base_currency_id", "=", record.bank_account_id.currency_id.id),
                    ("target_currency_id", "=", to_currency.id),
                    ("datetime", "<=", record.to_date),
                ],
                order="datetime DESC",
                limit=1,
            )

            if not exchange_rate:
                # raise ValidationError(f"No exchange rate found for {record.bank_account_id.currency_id.name} to {to_currency.name} on {record.to_date}")
                record.exchange_rate_to_bgn = 0
                continue

            record.exchange_rate_to_bgn = exchange_rate.exchange_rate

    @api.depends("amount_in", "amount_out", "amount", "amount_is_negative", "bank_currency", "start_amount")
    def _compute_amount_preview(self):
        for record in self:
            record.start_amount_preview = f"{record.start_amount:,.2f} <span class=\"text-muted\">(BGN {record.start_amount_bgn:,.2f})</span>"
            record.amount_in_preview = f"{record.amount_in:,.2f}"
            record.amount_out_preview = f"{record.amount_out:,.2f}"
            record.amount_preview = f"{record.amount:,.2f} <span class=\"text-muted\">(BGN {record.amount_bgn:,.2f})</span>"

    @api.depends("from_date", "to_date", "bank_account_id")
    def _compute_balance_and_last_transaction_date(self):
        for record in self:
            all_transactions = record._get_all_transactions()

            for transaction in all_transactions:
                amount_in = 0
                amount_in_bgn = 0
                amount_out = 0
                amount_out_bgn = 0

                if transaction.transaction_direction == "incoming":
                    amount_in += transaction.amount
                    amount_in_bgn += transaction.amount * record.exchange_rate_to_bgn
                else:
                    amount_out += transaction.amount
                    amount_out_bgn += transaction.amount * record.exchange_rate_to_bgn

                if transaction.date_value < record.from_date:
                    record.start_amount_in += amount_in
                    record.start_amount_out += amount_out
                    record.start_amount_in_bgn += amount_in * record.exchange_rate_to_bgn
                    record.start_amount_out_bgn += amount_out * record.exchange_rate_to_bgn
                    continue

                record.amount_out += amount_out
                record.amount_out_bgn += amount_out_bgn

                record.amount_in += amount_in
                record.amount_in_bgn += amount_in_bgn

            record.start_amount = record.start_amount_in - abs(record.start_amount_out)
            record.start_amount_bgn = record.start_amount_in_bgn - abs(record.start_amount_out_bgn)

            record.amount = record.start_amount + record.amount_in - abs(record.amount_out)
            record.amount_bgn = record.start_amount_bgn + record.amount_in_bgn - abs(record.amount_out_bgn)

            record.amount_is_negative = record.amount < 0
