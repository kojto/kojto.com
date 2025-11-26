from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoCommissionMainCodes(models.Model):
    _name = "kojto.commission.main.codes"
    _description = "Kojto Main Codes"
    _rec_name = "maincode"
    _order = "maincode desc"
    _sql_constraints = [('maincode_unique', 'UNIQUE(maincode)', 'Maincode must be unique!'),]

    name = fields.Char(string="Name")
    maincode = fields.Char(string="Maincode", required=True)
    description = fields.Char(string="Description", required=True)
    active = fields.Boolean(string="Is Active", default=True)
    cash_flow_only = fields.Boolean(string="Cash flow")

    @api.constrains('maincode')
    def _check_maincode_uniqueness(self):
        for record in self:
            if record.maincode:
                # Check for duplicates in all records, regardless of active
                duplicate = self.search([
                    ('maincode', '=', record.maincode),
                    ('id', '!=', record.id)
                ])
                if duplicate:
                    raise ValidationError(f"Maincode '{record.maincode}' already exists in another record.")
