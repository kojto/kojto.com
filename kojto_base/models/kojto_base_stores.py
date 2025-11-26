from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class KojtoBaseStores(models.Model):
    _name = "kojto.base.stores"
    _description = "Kojto Base Stores"
    _rec_name = "name_short"
    _order = "name asc"

    name = fields.Char(string="Store Name", required=True)
    name_short = fields.Char(string="Store Name Short", required=True)
    datetime_start = fields.Date(string="Date Added", default=fields.Date.context_today)
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Is Active", default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Store name must be unique!'),
        ('name_short_uniq', 'unique(name_short)', 'Store short name must be unique!')
    ]

    @api.constrains('name', 'name_short')
    def _check_names_unique(self):
        for record in self:
            if record.name:
                # Check for case-insensitive duplicate names
                duplicate = self.search([
                    ('id', '!=', record.id),
                    ('name', 'ilike', record.name)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_('Store name "%s" already exists.') % record.name)

            if record.name_short:
                # Check for case-insensitive duplicate short names
                duplicate = self.search([
                    ('id', '!=', record.id),
                    ('name_short', 'ilike', record.name_short)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_('Store short name "%s" already exists.') % record.name_short)
