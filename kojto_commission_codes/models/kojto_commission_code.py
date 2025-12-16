from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoCommissionCodes(models.Model):
    _name = "kojto.commission.codes"
    _description = "Kojto Codes"
    _rec_name = "name"
    _order = "name desc"
    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Code must be unique!'),]

    name = fields.Char(string="Name", compute="compute_name", store=True)
    active = fields.Boolean(string="Is Active", default=True)
    code = fields.Char(string="Code", required=True)
    code_type = fields.Char(string="Type")
    description = fields.Char(string="Description", required=True)
    maincode_id = fields.Many2one("kojto.commission.main.codes", string="Main Code", required=True)


    @api.depends("maincode_id.maincode", "code")
    def compute_name(self):
        for record in self:
            if record.maincode_id and record.code:
                record.name = f"{record.maincode_id.maincode}.{record.code}"
            else:
                record.name = False

    @api.constrains('code')
    def _check_code_uniqueness(self):
        for record in self:
            if record.code:
                duplicate = self.search([
                    ('code', '=', record.code),
                    ('id', '!=', record.id)
                ])
                if duplicate:
                    raise ValidationError(f"Code '{record.code}' already exists in another record.")




