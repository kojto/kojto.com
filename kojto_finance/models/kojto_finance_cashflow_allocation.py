# -*- coding: utf-8 -*-
"""
Kojto Finance Cashflow Allocation Model

This module handles the allocation of cashflow transactions to specific subcodes,
invoices, and accounting templates.
"""

from collections import defaultdict
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
from ..utils.allocation_auto_accounting import auto_accounting_for_allocation


class KojtoFinanceCashflowAllocation(models.Model):
    _name = "kojto.finance.cashflow.allocation"
    _description = "Kojto Finance Cashflow Allocation"
    _order = "id desc"

    # Basic Information
    description = fields.Text(string="Description")
    # This is the amount in the currency of the transaction
    amount = fields.Float(string="Amount", digits=(9, 2))
    # This is the amount in the base currency of the document/item that the allocation is related to (For example: received payment via bank in EUR for invoice in USD)
    amount_base = fields.Float(string="Amount Base", digits=(9, 2))

    transaction_id = fields.Many2one("kojto.finance.cashflow", string="Cashflow", required=True, index=True, ondelete='cascade')
    transaction_id_number = fields.Integer(related="transaction_id.id", string="Transaction ID")
    transaction_date = fields.Date(related="transaction_id.date_value", string="Transaction Date")
    transaction_currency = fields.Many2one(related="transaction_id.bank_account_id.currency_id", string="Transaction Currency")
    transaction_exchange_rate_to_bgn = fields.Float(related="transaction_id.exchange_rate_to_bgn", string="Transaction Exchange Rate")

    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    invoice_domain = fields.Char(string="Invoice Domain", compute="_compute_invoice_domain")
    invoice_id = fields.Many2one("kojto.finance.invoices", string="Invoice", index=True, ondelete='cascade')

    accounting_template_domain = fields.Char(string="Accounting Template Domain", compute="_compute_accounting_template_domain")
    accounting_template_id = fields.Many2one("kojto.finance.accounting.templates", string="Accounting Template")
    accounting_ref_number = fields.Char(string="Accounting Reference Number")
    subtype_id = fields.Many2one("kojto.finance.accounting.subtypes", string="Subtype ID")

    requires_ref_number = fields.Boolean(related="accounting_template_id.requires_ref_number")
    requires_subtype_id = fields.Boolean(related="accounting_template_id.requires_subtype_id")

    currency_id = fields.Many2one(related="transaction_id.bank_account_id.currency_id", string="Currency")
    exchange_rate_to_bgn = fields.Float(related="transaction_id.exchange_rate_to_bgn", string="Exchange Rate to BGN")
    exchange_rate_to_eur = fields.Float(related="transaction_id.exchange_rate_to_eur", string="Exchange Rate to EUR")
    allocation_value_in_bgn = fields.Float(string="Allocation Value in BGN", compute="_compute_allocation_value", store=True)
    allocation_value_in_eur = fields.Float(string="Allocation Value in EUR", compute="_compute_allocation_value", store=True)

    cash_flow_only_inherited = fields.Boolean(related="subcode_id.cash_flow_only", string="Cash Flow Only (i)", help="Cash Flow Only (inherited from subcode)")
    cash_flow_only = fields.Boolean(string="Cash Flow Only", help="Cash Flow Only")
    auto_allocated = fields.Boolean(string="Auto Allocated", default=False)

    transaction_direction = fields.Selection(related="transaction_id.transaction_direction", string="Transaction Direction")
    bank_account_id = fields.Many2one(related="transaction_id.bank_account_id", string="Bank Account")

    @api.depends("amount", "exchange_rate_to_bgn", "exchange_rate_to_eur")
    def _compute_allocation_value(self):
        for record in self:
            # Compute value in BGN
            if record.amount and record.exchange_rate_to_bgn:
                record.allocation_value_in_bgn = record.amount * record.exchange_rate_to_bgn
            else:
                record.allocation_value_in_bgn = 0.0
            # Compute value in EUR
            if record.amount and record.exchange_rate_to_eur:
                record.allocation_value_in_eur = record.amount * record.exchange_rate_to_eur
            else:
                record.allocation_value_in_eur = 0.0

    @api.depends("amount", "exchange_rate_to_bgn")
    def _compute_value_in_bgn(self):
        for record in self:
            record.value_in_bgn = record.amount * record.exchange_rate_to_bgn

    @api.depends("transaction_id.transaction_direction")
    def _compute_accounting_template_domain(self):
        for record in self:
            record.accounting_template_domain = []
            if not record.transaction_id.transaction_direction:
                continue

            ptype = "cashflow_in" if record.transaction_id.transaction_direction == "incoming" else "cashflow_out"
            record.accounting_template_domain = [("template_type_id.primary_type", "=", ptype)]

    @api.onchange("transaction_id")
    def select_default_accounting_template(self):
        self.accounting_template_id = self.transaction_id.accounting_template_id

    @api.onchange("invoice_id")
    def set_amount_and_subcode_id(self):
        if not self.invoice_id:
            return

        # Always inherit subcode_id from the invoice
        if self.invoice_id.subcode_id:
            self.subcode_id = self.invoice_id.subcode_id

        contents = self.invoice_id.content
        if not contents:
            return

        allocated_subcodes = self.transaction_id.transaction_allocation_ids.mapped("subcode_id")

        amount_by_subcode = defaultdict(lambda: {"amount": 0, "subcode_id": None, "currency_id": None, "exchange_rate_to_bgn": 1.0})
        for line in contents:
            amount_by_subcode[line.subcode_id.id]["amount"] += line.total_price
            amount_by_subcode[line.subcode_id.id]["subcode_id"] = line.subcode_id
            amount_by_subcode[line.subcode_id.id]["currency_id"] = line.currency_id
            amount_by_subcode[line.subcode_id.id]["exchange_rate_to_bgn"] = line.invoice_id.exchange_rate_to_bgn

        amount_by_subcode = sorted(amount_by_subcode.items(), key=lambda x: x[1]["subcode_id"].id, reverse=True)

        # Calculate available amount without causing circular dependency
        total_allocated = sum(self.transaction_id.transaction_allocation_ids.mapped("amount"))
        available_amount = self.transaction_id.amount - total_allocated

        # Use the available amount or the first subcode amount, whichever is smaller
        filtered_amount_by_subcode = [x for x in amount_by_subcode if x[1]["subcode_id"] not in allocated_subcodes]
        if not filtered_amount_by_subcode:
            return

        first_subcode_amount = filtered_amount_by_subcode[0][1]["amount"]
        self.amount = min(available_amount, first_subcode_amount)  # Always positive
        self.amount_base = self.amount

    @api.depends("transaction_id.counterparty_id", "transaction_id.date_value")
    def _compute_invoice_domain(self):
        for record in self:
            if record.transaction_id and record.transaction_id.counterparty_id:
                record.invoice_domain = str([
                    ("counterparty_id", "=", record.transaction_id.counterparty_id.id),
                    ("paid", "=", False)
                ])
            else:
                record.invoice_domain = str([("id", "=", False)])

    def open_o2m_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Open Allocation Record",
            "res_model": "kojto.finance.cashflow.allocation",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.onchange('transaction_id')
    def _onchange_transaction_id(self):
        if self.transaction_id:
            self.description = self.transaction_id.description

    def auto_accounting(self):
        """
        Automatically set accounting fields for this allocation using AI.
        Analyzes similar historical allocations and recommends accounting field values.
        """
        import logging
        _logger = logging.getLogger(__name__)

        for allocation in self:
            _logger.info("=== AUTO ACCOUNTING BUTTON PRESSED ===")
            _logger.info("Allocation ID: %s", allocation.id)
            _logger.info("Allocation subcode: %s", allocation.subcode_id.name if allocation.subcode_id else "None")
            _logger.info("Transaction counterparty: %s", allocation.transaction_id.counterparty_id.name if allocation.transaction_id and allocation.transaction_id.counterparty_id else "None")
            _logger.info("Transaction direction: %s", allocation.transaction_id.transaction_direction if allocation.transaction_id else "None")
            _logger.info("Amount: %s", allocation.amount)

            result = auto_accounting_for_allocation(allocation)
            _logger.info("Auto accounting result: %s", result)

            # Invalidate cache to ensure UI shows updated values
            allocation.invalidate_recordset([
                'accounting_template_id',
                'accounting_ref_number',
                'subtype_id',
                'cash_flow_only'
            ])

            # Show notification
            allocation.env['bus.bus']._sendone(
                allocation.env.user.partner_id,
                'simple_notification',
                {
                    'title': 'Auto Accounting',
                    'message': result,
                    'type': 'success' if 'Successfully' in result else 'warning',
                }
            )

        # Return True to refresh the current view without navigation
        return True

    @api.model
    def create(self, vals):
        allocation = super().create(vals)
        allocation._update_invoice_payment_status()
        return allocation

    def write(self, vals):
        result = super().write(vals)
        for allocation in self:
            allocation._update_invoice_payment_status()
        return result

    def unlink(self):
        invoice_ids = self.mapped('invoice_id.id')
        result = super().unlink()

        if invoice_ids:
            self._update_invoice_payment_status_after_deletion(invoice_ids)
        return result

    def _update_invoice_payment_status(self):
        # Removed automatic setting of 'paid' field
        # The 'paid' field should only be set manually from the frontend
        pass

    def _update_invoice_payment_status_after_deletion(self, invoice_ids):
        # Removed automatic setting of 'paid' field
        # The 'paid' field should only be set manually from the frontend
        pass
