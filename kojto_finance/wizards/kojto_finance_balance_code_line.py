# -*- coding: utf-8 -*-
"""
Kojto Finance Code Balance Line Model
"""

from odoo import models, fields
from datetime import datetime
from .utils.kojto_finance_balance_wizard_calculations import get_breakdown_records


class KojtoFinanceBalanceCodeLine(models.TransientModel):
    _name = "kojto.finance.balance.code.line"
    _description = "Code Balance Line"
    _order = "code_name"

    wizard_id = fields.Many2one("kojto.finance.balance.wizard", string="Wizard", ondelete="cascade", default=lambda self: self._default_wizard_id())

    code_id = fields.Many2one("kojto.commission.codes", string="Code")
    maincode = fields.Char(related="code_id.maincode_id.maincode", string="Main Code", readonly=True)
    code = fields.Char(related="code_id.code", string="Code", readonly=True)
    code_name = fields.Char(related="code_id.name", string="Code Name", readonly=True)
    description = fields.Char(related="code_id.description", string="Description", readonly=True)

    # Same fields as revenue expense dashboard
    currency_id = fields.Many2one("res.currency", string="Currency", related="wizard_id.currency_id", readonly=True)
    date_from = fields.Date(string="From Date", readonly=True)
    date_to = fields.Date(string="To Date", readonly=True)

    outgoing_pre_vat_total = fields.Float(string='Pre-VAT Tot. (OUT)', digits=(16, 2), default=0.0, help="Pre-VAT total for outgoing invoices")
    incoming_pre_vat_total = fields.Float(string='Pre-VAT Tot. (IN)', digits=(16, 2), default=0.0, help="Pre-VAT total for incoming invoices")
    invoiceless_revenue = fields.Float(string='Invoiceless Revenue', digits=(16, 2), default=0.0, help="Invoiceless revenue")
    invoiceless_expenses = fields.Float(string='Invoiceless Expenses', digits=(16, 2), default=0.0, help="Invoiceless expenses")
    time_tracking_hours = fields.Float(string='TT Hours', digits=(16, 2), default=0.0, help="Time tracking hours")
    time_tracking_total = fields.Float(string='TT Total', digits=(16, 2), default=0.0, help="Time tracking total value")
    assets_total = fields.Float(string='Assets Total', digits=(16, 2), default=0.0, help="Asset works total value")
    result = fields.Float(string='Result', digits=(16, 2), default=0.0, help="Result (calculated)")

    # M2M fields for breakdown records (populated on-demand, not computed automatically)
    outgoing_pre_vat_total_breakdown = fields.Many2many('kojto.finance.invoice.contents', 'bal_code_line_inv_out_rel', 'balance_line_id', 'invoice_content_id', string="Outgoing Pre-VAT Breakdown")
    incoming_pre_vat_total_breakdown = fields.Many2many('kojto.finance.invoice.contents', 'bal_code_line_inv_in_rel', 'balance_line_id', 'invoice_content_id', string="Incoming Pre-VAT Breakdown")
    invoiceless_revenue_breakdown = fields.Many2many('kojto.finance.cashflow.allocation', 'bal_code_line_cash_rev_rel', 'balance_line_id', 'allocation_id', string="Invoiceless Revenue Breakdown")
    invoiceless_expenses_breakdown = fields.Many2many('kojto.finance.cashflow.allocation', 'bal_code_line_cash_exp_rel', 'balance_line_id', 'allocation_id', string="Invoiceless Expenses Breakdown")
    hr_time_tracking_breakdown = fields.Many2many('kojto.hr.time.tracking', 'bal_code_line_tt_rel', 'balance_line_id', 'time_tracking_id', string="Time Tracking Breakdown")
    assets_works_breakdown = fields.Many2many('kojto.asset.works', 'bal_code_line_aw_rel', 'balance_line_id', 'asset_work_id', string="Assets Works Breakdown")


    def _default_wizard_id(self):
        """Get wizard_id from context if available"""
        context = self.env.context
        if context.get('default_wizard_id'):
            return context.get('default_wizard_id')
        elif context.get('active_model') == 'kojto.finance.balance.wizard' and context.get('active_id'):
            return context.get('active_id')
        return False



    def action_view_breakdown(self):
        """Open the breakdown form view and recalculate M2M breakdown fields"""
        self.ensure_one()

        # Recalculate M2M breakdown fields before opening the view
        if self.date_from and self.date_to and self.code_id:
            datetime_from = datetime.combine(self.date_from, datetime.min.time())
            datetime_to = datetime.combine(self.date_to, datetime.max.time())
            breakdown = get_breakdown_records(
                self.env, self.date_from, self.date_to, datetime_from, datetime_to,
                code_ids=[self.code_id.id]
            )
            # Populate all M2M fields
            self.outgoing_pre_vat_total_breakdown = breakdown['outgoing_pre_vat_total'].ids
            self.incoming_pre_vat_total_breakdown = breakdown['incoming_pre_vat_total'].ids
            self.invoiceless_revenue_breakdown = breakdown['invoiceless_revenue'].ids
            self.invoiceless_expenses_breakdown = breakdown['invoiceless_expenses'].ids
            self.hr_time_tracking_breakdown = breakdown['hr_time_tracking'].ids
            self.assets_works_breakdown = breakdown['assets_works'].ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Code Balance Breakdown',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('kojto_finance.view_kojto_finance_balance_code_line_form').id,
            'target': 'new',
        }

    def action_export_breakdown_to_excel(self):
        """Export breakdown data to Excel with separate sheets for each breakdown type"""
        self.ensure_one()
        from .utils.kojto_finance_balance_wizard_actions import action_export_breakdown_to_excel
        return action_export_breakdown_to_excel(self.sudo())
