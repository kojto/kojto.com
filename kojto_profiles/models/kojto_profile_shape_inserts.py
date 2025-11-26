# kojto_profiles/models/kojto_profile_shape_inserts.py

from odoo import api, fields, models

class KojtoProfileShapeInserts(models.Model):
    _name = "kojto.profile.shape.inserts"
    _description = "Shape Inserts for Kojto Profiles"

    profile_id = fields.Many2one("kojto.profiles", string="Profile", ondelete="cascade")
    shape_id = fields.Many2one("kojto.profile.shapes", string="Shape", required=True)
    x = fields.Float(string="X Coordinate", default=0.0)
    y = fields.Float(string="Y Coordinate", default=0.0)
    rotation = fields.Float(string="Rotation (degrees)", default=0.0, help="Rotation angle in degrees, between -180 and 180")

    def open_shape_window(self):
        """Open form view of the related shape."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.profile.shapes',
            'res_id': self.shape_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('kojto_profiles.view_kojto_profile_shapes_form').id,
            'target': 'current',
        }

