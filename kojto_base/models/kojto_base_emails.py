from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re

class KojtoBaseEmails(models.Model):
    _name = "kojto.base.emails"
    _description = "Kojto Emails"
    _rec_name = "name"
    _order = "name desc"

    active = fields.Boolean(string="Is Active", default=True)
    name = fields.Char(string="Email")

    @api.constrains("name")
    def check_email(self):
        name_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        for record in self:
            if record.name and not name_pattern.match(record.name):
                raise ValidationError(f'The email "{record.name}" is invalid.')
