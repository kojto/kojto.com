from odoo import models, fields, api, _

class KojtoOfferConsolidationIds(models.Model):
    _name = "kojto.offer.consolidation.ids"
    _description = "Kojto Consolidation IDs"
    _rec_name = "name"
    _order = "name desc"

    # General Information
    name = fields.Char(string="Consolidation Name")
    surcharges = fields.Many2many("kojto.offer.surcharges", string="Surcharges")
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    contribution_margin_percent = fields.Float(string="Contribution Margin (%)", required=True)

    # Add a field to store the total surcharge
    surcharges_percent = fields.Float(string="Total surcharges(%)", compute="compute_surcharges_total")

    @api.depends("surcharges.surcharge")
    def compute_surcharges_total(self):
        for record in self:
            record.surcharges_percent = sum(surcharge.surcharge for surcharge in record.surcharges)
        return {}

    def copy_consolidation_id(self):
        """Copy the consolidation ID record"""
        self.ensure_one()

        # Create a copy of the current record
        new_consolidation = self.copy({
            'name': f"{self.name} (Copy)",
            'surcharges': [(6, 0, self.surcharges.ids)],  # Copy the many2many relationship
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.consolidation.ids",
            "res_id": new_consolidation.id,
            "view_mode": "form",
            "target": "current",
        }
