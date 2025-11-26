# kojto_finance/models/kojto_finance_accounting_subtypes.py
from odoo import models, fields, api


class KojtoFinanceAccountingSubtypes(models.Model):
    _name = "kojto.finance.accounting.subtypes"
    _description = "Kojto Finance Accounting Subtypes"
    _order = "display_name desc"
    _rec_name = "display_name"

    name = fields.Char(string="Name")
    subtype_number = fields.Integer(string="Subtype Number", required=True, default=0)
    template_type_ids = fields.Many2many("kojto.finance.accounting.types", string="Used for following Accounting Types", relation="kojto_finance_accounting_subtypes_2_types_rel")

    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)

    @api.depends("subtype_number", "name")
    def _compute_display_name(self):
        for record in self:
            try:
                # Attempt to compute the display name
                subtype_number = record.subtype_number if isinstance(record.subtype_number, int) else 0
                name = record.name if record.name else "No Name"
                record.display_name = f"{subtype_number} - {name}"
            except Exception:
                # Fallback to "No Display Name" if anything goes wrong
                record.display_name = "No Display Name"
        return {}

    @api.onchange("subtype_number")
    def _onchange_fields(self):
        self._compute_display_name()


    def compute_display_name(self):
        #DELETE after migration
        try:
            subtype_number = self.subtype_number if isinstance(self.subtype_number, int) else 0
            name = self.name if self.name else "No Name"
            return f"{subtype_number} - {name}"
        except Exception:
            return "No Display Name"
