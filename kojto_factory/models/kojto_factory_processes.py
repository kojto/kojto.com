from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoFactoryProcesses(models.Model):
    _name = 'kojto.factory.processes'
    _description = 'Kojto Factory Processes'
    _rec_name = 'name'

    name = fields.Char(string='Process Name', required=True)
    short_name = fields.Char(string="Short Name", required=True)
    description = fields.Text(string='Description')
    material_id_is_required = fields.Boolean(string='Material Req.', default=False)
    asset_id_is_required = fields.Boolean(string='Asset Req.', default=False)
    thickness_is_required = fields.Boolean(string='Thickness Req.', default=False)
    process_unit_id = fields.Many2one('kojto.base.units', string='Unit', default=lambda self: self.env['kojto.base.units'].search([('name', '=', 'unit')], limit=1).id or False)

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if self.search([('name', '=', record.name), ('id', '!=', record.id)]):
                raise ValidationError("The process name must be unique.")
