from odoo import models, fields, api, _

class KojtoOfferContentElements(models.Model):
    _name = "kojto.offer.content.elements"
    _description = "Kojto Offer Content Elements"
    _rec_name = "name"
    _order = "position asc"

    name = fields.Char(string="Description")
    position = fields.Char(string="№", help="Alphanumeric! Don't change!", size=5)
    consolidation_id = fields.Many2one("kojto.offer.consolidation.ids", string="Consolidation ID", required=True)
    content_id = fields.Many2one("kojto.offer.contents", string="Content", ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="", related="content_id.currency_id", readonly=True)

    unit_price = fields.Float(string="Unit Price")
    quantity = fields.Float(string="Quantity")
    unit_id = fields.Many2one("kojto.base.units", string="Unit", related="consolidation_id.unit_id", readonly=True)

    base_price = fields.Float(string="Base Price", compute="compute_base_price_and_surcharge", readonly=True, digits=(16, 2))
    c_margin_from_consolidation_id = fields.Float(string="CM base(%)", related="consolidation_id.contribution_margin_percent", readonly=True, help="C-Margin from Consolidation ID")

    surcharge = fields.Float(string="Surch.", compute="compute_base_price_and_surcharge", readonly=True, digits=(16, 2), help="Surcharge amount")
    surcharges_percent = fields.Float(string="Surch. (%)", related="consolidation_id.surcharges_percent", readonly=True, help="Sum of all surcharge percentages applied to the base price")

    contribution_margin_percent = fields.Float(string="CM (%)", compute="compute_contribution_margin_percent", readonly=True, help="Total C-Margin")
    contribution_margin = fields.Float(string="C-Margin", compute="compute_contribution_margin", readonly=True, digits=(16, 2), help="C-Margin amount")

    total_price = fields.Float(string="Total Price", compute="compute_total_price", readonly=True, digits=(16, 2), help="Total price")

    @api.depends("unit_price", "quantity", "consolidation_id")
    def compute_base_price_and_surcharge(self):
        for record in self:
            record.base_price = record.unit_price * record.quantity
            record.surcharge = record.base_price * (record.surcharges_percent / 100.0)
        return {}

    @api.depends("base_price", "surcharges_percent", "consolidation_id")
    def compute_contribution_margin(self):
        for record in self:
            record.contribution_margin = record.base_price * (record.c_margin_from_consolidation_id / 100.0) + record.surcharge
        return {}

    @api.depends("contribution_margin", "total_price")
    def compute_contribution_margin_percent(self):
        for record in self:
            record.contribution_margin_percent = record.contribution_margin / record.total_price * 100 if record.total_price else 0.0
        return {}

    @api.depends("base_price", "surcharge")
    def compute_total_price(self):
        for record in self:
            record.total_price = record.base_price + record.surcharge
        return {}



    @api.onchange("consolidation_id")
    def _onchange_consolidation_id(self):
        if self.consolidation_id:
            self.unit_id = self.consolidation_id.unit_id
            self.name = self.consolidation_id.name
        return {}

    def open_o2m_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.consolidation.ids",
            "view_mode": "form",
            "res_id": self.consolidation_id.id,
            "target": "current",
        }

    def unlink(self):
        # Call the parent unlink method to actually delete the records
        result = super().unlink()

        # Return an action to refresh the current view without closing the window
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.content.elements",
            "view_mode": "list,form",
            "domain": [("content_id", "=", self.env.context.get('default_content_id', False))],
            "context": {"default_content_id": self.env.context.get('default_content_id', False)},
            "target": "new",
            "name": "Content Elements",
        }

    def copy_content_element(self):
        self.ensure_one()
        # Create a copy of the current record
        copied_record = self.copy({
            'content_id': self.content_id.id,
        })

        # Return an action to open the copied record in form view
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.content.elements",
            "view_mode": "form",
            "res_id": copied_record.id,
            "target": "new",
            "name": "Copy Content Element",
        }
