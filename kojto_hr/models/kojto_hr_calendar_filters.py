from odoo import api, fields, models

class CalendarFilters(models.Model):
    _name = 'kojto.hr.calendar.filters'
    _description = 'Kojto Hr Calendar Filters'

    user_id = fields.Many2one('res.users', 'Me', required=True, default=lambda self: self.env.user, index=True, ondelete='cascade')
    employee_id = fields.Many2one("kojto.hr.employees", string="Employee", required=True)
    active = fields.Boolean('Active', default=True)
    employee_checked = fields.Boolean('Checked', default=True)

    _user_id_employee_id_unique = models.Constraint(
        'UNIQUE(user_id, employee_id)',
        'A user cannot have the same employee filter twice.',
    )


    def write(self, vals):
        """
          Override write method to ensure only one employee filter is checked at a time per user.
          When an employee filter is checked, all other employee filters for the same user are unchecked.
        """
        result = super(CalendarFilters, self).write(vals)

        if vals.get('employee_checked') is True:
            for record in self:
                other_filters = self.env['kojto.hr.calendar.filters'].search([
                    ('user_id', '=', record.user_id.id),
                    ('id', '!=', record.id),
                    ('employee_checked', '=', True)
                ])
                if other_filters:
                    other_filters.write({'employee_checked': False})

        return result

    @api.model
    def get_checked_employee(self):
        filters = self.search([
            ('user_id', '=', self.env.user.id),
            ('employee_checked', '=', True)
        ], order='employee_id')

        return filters[0].employee_id.id if filters else False
