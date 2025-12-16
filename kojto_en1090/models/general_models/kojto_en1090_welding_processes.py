from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError

class KojtoEn1090WeldingProcesses(models.Model):


    #according to ISO 4063:2023
    _name = "kojto.en1090.welding.processes"
    _description = "Welding Processes"
    _order = "code"

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)

    translation_ids = fields.One2many("kojto.en1090.translations", "process_id", string="Translations")

    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description")

    welding_parameter_ids = fields.Many2many('kojto.en1090.welding.parameters', 'kojto_en1090_weld_param_process_rel', 'kojto_en1090_welding_processes_id', 'kojto_en1090_welding_parameters_id', string="Welding Parameters")

    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_("Welding process code must be unique!"))
