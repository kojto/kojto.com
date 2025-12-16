from odoo import models, fields, api

class KojtoEn1090WeldingParameters(models.Model):
    _name = "kojto.en1090.welding.parameters"
    _description = "Welding Parameters"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)

    abbreviation = fields.Char(string="Abbreviation")
    description = fields.Text(string="Description")

    translation_ids = fields.One2many("kojto.en1090.translations", "parameter_id", string="Translations")

    is_required = fields.Boolean(string="Required", default=False, help="If checked, this parameter must be filled in when used in WPS or WPQR")
    welding_process_ids = fields.Many2many('kojto.en1090.welding.processes', string="Welding Processes", relation='kojto_en1090_weld_param_process_rel')
    unit = fields.Char(string="Unit")
    default_parameter_value = fields.Char(string="Default Value")

    @api.constrains('abbreviation')
    def _check_abbreviation_unique(self):
        for record in self:
            if record.abbreviation:
                duplicate = self.env['kojto.en1090.welding.parameters'].search([
                    ('abbreviation', '=', record.abbreviation),
                    ('id', '!=', record.id)
                ])
                if duplicate:
                    raise models.ValidationError(f"Abbreviation '{record.abbreviation}' must be unique!")
