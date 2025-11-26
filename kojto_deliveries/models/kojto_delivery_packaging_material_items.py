from odoo import models, fields, api


class KojtoDeliveryPackagingMaterialItems(models.Model):
    _name = "kojto.delivery.packaging.material.items"
    _description = "Delivery Packaging Material Items"
    _rec_name = "name"
    _sort = "name desc"

    name = fields.Char(related="packaging_material_id.name", string="Name")
    delivery_package_id = fields.Many2one("kojto.delivery.packages", string="Delivery Package", ondelete="cascade", required=True)
    packaging_material_id = fields.Many2one("kojto.delivery.packaging.materials", string="Delivery Packaging Material", ondelete="cascade", required=True)

    position = fields.Char(string="Position")
    quantity = fields.Float(string="Quantity", digits=(14, 2), required=True)
    total_weight = fields.Float(string="Total Weight", digits=(20, 2), compute="compute_total_weight")

    unit_weight = fields.Float(related="packaging_material_id.weight", string="Unit Weight", digits=(14, 2))

    @api.depends("unit_weight", "quantity")
    def compute_total_weight(self):
        for record in self:
            record.total_weight = record.unit_weight * record.quantity if record.unit_weight and record.quantity else 0.0

    def delete_packaging_material_item(self):
        """Custom delete method that removes the packaging material item but stays in the list view"""
        self.ensure_one()
        package_id = self.delivery_package_id.id
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Packaging Material Items',
            'res_model': 'kojto.delivery.packaging.material.items',
            'view_mode': 'list',
            'domain': [('delivery_package_id', '=', package_id)],
            'context': {'default_delivery_package_id': package_id},
            'target': 'new',
        }
