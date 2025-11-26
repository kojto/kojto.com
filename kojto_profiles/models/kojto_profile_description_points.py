from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoProfileDescriptionPoints(models.Model):
    _name = "kojto.profile.description.points"
    _description = "Kojto Profile Description Points"

    profile_id = fields.Many2one("kojto.profiles", string="Profile", required=True, ondelete="cascade")
    x = fields.Float(string="X Coordinate", required=True, default=0)
    y = fields.Float(string="Y Coordinate", required=True, default=0)

    profile_strip_id = fields.Many2one("kojto.profile.strips", string="Profile Strip", ondelete="cascade", domain="[('profile_id', '=', profile_id)]")

    description = fields.Char(string="Description", default="P_01")
    color = fields.Selection([
        ('red', 'Red'),
        ('green', 'Green'),
        ('blue', 'Blue'),
        ('yellow', 'Yellow'),
        ('magenta', 'Magenta'),
        ('cyan', 'Cyan'),
        ('black', 'Black'),
        ('orange', 'Orange'),
        ('purple', 'Purple'),
        ('brown', 'Brown'),
        ('gray', 'Gray'),
        ('white', 'White')
    ], string='Color', default='black')


    representation_shape = fields.Selection([("circle", "Circle"), ("triangle", "Triangle"), ("square", "Square")], default="circle")
    representation_shape_size = fields.Float(string="Size", default=5)

    description_offset_x = fields.Float(string="dX", default=0)
    description_offset_y = fields.Float(string="dY", default=0)
    description_size = fields.Float(string="Font Size", default=5)

    @api.onchange('x', 'y', 'description', 'color', 'representation_shape_size', 'description_offset_x', 'description_offset_y', 'description_size')
    def _onchange_any_field(self):
        """Trigger profile drawing update when any field changes."""
        if self.profile_id:
            self.profile_id._compute_drawing()

    @api.constrains('profile_strip_id', 'profile_id')
    def _check_strip_belongs_to_profile(self):
        """Ensure that the selected strip belongs to the same profile."""
        for record in self:
            if record.profile_strip_id and record.profile_id and record.profile_strip_id.profile_id != record.profile_id:
                raise ValidationError("The selected strip must belong to the same profile.")

    def get_color_hex(self):
        """Return the hex color value for the selected color."""
        color_map = {
            'red': '#FF0000',
            'green': '#00FF00',
            'blue': '#0000FF',
            'yellow': '#FFFF00',
            'magenta': '#FF00FF',
            'cyan': '#00FFFF',
            'black': '#000000',
            'orange': '#FFA500',
            'purple': '#800080',
            'brown': '#A52A2A',
            'gray': '#808080',
            'white': '#FFFFFF'
        }
        return color_map.get(self.color, '#000000')
