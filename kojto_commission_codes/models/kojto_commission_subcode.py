from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoCommissionSubcodes(models.Model):
    _name = "kojto.commission.subcodes"
    _description = "Kojto Subcodes"
    _rec_name = "name"
    _order = "subcode desc"

    _sql_constraints = [('unique_name', 'unique(name)', 'The combination of Main Code, Code, and Subcode must be unique.')]

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    subcode = fields.Char(string="Subcode", required=True)
    code_id = fields.Many2one("kojto.commission.codes", string="Code", ondelete="cascade", required=True)
    code_description = fields.Char(related="code_id.description", string="Code Description")
    maincode_id = fields.Many2one(related="code_id.maincode_id", string="Main Code", ondelete="cascade", required=True)
    description = fields.Char(string="Description", required=True)
    active = fields.Boolean(string="Is Active", default=True)
    maincode = fields.Char(related="maincode_id.maincode", store=True, string="Main Code")
    code = fields.Char(related="code_id.code", store=True, string="Code")
    cash_flow_only = fields.Boolean(string="Cash Flow Only", related="maincode_id.cash_flow_only")
    show_in_hr_tracking = fields.Boolean(string="Show in HR Tracking", default=False)
    show_in_asset_works = fields.Boolean(string="Show in Asset Works", default=False)

    @api.depends("maincode_id.maincode", "code_id.code", "subcode")
    def _compute_name(self):
        for record in self:
            if record.maincode_id and record.code_id and record.subcode:
                record.name = f"{record.maincode_id.maincode}.{record.code_id.code}.{record.subcode}"
            else:
                record.name = ""

    @api.constrains('maincode_id', 'code_id', 'subcode')
    def _check_unique_name(self):
        for record in self:
            if not (record.maincode_id and record.code_id and record.subcode):
                continue
            name_value = f"{record.maincode_id.maincode}.{record.code_id.code}.{record.subcode}"
            existing = self.search([
                ('name', '=', name_value),
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError("A subcode with this Main Code, Code, and Subcode already exists.")

    display_name = fields.Char(compute="_compute_display_name", store=False)

    @api.depends("name", "description")
    def _compute_display_name(self):
        for record in self:
            show_description = self.env.context.get('show_description', False)
            if show_description and record.description:
                # Use parentheses to visually distinguish description
                record.display_name = f"{record.name} ({record.code_description} - {record.description})"
            else:
                record.display_name = record.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, **kwargs):
        """
        Customize the search for Many2one dropdown to search both name and description.
        """
        args = args or []
        domain = args + ['|', ('name', operator, name), ('description', operator, name)]

        # Add context to indicate this is a name_search call
        records = self.with_context(name_search=True)._search(domain, limit=limit)

        # Use display_name computation for consistent formatting
        result = []
        for record in self.browse(records).with_user(name_get_uid or self.env.user):
            # The display_name will automatically include description due to context
            display_name = record.with_context(name_search=True).display_name
            result.append((record.id, display_name))
        return result
