from odoo import models, fields, api


class KojtoDeliveryPackages(models.Model):
    _name = "kojto.delivery.packages"
    _description = "Delivery Packages"
    _rec_name = "name"
    _sort = "name desc"

    delivery_id = fields.Many2one("kojto.deliveries", string="Delivery", ondelete="cascade", required=True)
    name = fields.Char(string="Name", default=lambda self: self.generate_default_name())



    can_stack_on_it = fields.Boolean(string="Stack On It", default=False)
    pre_content_text = fields.Text(string="Pre Content Text")

    package_content_ids = fields.One2many("kojto.delivery.package.contents", "delivery_package_id", string="Package Items")
    packaging_material_item_ids = fields.One2many("kojto.delivery.packaging.material.items", "delivery_package_id", string="Packaging Material Items")

    gross_weight = fields.Float(string="Gross (kg)", digits=(20, 2), compute="compute_gross_weight")
    net_weight = fields.Float(string="Net (kg)", digits=(20, 2), compute="compute_net_weight")
    tare_weight = fields.Float(string="Tare (kg)", digits=(20, 2), compute="compute_tare_weight")

    width = fields.Float(string="Width (mm)", digits=(20, 2))
    length = fields.Float(string="Length (mm)", digits=(20, 2))
    height = fields.Float(string="Height (mm)", digits=(20, 2))


    @api.depends("net_weight", "tare_weight")
    def compute_gross_weight(self):
        for record in self:
            record.gross_weight = record.net_weight + record.tare_weight

    @api.depends('package_content_ids.total_weight')
    def compute_net_weight(self):
        for record in self:
            record.net_weight = sum(item.total_weight for item in record.package_content_ids)

    @api.depends('packaging_material_item_ids.total_weight')
    def compute_tare_weight(self):
        for record in self:
            record.tare_weight = sum(item.total_weight for item in record.packaging_material_item_ids)


    @api.model
    def generate_default_name(self):
        latest_package = self.search([], order="name desc", limit=1)
        if latest_package and latest_package.name:
            try:
                last_number = int(latest_package.name.split("-")[-1])
                return f"PKG-{str(last_number + 1).zfill(3)}"
            except (ValueError, IndexError):
                pass
        return "PKG-001"

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            # Handle batch creation
            for val in vals:
                if not val.get("name"):
                    val["name"] = self.generate_default_name()
        else:
            # Handle single record creation
            if not vals.get("name"):
                vals["name"] = self.generate_default_name()

        result = super(KojtoDeliveryPackages, self).create(vals)
        return result

    def open_package_contents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Package Contents",
            "res_model": "kojto.delivery.package.contents",
            "view_id": self.env.ref("kojto_deliveries.view_kojto_delivery_package_contents_list_at").id,
            "view_mode": "list",
            "domain": [("delivery_package_id", "=", self.id)],
            "context": {"default_delivery_package_id": self.id},
            "target": "new",
        }

    def open_packaging_material_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Packaging Material Items",
            "res_model": "kojto.delivery.packaging.material.items",
            "view_id": self.env.ref("kojto_deliveries.view_kojto_delivery_packaging_material_items_list").id,
            "view_mode": "list",
            "domain": [("delivery_package_id", "=", self.id)],
            "context": {"default_delivery_package_id": self.id},
            "target": "new",
        }
