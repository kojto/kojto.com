from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoBaseUnits(models.Model):
    _name = "kojto.base.units"
    _description = "Kojto Units"
    _rec_name = "name"
    _order = "name desc"

    description = fields.Char(string="Description")
    unit_type = fields.Selection(
        selection=[
            ("time", "Time"),
            ("length", "Length"),
            ("weight", "Weight"),
            ("area", "Area"),
            ("volume", "Volume"),
            ("temperature", "Temperature"),
            ("pressure", "Pressure"),
            ("energy", "Energy"),
            ("power", "Power"),
            ("currency", "Currency"),
            ("quantity", "Quantity"),
            ("speed", "Speed"),
            ("proportion", "Proportion"),
            ("force", "Force"),
            ("density", "Density"),
        ],
        string="Unit Type",
        required=True,
    )
    translation_ids = fields.One2many("kojto.base.units.translation", "unit_id", string="Translations")
    name = fields.Char(string="Unit", required=True)
    conversion_factor = fields.Float(string="Conversion Factor", default=1.0, required=True, help="Conversion factor relative to the base unit of the same type (e.g., 1 for the base unit, 0.001 for milli-).")

    @api.constrains("unit_type", "conversion_factor")
    def _check_unique_base_unit(self):
        for record in self:
            if record.conversion_factor == 1.0:
                existing_base = self.search(
                    [
                        ("unit_type", "=", record.unit_type),
                        ("conversion_factor", "=", 1.0),
                        ("id", "!=", record.id),
                    ]
                )
                if existing_base:
                    raise ValidationError(f"Only one unit of type '{record.unit_type}' can have a conversion factor of 1. Unit '{existing_base.name}' is already set as the base unit.")


class KojtoBaseUnitsTranslation(models.Model):
    _name = "kojto.base.units.translation"
    _description = "Kojto Base Units Translation"
    _rec_name = "name"

    unit_id = fields.Many2one("kojto.base.units", string="Unit", required=True, ondelete="cascade")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    name = fields.Char(string="Name", required=True)

    @api.constrains("unit_id", "language_id")
    def _check_unique_unit_language(self):
        for record in self:
            if self.search_count([
                ("unit_id", "=", record.unit_id.id),
                ("language_id", "=", record.language_id.id),
                ("id", "!=", record.id),
            ]) > 0:
                raise ValidationError(f"Only one translation per language is allowed for each unit! A translation for unit '{record.unit_id.name}' in language '{record.language_id.name}' already exists.")
