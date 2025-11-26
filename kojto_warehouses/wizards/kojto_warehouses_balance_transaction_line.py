# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Transaction Line Model
"""

from odoo import models, fields


class KojtoWarehousesBalanceTransactionLine(models.TransientModel):
    _name = "kojto.warehouses.balance.transaction.line"
    _description = "Warehouse Balance Transaction Line"
    _order = "date_issue desc, warehouse_name"

    wizard_id = fields.Many2one("kojto.warehouses.balance.wizard", string="Wizard", ondelete="cascade", required=True)
    transaction_id = fields.Many2one("kojto.warehouses.transactions", string="Transaction", readonly=True)
    transaction_name = fields.Char(string="Transaction Name", readonly=True)
    date_issue = fields.Date(string="Date", readonly=True)
    warehouse_id = fields.Many2one("kojto.base.stores", string="Warehouse", readonly=True)
    warehouse_name = fields.Char(string="Warehouse", readonly=True)
    item_name = fields.Char(string="Item", readonly=True)
    batch_name = fields.Char(string="Batch", readonly=True)
    transaction_type = fields.Selection([('to_store', 'To Store'), ('from_store', 'From Store')], string="Type", readonly=True)
    quantity = fields.Float(string="Quantity", digits=(16, 2), readonly=True)
    unit_price_eur = fields.Float(string="Unit Price (EUR)", digits=(16, 2), readonly=True)
    transaction_value_eur = fields.Float(string="Transaction Value (EUR)", digits=(16, 2), default=0.0, readonly=True, help="Value of this transaction in EUR")
    currency_id = fields.Many2one("res.currency", string="Currency", related="wizard_id.currency_id", readonly=True)
