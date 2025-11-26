# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Subcode Identifier Line Model
"""

from odoo import models, fields, api
from odoo.exceptions import UserError


class KojtoWarehousesBalanceSubcodeIdentifierLine(models.TransientModel):
    _name = "kojto.warehouses.balance.subcode.identifier.line"
    _description = "Warehouse Balance Subcode Identifier Line"
    _order = "subcode_id, identifier_id"

    wizard_id = fields.Many2one("kojto.warehouses.balance.wizard", string="Wizard", ondelete="cascade", required=True)
    identifier_id = fields.Char(string="Identifier ID", readonly=True)
    identifier_name = fields.Char(string="Identifier Name", readonly=True, compute="_compute_subcode_identifier_info", store=True)
    identifier_type = fields.Selection(selection=[("material", "Material"), ("goods", "Goods"), ("asset", "Asset")], string="Identifier Type", readonly=True, compute="_compute_subcode_identifier_info", store=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", readonly=True)
    subcode_description = fields.Char(string="Subcode Description", related="subcode_id.description", readonly=True, store=True)
    transaction_ids = fields.Many2many("kojto.warehouses.transactions", "wh_bal_subcode_id_tx_rel", "subcode_identifier_line_id", "transaction_id", string="Transactions", readonly=True)

    # Aggregated fields
    total_quantity = fields.Float(string="Total Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_to_store_quantity = fields.Float(string="To Store Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_from_store_quantity = fields.Float(string="From Store Quantity", digits=(16, 2), readonly=True, compute="_compute_totals")
    unit_id = fields.Many2one("kojto.base.units", string="Unit", readonly=True, compute="_compute_unit")
    total_value_eur = fields.Float(string="Total Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_to_store_value_eur = fields.Float(string="To Store Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    total_from_store_value_eur = fields.Float(string="From Store Value", digits=(16, 2), readonly=True, compute="_compute_totals")
    transaction_count = fields.Integer(string="Transaction Count", readonly=True, compute="_compute_totals")

    currency_id = fields.Many2one("res.currency", string="Currency", related="wizard_id.currency_id", readonly=True)

    @api.depends('transaction_ids', 'transaction_ids.batch_id.invoice_content_id.identifier_id')
    def _compute_subcode_identifier_info(self):
        """Compute identifier info from transactions"""
        for record in self:
            if record.identifier_name:
                continue  # Already set by wizard
            identifier_name = False
            identifier_type = False
            # Get info from first transaction that has it
            if record.transaction_ids:
                transactions = record.transaction_ids
                transactions.mapped('batch_id.invoice_content_id.identifier_id')
                for transaction in transactions:
                    if transaction.batch_id and transaction.batch_id.invoice_content_id and transaction.batch_id.invoice_content_id.identifier_id:
                        identifier = transaction.batch_id.invoice_content_id.identifier_id
                        identifier_name = identifier.name
                        identifier_type = identifier.identifier_type
                        break
            record.identifier_name = identifier_name
            record.identifier_type = identifier_type

    @api.depends('transaction_ids', 'transaction_ids.transaction_quantity', 'transaction_ids.transaction_value_pre_vat_eur', 'transaction_ids.to_from_store')
    def _compute_totals(self):
        """Compute aggregated totals for this subcode-identifier combination - optimized single pass"""
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

    @api.depends('identifier_id')
    def _compute_unit(self):
        """Compute unit from identifier"""
        for record in self:
            if record.identifier_id:
                # Find the identifier record by identifier string
                identifier_record = record.env['kojto.finance.accounting.identifiers'].search([
                    ('identifier', '=', record.identifier_id)
                ], limit=1)
                record.unit_id = identifier_record.unit_id if identifier_record else False
            else:
                record.unit_id = False

    def action_view_transactions(self):
        """Open a window showing all transactions for this subcode-identifier combination"""
        self.ensure_one()

        # Read all values immediately to avoid transient record access issues
        # Use read() to get all values in one query before any potential deletion
        values = self.read(['identifier_id', 'subcode_id', 'wizard_id'])[0]

        identifier_id = values.get('identifier_id')
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

        if not identifier_id or not subcode_id:
            raise UserError("No identifier or subcode selected.")

        if not date_from or not date_to:
            raise UserError("Date range is not set.")

        # Get transactions for this subcode-identifier combination in the date range
        domain = [
            ('identifier_id', '=', identifier_id),
            ('subcode_id', '=', subcode_id),
            ('date_issue', '>=', date_from),
            ('date_issue', '<=', date_to),
        ]

        return {
            'name': f'Transactions - {subcode_name} @ {identifier_id} ({date_from} to {date_to})',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {},
            'target': 'current',
        }

    def action_export_subcode_identifier_to_excel(self):
        """Export transactions for this subcode-identifier combination to Excel"""
        self.ensure_one()
        from .utils.kojto_warehouses_balance_wizard_actions import action_export_subcode_identifier_transactions_to_excel
        return action_export_subcode_identifier_transactions_to_excel(self.sudo())

