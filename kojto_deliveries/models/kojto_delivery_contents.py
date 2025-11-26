from odoo import models, fields, api


class KojtoDeliveryContents(models.Model):
    _name = "kojto.delivery.contents"
    _description = "Delivery Contents"
    _order = "position asc, id asc"

    delivery_id = fields.Many2one("kojto.deliveries", string="Delivery", ondelete="cascade", required=True)
    position = fields.Char(string="№", size=5)
    name = fields.Text(string="Description")
    quantity = fields.Float(string="Quantity", digits=(16, 2), required=True)
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    quantity_package_contents = fields.Float(string="In package", digits=(16, 2), compute="_compute_quantity_package_contents")

    unit_weight = fields.Float(string="Unit Weight (kg)", digits=(14, 2))
    net_weight = fields.Float(string="Net Weight (kg)", digits=(20, 2), compute="compute_net_weight")

    content_compositions = fields.One2many("kojto.delivery.consumed.materials", "delivery_content_id", string="Consumed Materials")

    @api.depends("quantity", "unit_weight")
    def compute_net_weight(self):
        for record in self:
            record.net_weight = record.quantity * record.unit_weight if record.quantity and record.unit_weight else 0.0

    @api.depends("delivery_id.packages.package_content_ids.delivery_content_id", "delivery_id.packages.package_content_ids.quantity")
    def _compute_quantity_package_contents(self):
        for record in self:
            total_packaged = sum(
                package_content.quantity
                for package_content in self.env["kojto.delivery.package.contents"].search([
                    ("delivery_content_id", "=", record.id)
                ])
            )
            record.quantity_package_contents = total_packaged

    def open_consumed_materials(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Consumed Materials",
            "res_model": "kojto.delivery.consumed.materials",
            "view_id": self.env.ref("kojto_deliveries.view_kojto_delivery_consumed_materials_list").id,
            "view_mode": "list",
            "domain": [("delivery_content_id", "=", self.id)],
            "context": {
                "default_delivery_content_id": self.id,
                "default_name": f"Consumed materials for {self.name or self.position or 'Content'}",
            },
            "target": "new",
        }
