# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Subcode Line Model
"""

from odoo import models, fields, api
from odoo.exceptions import UserError


class KojtoWarehousesBalanceSubcodeLine(models.TransientModel):
    _name = "kojto.warehouses.balance.subcode.line"
    _description = "Warehouse Balance Subcode Line"
    _order = "subcode_id"

    wizard_id = fields.Many2one("kojto.warehouses.balance.wizard", string="Wizard", ondelete="cascade", required=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", readonly=True)
    subcode_description = fields.Char(string="Subcode Description", related="subcode_id.description", readonly=True, store=True)
    transaction_ids = fields.Many2many("kojto.warehouses.transactions", "wh_bal_subcode_tx_rel", "subcode_line_id", "transaction_id", string="Transactions", readonly=True)

    # Aggregated fields
    total_quantity = fields.Float(string="Total Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_to_store_quantity = fields.Float(string="To Store Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_from_store_quantity = fields.Float(string="From Store Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_value_eur = fields.Float(string="Total Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_to_store_value_eur = fields.Float(string="To Store Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_from_store_value_eur = fields.Float(string="From Store Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    transaction_count = fields.Integer(string="Transaction Count", readonly=True, compute="_compute_totals")

    currency_id = fields.Many2one("res.currency", string="Currency", related="wizard_id.currency_id", readonly=True)


    @api.depends('transaction_ids', 'transaction_ids.transaction_quantity', 'transaction_ids.transaction_value_pre_vat_eur', 'transaction_ids.to_from_store')
    def _compute_totals(self):
        """Compute aggregated totals for this subcode - optimized single pass"""
        for record in self:
            transactions = record.transaction_ids
            if not transactions:
                record.transaction_count = 0
                record.total_quantity = 0.0
                record.total_to_store_quantity = 0.0
                record.total_from_store_quantity = 0.0
                record.total_value_eur = 0.0
                record.total_to_store_value_eur = 0.0
                record.total_from_store_value_eur = 0.0
                continue

            # Batch read all needed fields in one query
            tx_data = transactions.read([
                'transaction_quantity',
                'transaction_value_pre_vat_eur',
                'to_from_store'
            ])

            # Single pass through data to compute all totals
            total_to_store_quantity = 0.0
            total_from_store_quantity = 0.0
            total_value_eur = 0.0
            total_to_store_value_eur = 0.0
            total_from_store_value_eur = 0.0

            for tx in tx_data:
                qty = tx.get('transaction_quantity', 0.0) or 0.0
                value_eur = tx.get('transaction_value_pre_vat_eur', 0.0) or 0.0
                to_from = tx.get('to_from_store', '')

                total_value_eur += value_eur

                if to_from == 'to_store':
                    total_to_store_quantity += qty
                    total_to_store_value_eur += value_eur
                elif to_from == 'from_store':
                    total_from_store_quantity += qty
                    total_from_store_value_eur += abs(value_eur)

            record.transaction_count = len(transactions)
            record.total_to_store_quantity = total_to_store_quantity
            record.total_from_store_quantity = total_from_store_quantity
            # Total quantity = To Store - From Store
            record.total_quantity = total_to_store_quantity - total_from_store_quantity
            record.total_value_eur = total_value_eur
            record.total_to_store_value_eur = total_to_store_value_eur
            record.total_from_store_value_eur = total_from_store_value_eur

    def action_view_transactions(self):
        """Open a window showing all transactions for this subcode"""
        self.ensure_one()

        # Read all values immediately to avoid transient record access issues
        # Use read() to get all values in one query before any potential deletion
        values = self.read(['subcode_id', 'wizard_id'])[0]

        subcode_id = values.get('subcode_id') and values['subcode_id'][0] or False
        subcode_name = values.get('subcode_id') and values['subcode_id'][1] or "N/A"
        wizard_id = values.get('wizard_id') and values['wizard_id'][0] or False

        # Read wizard values separately
        date_from = False
        date_to = False
        if wizard_id:
            wizard_values = self.env['kojto.warehouses.balance.wizard'].browse(wizard_id).read(['date_from', 'date_to'])
            if wizard_values:
                date_from = wizard_values[0].get('date_from')
                date_to = wizard_values[0].get('date_to')

        if not subcode_id:
            raise UserError("No subcode selected.")

        if not date_from or not date_to:
            raise UserError("Date range is not set.")

        # Get transactions for this subcode in the date range
        domain = [
            ('subcode_id', '=', subcode_id),
            ('date_issue', '>=', date_from),
            ('date_issue', '<=', date_to),
        ]

        return {
            'name': f'Transactions - Subcode {subcode_name} ({date_from} to {date_to})',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {},
            'target': 'current',
        }

    def action_export_subcode_to_excel(self):
        """Export transactions for this subcode to Excel"""
        self.ensure_one()
        from .utils.kojto_warehouses_balance_wizard_actions import action_export_subcode_transactions_to_excel
        return action_export_subcode_transactions_to_excel(self.sudo())

