from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoDeliveryPackageContents(models.Model):
    _name = "kojto.delivery.package.contents"
    _description = "Delivery Package Contents"
    _rec_name = "name"
    _order = "position asc"

    name = fields.Char(string="Name")
    position = fields.Char(string="Position", related="delivery_content_id.position")
    delivery_package_id = fields.Many2one("kojto.delivery.packages", string="Package", ondelete="cascade", required=True)
    delivery_id = fields.Many2one(related='delivery_package_id.delivery_id', store=True)

    # Add domain to restrict delivery_content_id to contents of the same delivery_id
    delivery_content_id = fields.Many2one("kojto.delivery.contents", string="Item", ondelete="cascade", required=True, domain="[('delivery_id', '=', delivery_id)]")

    quantity = fields.Float(string="Quantity", digits=(14, 2))
    total_weight = fields.Float(string='Total Weight', compute='_compute_total_weight')
    unit_weight = fields.Float(related="delivery_content_id.unit_weight", string="Unit Weight")

    @api.depends("delivery_content_id", "quantity")
    def _compute_total_weight(self):
        for record in self:
            record.total_weight = record.quantity * record.unit_weight if record.quantity and record.unit_weight else 0.0

    @api.constrains("delivery_content_id", "delivery_id")
    def _check_delivery_content_delivery_id(self):
        for record in self:
            if record.delivery_content_id and record.delivery_id:
                if record.delivery_content_id.delivery_id != record.delivery_id:
                    raise ValidationError(
                        f"The selected item ({record.delivery_content_id.name}) belongs to a different delivery "
                        f"({record.delivery_content_id.delivery_id.name}). It must belong to the same delivery "
                        f"as the package ({record.delivery_id.name})."
                    )

    @api.constrains("delivery_content_id", "quantity")
    def check_quantity_limit(self):
        for record in self:
            if record.delivery_content_id and record.quantity:
                total_packaged = sum(
                    item.quantity
                    for item in self.search(
                        [
                            ("delivery_content_id", "=", record.delivery_content_id.id),
                            ("id", "!=", record.id),
                        ]
                    )
                )
                if total_packaged + record.quantity > record.delivery_content_id.quantity:
                    raise ValidationError(
                        f"Total packaged quantity ({total_packaged + record.quantity}) cannot exceed the delivery content quantity ({record.delivery_content_id.quantity})"
                    )

    def delete_package_content(self):
        """Custom delete method that removes the package content but stays in the list view"""
        self.ensure_one()
        package_id = self.delivery_package_id.id
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Package Contents',
            'res_model': 'kojto.delivery.package.contents',
            'view_mode': 'list',
            'domain': [('delivery_package_id', '=', package_id)],
            'context': {'default_delivery_package_id': package_id},
            'target': 'new',
        }

    def action_fill_with_unallocated_contents(self):
        # Try to get the package id from context (active_id or default_delivery_package_id)
        package_id = self.env.context.get('active_id') or self.env.context.get('default_delivery_package_id')
        if not package_id:
            # fallback: try to get from the first record if any
            first_content = self.search([], limit=1)
            package_id = first_content.delivery_package_id.id if first_content else None
        if not package_id:
            raise ValidationError('No package selected to fill.')
        package = self.env['kojto.delivery.packages'].browse(package_id)
        if not package:
            raise ValidationError('Package not found.')
        DeliveryContent = self.env['kojto.delivery.contents']
        PackageContent = self.env['kojto.delivery.package.contents']
        # Get all delivery contents for this delivery
        delivery_contents = DeliveryContent.search([('delivery_id', '=', package.delivery_id.id)])
        for content in delivery_contents:
            unallocated_qty = content.quantity - content.quantity_package_contents
            if unallocated_qty > 0:
                # Check if already present in this package
                package_content = PackageContent.search([
                    ('delivery_package_id', '=', package.id),
                    ('delivery_content_id', '=', content.id)
                ], limit=1)
                if package_content:
                    package_content.quantity += unallocated_qty
                else:
                    PackageContent.create({
                        'delivery_package_id': package.id,
                        'delivery_content_id': content.id,
                        'quantity': unallocated_qty,
                    })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.delivery.package.contents',
            'view_mode': 'list',
            'domain': [('delivery_package_id', '=', package_id)],
            'target': 'current',
            'context': {
                'notification': {
                    'title': 'Package Filled',
                    'message': 'All unallocated delivery contents have been added to this package.',
                    'type': 'success',
                }
            }
        }



