# -*- coding: utf-8 -*-
"""
Kojto Finance Balance Wizard

Purpose:
--------
Wizard that allows users to select a date range and calculate financial balance
at different consolidation levels (Company, Main Code, Code, Subcode).
Calculates revenue and expenses using the same logic as the revenue and expense dashboard.
"""

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
from .utils.kojto_finance_balance_wizard_calculations import calculate_subcode_balance
from .utils.kojto_finance_balance_wizard_actions import action_export_balance_to_excel


class KojtoFinanceBalanceWizard(models.TransientModel):
    _name = "kojto.finance.balance.wizard"
    _description = "Kojto Finance Balance Wizard"

    # Date range fields
    date_from = fields.Date(string="From Date", required=True, default=lambda self: self._default_date_from())
    date_to = fields.Date(string="To Date", required=True, default=lambda self: self._default_date_to())

    # Results fields
    subcode_balance_line_ids = fields.One2many("kojto.finance.balance.subcode.line", "wizard_id", string="Subcode Balance Lines")
    code_balance_line_ids = fields.One2many("kojto.finance.balance.code.line", "wizard_id", string="Code Balance Lines")
    maincode_balance_line_ids = fields.One2many("kojto.finance.balance.maincode.line", "wizard_id", string="Main Code Balance Lines")
    company_balance_line_ids = fields.One2many("kojto.finance.balance.company.line", "wizard_id", string="Company Balance Lines")

    # Summary fields
    total_subcodes = fields.Integer(string="Total Subcodes", compute="_compute_totals")
    total_activities = fields.Integer(string="Total Activities", compute="_compute_totals")
    total_outgoing_pre_vat_total = fields.Float(string="Total Outgoing Pre-VAT", digits=(16, 2), compute="_compute_totals")
    total_incoming_pre_vat_total = fields.Float(string="Total Incoming Pre-VAT", digits=(16, 2), compute="_compute_totals")
    total_invoiceless_revenue = fields.Float(string="Total Invoiceless Revenue", digits=(16, 2), compute="_compute_totals")
    total_invoiceless_expenses = fields.Float(string="Total Invoiceless Expenses", digits=(16, 2), compute="_compute_totals")
    total_result = fields.Float(string="Total Result", digits=(16, 2), compute="_compute_totals")
    total_time_tracking_hours = fields.Float(string="Total TT Hours", digits=(16, 2), compute="_compute_totals")
    total_time_tracking_total = fields.Float(string="Total TT Total", digits=(16, 2), compute="_compute_totals")
    total_assets_total = fields.Float(string="Total Assets Total", digits=(16, 2), compute="_compute_totals")

    # Currency field for monetary widget (same logic as revenue expense dashboard)
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id", readonly=True)

    @api.depends()
    def _compute_currency_id(self):
        """Always use EUR currency (id 125)"""
        eur_currency = self.env.ref('base.EUR')
        for record in self:
            record.currency_id = eur_currency.id if eur_currency else 125

    def _default_date_from(self):
        """Default to January 1st of current year"""
        today = datetime.now().date()
        return today.replace(month=1, day=1)

    def _default_date_to(self):
        """Default to today"""
        return datetime.now().date()

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-calculate balance when wizard is created"""
        wizards = super().create(vals_list)
        for wizard in wizards:
            if wizard.date_from and wizard.date_to:
                wizard._create_balance_lines()
        return wizards

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        """Recalculate balance when dates change"""
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                return {
                    'warning': {
                        'title': 'Invalid Date Range',
                        'message': 'From date cannot be after To date.',
                    }
                }
            self._create_balance_lines()

    def _create_balance_lines(self):
        """Create balance lines from calculated data"""
        self.ensure_one()

        # Calculate balance data
        calculated_data = calculate_subcode_balance(
            self.env,
            self.date_from,
            self.date_to
        )

        # Convert data dictionaries to Odoo command tuples and add wizard_id
        subcode_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['subcode_balance_lines']
        ]
        code_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['code_balance_lines']
        ]
        maincode_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['maincode_balance_lines']
        ]
        company_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['company_balance_lines']
        ]

        # Update wizard with results
        self.write({
            'subcode_balance_line_ids': [(5, 0, 0)] + subcode_lines,
            'code_balance_line_ids': [(5, 0, 0)] + code_lines,
            'maincode_balance_line_ids': [(5, 0, 0)] + maincode_lines,
            'company_balance_line_ids': [(5, 0, 0)] + company_lines,
        })


    @api.depends("subcode_balance_line_ids")
    def _compute_totals(self):
        """Compute total counts and financial totals"""
        for record in self:
            record.total_subcodes = len(record.subcode_balance_line_ids)
            record.total_activities = 0
            record.total_outgoing_pre_vat_total = sum(record.subcode_balance_line_ids.mapped("outgoing_pre_vat_total"))
            record.total_incoming_pre_vat_total = sum(record.subcode_balance_line_ids.mapped("incoming_pre_vat_total"))
            record.total_invoiceless_revenue = sum(record.subcode_balance_line_ids.mapped("invoiceless_revenue"))
            record.total_invoiceless_expenses = sum(record.subcode_balance_line_ids.mapped("invoiceless_expenses"))
            record.total_time_tracking_hours = sum(record.subcode_balance_line_ids.mapped("time_tracking_hours"))
            record.total_time_tracking_total = sum(record.subcode_balance_line_ids.mapped("time_tracking_total"))
            record.total_assets_total = sum(record.subcode_balance_line_ids.mapped("assets_total"))
            record.total_result = (
                record.total_outgoing_pre_vat_total
                - record.total_incoming_pre_vat_total
                - record.total_invoiceless_expenses
                + record.total_invoiceless_revenue
                + record.total_time_tracking_total
                + record.total_assets_total
            )

    def action_export_balance_to_excel(self):
        """Export all balance data to Excel with separate sheets for each consolidation level"""
        return action_export_balance_to_excel(self)

    def action_save_balance(self):
        """Save the current balance calculation (same as export but without creating file)"""
        self.ensure_one()

        # Ensure balance lines are created/updated (same check as export)
        if not self.subcode_balance_line_ids:
            if self.date_from and self.date_to:
                self._create_balance_lines()
            else:
                raise UserError("No data to save. Please set date range and compute the balance first.")

        # Return a client action that does nothing (keeps window open, same pattern as export)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Balance Saved',
                'message': f'Balance for period {self.date_from} to {self.date_to} has been recomputed and saved.',
                'type': 'success',
                'sticky': False,
            }
        }

