from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoHrBusinessTripLogbook(models.Model):
    _name = 'kojto.hr.business.trip.logbook'
    _description = 'Business Trip Logbook Entry'
    _order = 'date, id'

    trip_id = fields.Many2one('kojto.hr.business.trips', string='Business Trip', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True)
    is_working_day = fields.Selection([('working', 'working day'), ('not_working', 'Not working day')], string='Day Type', required=True, default='working')
    day_of_week = fields.Char(string='Day', compute='_compute_day_of_week')
    route_description = fields.Char(string='Route Description', required=True, help='Describe the journey from start point to end point (e.g., "Sofia to Plovdiv" or "Office to Client Site")')
    from_km = fields.Float(string="From (km)", digits=(10, 2))
    to_km = fields.Float(string="To (km)", digits=(10, 2))
    distance_km = fields.Float(string="Distance (km)", compute="_compute_distance_km", store=True, digits=(10, 2))
    personal_km = fields.Float(string="Personal (km)", digits=(10, 2), default=0.0)
    comment = fields.Text(string="Comment")

    @api.constrains('from_km', 'to_km')
    def _check_km_values(self):
        for record in self:
            if record.from_km is not None and record.from_km < 0:
                raise ValidationError("From (km) must be positive.")
            if record.from_km is not None and record.to_km is not None and record.to_km <= record.from_km:
                raise ValidationError("To (km) must be larger than From (km).")

    @api.depends('from_km', 'to_km')
    def _compute_distance_km(self):
        for record in self:
            if record.from_km and record.to_km:
                record.distance_km = record.to_km - record.from_km
            else:
                record.distance_km = 0.0

    @api.depends('date')
    def _compute_day_of_week(self):
        for rec in self:
            if rec.date:
                rec.day_of_week = fields.Date.from_string(rec.date).strftime('%A')
            else:
                rec.day_of_week = ''

    def copy_logbook_entry(self):
        """Copy a single logbook entry"""
        self.ensure_one()

        # Create a new logbook entry with the same data
        new_entry_vals = {
            'trip_id': self.trip_id.id,
            'date': self.date,
            'is_working_day': self.is_working_day,
            'route_description': self.route_description,
            'from_km': self.from_km,
            'to_km': self.to_km,
            'personal_km': self.personal_km,
            'comment': self.comment,
        }

        new_entry = self.create(new_entry_vals)

        # Return action to refresh the view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trips',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
