from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoBaseTaxNumbers(models.Model):
    _name = "kojto.base.tax.numbers"
    _description = "Kojto Tax Numbers"
    _rec_name = "tax_number"
    _order = "tax_number desc"

    description = fields.Char(string="Description")
    active = fields.Boolean(string="Is Active", default=True)
    name = fields.Char("Name", compute="get_name")
    tax_number = fields.Char(string="Tax Number", required=True)

    @api.depends("tax_number", "description", "active")
    def get_name(self):
        for record in self:
            if record.description:
                record.name = f"{record.tax_number}_{record.description}"
            else:
                record.name = f"{record.tax_number}"

    @api.constrains('tax_number')
    def _check_unique_tax_number(self):
        for record in self:
            if record.tax_number:
                domain = [('tax_number', '=', record.tax_number)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError('Tax Number must be unique!')
