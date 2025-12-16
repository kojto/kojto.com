from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class KojtoEn1090WeldingParameterContents(models.Model):
    _name = "kojto.en1090.welding.parameter.contents"
    _description = "Welding Parameter Contents"
    _order = "welding_parameter_id, id"

    _sql_constraints = [('weld_deposition_parameter_uniq', 'unique(weld_deposition_id, welding_parameter_id)', 'Parameter must be unique per Weld Deposition!')]

    active = fields.Boolean(string="Active", default=True, readonly=True)
    value = fields.Char(string="Value", store=True, help="Formatted display value based on parameter type")
    weld_deposition_id = fields.Many2one("kojto.en1090.weld.depositions", string="Weld Deposition", required=True, ondelete="cascade")
    welding_parameter_id = fields.Many2one('kojto.en1090.welding.parameters', string="Welding Parameter", required=True)
    parameter_unit = fields.Char(related="welding_parameter_id.unit", string="Unit")
    parameter_abbreviation = fields.Char(related="welding_parameter_id.abbreviation", string="Abbr.")
    parameter_is_required = fields.Boolean(related="welding_parameter_id.is_required", string="Req.")

    @api.constrains('weld_deposition_id', 'welding_parameter_id')
    def _check_unique_parameter_per_deposition(self):
        """Ensure that each parameter can exist only once per deposition."""
        for record in self:
            if record.weld_deposition_id and record.welding_parameter_id:
                # Check if there's another record with the same deposition and parameter
                duplicate = self.search([
                    ('weld_deposition_id', '=', record.weld_deposition_id.id),
                    ('welding_parameter_id', '=', record.welding_parameter_id.id),
                    ('id', '!=', record.id)
                ], limit=1)

                if duplicate:
                    raise ValidationError(_(
                        "Parameter '%s' already exists in this deposition. "
                        "Each parameter can only be used once per deposition."
                    ) % record.welding_parameter_id.name)
