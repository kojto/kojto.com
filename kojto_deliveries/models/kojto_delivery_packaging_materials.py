from odoo import models, fields


class KojtoDeliveryPackagingMaterials(models.Model):
    _name = "kojto.delivery.packaging.materials"
    _description = "Delivery Packaging Materials"
    _rec_name = "name"
    _sort = "name desc"

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Is Active", default=False)

    weight = fields.Float(string="Weight (kg)", digits=(14, 2), required=True)
    unit_id = fields.Many2one("kojto.base.units", string="Dimensions Unit", required=True)

    width = fields.Integer(string="Dimension X", required=True)
    depth = fields.Integer(string="Dimension Y", required=True)
    height = fields.Integer(string="Dimension Z", required=True)

    description = fields.Text(string="Description")
    include_in_cmr = fields.Boolean(string="Include In CMR", default=False)
