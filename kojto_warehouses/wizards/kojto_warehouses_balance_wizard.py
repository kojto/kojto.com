# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Wizard

Purpose:
--------
Wizard that allows users to select warehouses, date range and calculate warehouse balance
showing beginning value, ending value, and list of transactions with values.
All values are displayed in EUR.
"""

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
from .utils.kojto_warehouses_balance_wizard_calculations import calculate_warehouse_balance


class KojtoWarehousesBalanceWizard(models.TransientModel):
    _name = "kojto.warehouses.balance.wizard"
    _description = "Kojto Warehouses Balance Wizard"

    # Date range fields
    date_from = fields.Date(string="From Date", required=True, default=lambda self: self._default_date_from())
    date_to = fields.Date(string="To Date", required=True, default=lambda self: self._default_date_to())

    # Results fields
    warehouse_balance_line_ids = fields.One2many("kojto.warehouses.balance.info.line", "wizard_id", string="Warehouse Balance Lines")
    transaction_line_ids = fields.One2many("kojto.warehouses.balance.transaction.line", "wizard_id", string="Transaction Lines")
    identifier_line_ids = fields.One2many("kojto.warehouses.balance.identifier.line", "wizard_id", string="Identifier Lines", compute="_compute_identifier_line_ids", store=True)
    subcode_line_ids = fields.One2many("kojto.warehouses.balance.subcode.line", "wizard_id", string="Subcode Lines", compute="_compute_subcode_line_ids", store=True)
    subcode_identifier_line_ids = fields.One2many("kojto.warehouses.balance.subcode.identifier.line", "wizard_id", string="Subcode Identifier Lines", compute="_compute_subcode_identifier_line_ids", store=True)
    transaction_ids = fields.Many2many(
        "kojto.warehouses.transactions",
        "wh_bal_tx_rel",
        "wizard_id",
        "transaction_id",
        string="Transactions",
        compute="_compute_transaction_ids",
        store=True
    )

    # Summary fields
    beginning_value = fields.Float(string="Beginning Value (EUR)", digits=(16, 2), compute="_compute_summary_values", readonly=True)
    ending_value = fields.Float(string="Ending Value (EUR)", digits=(16, 2), compute="_compute_summary_values", readonly=True)
    total_transactions_value = fields.Float(string="Total Transactions Value (EUR)", digits=(16, 2), compute="_compute_summary_values", readonly=True)

    # Currency field for monetary widget (always EUR)
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id", readonly=True)

    @api.depends()
    def _compute_currency_id(self):
        """Always use EUR currency"""
        eur_currency = self.env.ref('base.EUR')
        for record in self:
            record.currency_id = eur_currency.id if eur_currency else False

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
            # Force computation of transaction_ids first
            wizard._compute_transaction_ids()
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
            # Force computation of transaction_ids first
            self._compute_transaction_ids()
            self._create_balance_lines()

    def _create_balance_lines(self):
        """Create balance lines from calculated data"""
        self.ensure_one()

        # Ensure transaction_ids are computed before calculating balance
        self._compute_transaction_ids()

        # Always calculate for all warehouses (empty list means all)
        calculated_data = calculate_warehouse_balance(
            self.env,
            self.date_from,
            self.date_to,
            warehouse_ids=None,  # None means all warehouses
            wizard_id=self.id
        )

        # Create consolidated line (totals for all warehouses)
        total_beginning = sum(line.get('beginning_value', 0.0) for line in calculated_data['warehouse_balance_lines'])
        total_ending = sum(line.get('ending_value', 0.0) for line in calculated_data['warehouse_balance_lines'])
        total_to_store = sum(line.get('to_store_value', 0.0) for line in calculated_data['warehouse_balance_lines'])
        total_from_store = sum(line.get('from_store_value', 0.0) for line in calculated_data['warehouse_balance_lines'])

        consolidated_line = [(
            0, 0, {
                'wizard_id': self.id,
                'warehouse_id': False,
                'warehouse_name': 'All Warehouses',
                'beginning_value': total_beginning,
                'ending_value': total_ending,
                'to_store_value': total_to_store,
                'from_store_value': total_from_store,
            }
        )]

        # Convert individual warehouse data dictionaries to Odoo command tuples and add wizard_id
        warehouse_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['warehouse_balance_lines']
        ]
        transaction_lines = [
            (0, 0, dict(line_data, wizard_id=self.id))
            for line_data in calculated_data['transaction_lines']
        ]

        # Update wizard with results (consolidated line first, then individual warehouses)
        self.write({
            'warehouse_balance_line_ids': [(5, 0, 0)] + consolidated_line + warehouse_lines,
            'transaction_line_ids': [(5, 0, 0)] + transaction_lines,
        })

    @api.depends("date_from", "date_to")
    def _compute_transaction_ids(self):
        """Compute transactions linked to this balance based on date range"""
        for record in self:
            if record.date_from and record.date_to:
                # Find all transactions in the date range
                transactions = self.env['kojto.warehouses.transactions'].search([
                    ('date_issue', '>=', record.date_from),
                    ('date_issue', '<=', record.date_to),
                    ('transaction_value_pre_vat_eur', '!=', False),
                ])
                # Force write to ensure relation table is populated
                record.write({'transaction_ids': [(6, 0, transactions.ids)]})
            else:
                record.transaction_ids = False

    @api.depends("transaction_ids", "transaction_ids.identifier_id")
    def _compute_identifier_line_ids(self):
        """Compute identifier lines grouped by identifier_id"""
        for record in self:
            if not record.transaction_ids:
                # Clear existing lines
                record.identifier_line_ids = [(5, 0, 0)]
                continue

            # Use SQL to efficiently group and fetch identifier info in one query
            cr = record.env.cr
            tx_ids = record.transaction_ids.ids
            if not tx_ids:
                record.identifier_line_ids = [(5, 0, 0)]
                continue

            # First, group all transactions by identifier_id (using read for efficiency)
            transactions_data = record.transaction_ids.read(['identifier_id'])
            identifier_groups = {}
            for tx_data in transactions_data:
                identifier_id = tx_data.get('identifier_id') or 'No Identifier'
                if identifier_id not in identifier_groups:
                    identifier_groups[identifier_id] = []
                identifier_groups[identifier_id].append(tx_data['id'])

            # SQL query to get identifier info for all unique identifier_ids in one go
            # Use COALESCE to handle NULL identifier_id
            unique_identifier_ids = [iid for iid in identifier_groups.keys() if iid != 'No Identifier']
            identifier_info_map = {}

            if unique_identifier_ids:
                query = """
                    SELECT DISTINCT ON (COALESCE(t.identifier_id, ''))
                        COALESCE(t.identifier_id, '') as identifier_id,
                        ai.name as identifier_name,
                        ai.identifier_type
                    FROM kojto_warehouses_transactions t
                    INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
                    INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
                    LEFT JOIN kojto_finance_invoice_contents ic ON b.invoice_content_id = ic.id
                    LEFT JOIN kojto_finance_accounting_identifiers ai ON ic.identifier_id = ai.id
                    WHERE t.identifier_id IN %s
                    ORDER BY COALESCE(t.identifier_id, ''), t.id
                """
                cr.execute(query, (tuple(unique_identifier_ids),))
                results = cr.dictfetchall()

                # Build identifier info map from SQL results
                for row in results:
                    identifier_id = row.get('identifier_id') or 'No Identifier'
                    if identifier_id not in identifier_info_map:
                        identifier_info_map[identifier_id] = (
                            row.get('identifier_name'),
                            row.get('identifier_type')
                        )

            # Delete existing lines and create new ones
            identifier_lines = [(5, 0, 0)]  # Clear existing
            for identifier_id, transaction_ids in identifier_groups.items():
                identifier_name, identifier_type = identifier_info_map.get(identifier_id, (False, False))
                identifier_lines.append((0, 0, {
                    'wizard_id': record.id,
                    'identifier_id': identifier_id,
                    'identifier_name': identifier_name,
                    'identifier_type': identifier_type,
                    'transaction_ids': [(6, 0, transaction_ids)],
                }))

            record.identifier_line_ids = identifier_lines

    @api.depends("transaction_ids", "transaction_ids.subcode_id")
    def _compute_subcode_line_ids(self):
        """Compute subcode lines grouped by subcode_id"""
        for record in self:
            if not record.transaction_ids:
                record.subcode_line_ids = [(5, 0, 0)]
                continue

            # Group transactions by subcode_id
            transactions_data = record.transaction_ids.read(['subcode_id'])
            subcode_groups = {}
            for tx_data in transactions_data:
                subcode_id_raw = tx_data.get('subcode_id')
                # Many2one fields return tuple (id, name) from read(), extract just the ID
                if isinstance(subcode_id_raw, tuple):
                    subcode_id = subcode_id_raw[0] if subcode_id_raw[0] else 'No Subcode'
                elif subcode_id_raw:
                    subcode_id = subcode_id_raw
                else:
                    subcode_id = 'No Subcode'
                if subcode_id not in subcode_groups:
                    subcode_groups[subcode_id] = []
                subcode_groups[subcode_id].append(tx_data['id'])

            # Create subcode lines
            subcode_lines = [(5, 0, 0)]
            for subcode_id, transaction_ids in subcode_groups.items():
                if subcode_id == 'No Subcode':
                    subcode_record_id = False
                else:
                    subcode_record_id = subcode_id

                subcode_lines.append((0, 0, {
                    'wizard_id': record.id,
                    'subcode_id': subcode_record_id,
                    'transaction_ids': [(6, 0, transaction_ids)],
                }))

            record.subcode_line_ids = subcode_lines

    @api.depends("transaction_ids", "transaction_ids.identifier_id", "transaction_ids.subcode_id")
    def _compute_subcode_identifier_line_ids(self):
        """Compute subcode-identifier lines grouped by subcode_id and identifier_id combination"""
        for record in self:
            if not record.transaction_ids:
                record.subcode_identifier_line_ids = [(5, 0, 0)]
                continue

            # Group transactions by subcode_id and identifier_id combination
            transactions_data = record.transaction_ids.read(['identifier_id', 'subcode_id'])
            subcode_identifier_groups = {}
            for tx_data in transactions_data:
                identifier_id = tx_data.get('identifier_id') or 'No Identifier'
                subcode_id_raw = tx_data.get('subcode_id')
                # Many2one fields return tuple (id, name) from read(), extract just the ID
                if isinstance(subcode_id_raw, tuple):
                    subcode_id = subcode_id_raw[0] if subcode_id_raw[0] else 'No Subcode'
                elif subcode_id_raw:
                    subcode_id = subcode_id_raw
                else:
                    subcode_id = 'No Subcode'
                key = (subcode_id, identifier_id)
                if key not in subcode_identifier_groups:
                    subcode_identifier_groups[key] = []
                subcode_identifier_groups[key].append(tx_data['id'])

            # SQL query to get identifier and subcode info
            unique_identifier_ids = list(set([key[1] for key in subcode_identifier_groups.keys() if key[1] != 'No Identifier']))
            unique_subcode_ids = list(set([key[0] for key in subcode_identifier_groups.keys() if key[0] != 'No Subcode' and isinstance(key[0], int)]))
            identifier_info_map = {}
            subcode_info_map = {}

            if unique_identifier_ids:
                query = """
                    SELECT DISTINCT ON (COALESCE(t.identifier_id, ''))
                        COALESCE(t.identifier_id, '') as identifier_id,
                        ai.name as identifier_name,
                        ai.identifier_type
                    FROM kojto_warehouses_transactions t
                    INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
                    INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
                    LEFT JOIN kojto_finance_invoice_contents ic ON b.invoice_content_id = ic.id
                    LEFT JOIN kojto_finance_accounting_identifiers ai ON ic.identifier_id = ai.id
                    WHERE t.identifier_id IN %s
                    ORDER BY COALESCE(t.identifier_id, ''), t.id
                """
                cr = record.env.cr
                cr.execute(query, (tuple(unique_identifier_ids),))
                results = cr.dictfetchall()
                for row in results:
                    identifier_id = row.get('identifier_id') or 'No Identifier'
                    if identifier_id not in identifier_info_map:
                        identifier_info_map[identifier_id] = (
                            row.get('identifier_name'),
                            row.get('identifier_type')
                        )

            # Create subcode-identifier lines
            subcode_identifier_lines = [(5, 0, 0)]
            for (subcode_id, identifier_id), transaction_ids in subcode_identifier_groups.items():
                identifier_name, identifier_type = identifier_info_map.get(identifier_id, (False, False))
                if subcode_id == 'No Subcode':
                    subcode_record_id = False
                else:
                    subcode_record_id = subcode_id

                subcode_identifier_lines.append((0, 0, {
                    'wizard_id': record.id,
                    'identifier_id': identifier_id if identifier_id != 'No Identifier' else False,
                    'identifier_name': identifier_name,
                    'identifier_type': identifier_type,
                    'subcode_id': subcode_record_id,
                    'transaction_ids': [(6, 0, transaction_ids)],
                }))

            record.subcode_identifier_line_ids = subcode_identifier_lines

    @api.depends("warehouse_balance_line_ids", "transaction_line_ids")
    def _compute_summary_values(self):
        """Compute summary values"""
        for record in self:
            record.beginning_value = sum(
                record.warehouse_balance_line_ids.mapped("beginning_value")
            )
            record.ending_value = sum(
                record.warehouse_balance_line_ids.mapped("ending_value")
            )
            record.total_transactions_value = sum(
                record.transaction_line_ids.mapped("transaction_value_eur")
            )

    def action_export_balance_to_excel(self):
        """Export all balance data to Excel"""
        from .utils.kojto_warehouses_balance_wizard_actions import action_export_balance_to_excel
        return action_export_balance_to_excel(self)

    def action_save_balance(self):
        """Save/recompute the current balance calculation"""
        self.ensure_one()

        if not self.date_from or not self.date_to:
            raise UserError("No data to save. Please set date range and compute the balance first.")

        # Only recalculate if lines don't exist yet (same pattern as finance balance wizard)
        # This prevents deleting records that might be accessed by buttons
        if not self.warehouse_balance_line_ids:
            # Force computation of transaction_ids first
            self._compute_transaction_ids()
            self._create_balance_lines()
        else:
            # Lines already exist, just show notification
            pass

        # Return a client action that does nothing (keeps window open)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Balance Saved',
                'message': f'Balance for period {self.date_from} to {self.date_to} has been saved.',
                'type': 'success',
                'sticky': False,
            }
        }

