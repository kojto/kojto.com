# kojto_finance/models/kojto_finance_accounting_identifiers.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class KojtoFinanceAccountingIdentifiers(models.Model):
    _name = "kojto.finance.accounting.identifiers"
    _description = "Kojto Finance Accounting Identifiers"
    _order = "display_name desc"
    _rec_name = "display_name"

    name = fields.Char(string="Identifier Description")
    identifier = fields.Char(string="Identifier", required=True)
    identifier_type = fields.Selection(selection=[("material", "Material"), ("goods", "Goods"), ("asset", "Asset")], string="Identifier Type", required=True, default="material")
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    active = fields.Boolean(string="Is Active", default=True)
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)

    @api.constrains("identifier")
    def _check_unique_identifier(self):
        for record in self:
            if self.search_count([("identifier", "=", record.identifier), ("id", "!=", record.id)]):
                raise ValidationError("Identifier must be unique!")

    @api.depends("identifier", "name", "unit_id")
    def _compute_display_name(self):
        for record in self:
            unit = f"({record.unit_id.name})" if record.unit_id else ""
            extra = f"{record.identifier_type[0].upper()}{unit}"
            record.display_name = f"{record.identifier}/{record.name} {extra}" if record.name else f"{record.identifier} {extra}"
        return {}
