from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoEn1090Translations(models.Model):
    _name = "kojto.en1090.translations"
    _description = "EN1090 Translations"
    _order = "name"
    _sql_constraints = [
        ('unique_translation_specialist', 'UNIQUE(translated_name, language_id, specialist_id)', 'Translation must be unique per language and specialist!'),
        ('unique_translation_geometry', 'UNIQUE(translated_name, language_id, geometry_id)', 'Translation must be unique per language and geometry!'),
        ('unique_translation_process', 'UNIQUE(translated_name, language_id, process_id)', 'Translation must be unique per language and process!'),
        ('unique_translation_parameter', 'UNIQUE(translated_name, language_id, parameter_id)', 'Translation must be unique per language and parameter!'),
    ]
    _rec_name = 'translated_name'

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    active = fields.Boolean(string="Active", default=True)

    language_id = fields.Many2one("res.lang", string="Language", required=True, default=lambda self: self.env.ref("base.lang_en").id)

    specialist_id = fields.Many2one("kojto.en1090.welding.specialists", string="Specialist")
    geometry_id = fields.Many2one("kojto.en1090.weld.geometries", string="Geometry")
    process_id = fields.Many2one("kojto.en1090.welding.processes", string="Process")
    parameter_id = fields.Many2one("kojto.en1090.welding.parameters", string="Parameter")

    translated_name = fields.Char(string="Translated Name", required=True)

    @api.depends('specialist_id', 'geometry_id', 'process_id', 'parameter_id', 'translated_name')
    def _compute_name(self):
        for record in self:
            if record.translated_name:
                # Determine the model name based on which reference field is set
                if record.specialist_id:
                    record.name = f"Welding Specialist - {record.translated_name}"
                elif record.geometry_id:
                    record.name = f"Weld Geometry - {record.translated_name}"
                elif record.process_id:
                    record.name = f"Welding Process - {record.translated_name}"
                elif record.parameter_id:
                    record.name = f"Welding Parameter - {record.translated_name}"
                else:
                    record.name = f"Translation - {record.translated_name}"
            else:
                record.name = "New Translation"

    @api.constrains('translated_name', 'language_id')
    def _check_unique_translation(self):
        for record in self:
            if record.translated_name and record.language_id:
                # Check uniqueness based on the specific reference field that is set
                domain = [
                    ('translated_name', '=', record.translated_name),
                    ('language_id', '=', record.language_id.id),
                    ('id', '!=', record.id)
                ]

                # Add the appropriate reference field to the domain
                if record.specialist_id:
                    domain.append(('specialist_id', '=', record.specialist_id.id))
                elif record.geometry_id:
                    domain.append(('geometry_id', '=', record.geometry_id.id))
                elif record.process_id:
                    domain.append(('process_id', '=', record.process_id.id))
                elif record.parameter_id:
                    domain.append(('parameter_id', '=', record.parameter_id.id))

                duplicate = self.search(domain)
                if duplicate:
                    raise ValidationError(f"A translation for this name in {record.language_id.name} already exists for this reference!")

    def action_view_reference(self):
        """Action to view the referenced record"""
        self.ensure_one()
        # Determine which reference field is set and return the appropriate action
        if self.specialist_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'View Welding Specialist',
                'res_model': 'kojto.en1090.welding.specialists',
                'res_id': self.specialist_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.geometry_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'View Weld Geometry',
                'res_model': 'kojto.en1090.weld.geometries',
                'res_id': self.geometry_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.process_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'View Welding Process',
                'res_model': 'kojto.en1090.welding.processes',
                'res_id': self.process_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.parameter_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'View Welding Parameter',
                'res_model': 'kojto.en1090.welding.parameters',
                'res_id': self.parameter_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def create(self, vals):
        """Override create to automatically set the appropriate reference field based on context"""
        # The reference fields are now set automatically through the One2many relationship
        # No additional logic needed here
        return super().create(vals)

    def write(self, vals):
        """Override write to handle any necessary updates"""
        # The reference fields are now managed through the One2many relationship
        # No additional logic needed here
        return super().write(vals)
