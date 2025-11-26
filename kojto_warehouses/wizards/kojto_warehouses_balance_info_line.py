# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Info Line Model
"""

from odoo import models, fields, api
from odoo.exceptions import UserError


class KojtoWarehousesBalanceInfoLine(models.TransientModel):
    _name = "kojto.warehouses.balance.info.line"
    _description = "Warehouse Balance Info Line"
    _order = "warehouse_name"

    wizard_id = fields.Many2one("kojto.warehouses.balance.wizard", string="Wizard", ondelete="cascade", required=True)
    warehouse_id = fields.Many2one("kojto.base.stores", string="Warehouse", readonly=True)
    warehouse_name = fields.Char(string="Warehouse Name", readonly=True)
    beginning_value = fields.Float(string="Beginning Value", digits=(16, 2), default=0.0, readonly=True, help="Value of warehouse content at the beginning of the period")
    ending_value = fields.Float(string="Ending Value", digits=(16, 2), default=0.0, readonly=True, help="Value of warehouse content at the end of the period")
    change_value = fields.Float(string="Change", digits=(16, 2), compute="_compute_change_value", readonly=True, help="Change in value (Ending - Beginning)")
    to_store_value = fields.Float(string="To Store Value", digits=(16, 2), default=0.0, readonly=True, help="Total value of transactions TO store during the period")
    from_store_value = fields.Float(string="From Store Value", digits=(16, 2), default=0.0, readonly=True, help="Total value of transactions FROM store during the period")
    currency_id = fields.Many2one("res.currency", string="Currency", related="wizard_id.currency_id", readonly=True)

    @api.depends('beginning_value', 'ending_value')
    def _compute_change_value(self):
        """Compute change value as ending - beginning"""
        for record in self:
            record.change_value = (record.ending_value or 0.0) - (record.beginning_value or 0.0)

    def action_view_transactions(self):
        """Open a window showing all transactions for this warehouse in the date range"""
        self.ensure_one()

        # Read all values immediately to avoid transient record access issues
        # Use read() to get all values in one query before any potential deletion
        values = self.read(['warehouse_id', 'warehouse_name', 'wizard_id'])[0]

        warehouse_id = values.get('warehouse_id') and values['warehouse_id'][0] or False
        warehouse_name = values.get('warehouse_name') or 'Unknown'
        wizard_id = values.get('wizard_id') and values['wizard_id'][0] or False

        # Read wizard values separately
        date_from = False
        date_to = False
        if wizard_id:
            wizard_values = self.env['kojto.warehouses.balance.wizard'].browse(wizard_id).read(['date_from', 'date_to'])
            if wizard_values:
                date_from = wizard_values[0].get('date_from')
                date_to = wizard_values[0].get('date_to')

        if not date_from or not date_to:
            raise UserError("Date range is not set.")

        # Build domain - if warehouse_id is False, show all warehouses
        if warehouse_id:
            # Filter by specific warehouse
            domain = [
                ('batch_id.store_id', '=', warehouse_id),
                ('date_issue', '>=', date_from),
                ('date_issue', '<=', date_to),
            ]
        else:
            # Show all warehouses (All Warehouses line)
            domain = [
                ('date_issue', '>=', date_from),
                ('date_issue', '<=', date_to),
            ]

        return {
            'name': f'Transactions - {warehouse_name} ({date_from} to {date_to})',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'list',
            'domain': domain,
            'context': {
                'search_default_group_by_date': 1,
            },
            'target': 'current',
        }

    def action_export_warehouse_to_excel(self):
        """Export transactions for this warehouse to Excel"""
        self.ensure_one()
        from .utils.kojto_warehouses_balance_wizard_actions import action_export_warehouse_transactions_to_excel
        return action_export_warehouse_transactions_to_excel(self.sudo())

