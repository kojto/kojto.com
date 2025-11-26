# kojto_finance/models/kojto_finance_accounting_types.py
from odoo import models, fields, api


class KojtoFinanceAccountingTypes(models.Model):  # продажба или покупка на услуга, стока, ДМА, финансова услуга, Материал, продукция, отпасък
    _name = "kojto.finance.accounting.types"
    _description = "Kojto Finance Accounting Types"
    _order = "name desc"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)  # продажба или покупка на услуга, стока, ДМА ...
    accounting_warehouse = fields.Char()
    accounting_warehouse_name = fields.Char(string="Accounting Warehouse Name")

    primary_type = fields.Selection(
        selection=[
            ("purchase", "Purchase"),
            ("sale", "Sale"),
            ("cashflow_in", "Incoming Cashflow"),
            ("cashflow_out", "Outgoing Cashflow"),
        ],
        string="Transaction Type",
        required=True,
        default="purchase",
    )

    secondary_type = fields.Selection(
        selection=[
            ("service", "Service"),
            ("material", "Material"),
            ("goods", "Goods"),
            ("products", "Products"),
            ("advance", "Advance Payment"),
            ("asset", "Asset"),
            ("waste", "Waste"),
            ("future", "Future Period"),
            ("financial_service", "Financial Service"),
            ("cashflow", "Cashflow"),
        ],
        string="Template Type",
        required=True,
        default="service",
    )
