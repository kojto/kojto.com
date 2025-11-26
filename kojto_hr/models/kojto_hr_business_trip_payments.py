from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KojtoHrBusinessTripPayments(models.Model):
    _name = "kojto.hr.business.trip.payments"
    _description = "Kojto HR Business Trip Payments to Employee"
    _rec_name = "description"
    _order = "payment_date desc"

    trip_id = fields.Many2one("kojto.hr.business.trips", string="Business Trip", required=True, ondelete="cascade")
    payment_datetime = fields.Datetime(string="Payment Date/Time", required=True, default=fields.Datetime.now)
    payment_date = fields.Date(string="Payment Date", compute="_compute_payment_date", store=True)
    description = fields.Char(string="Description", required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True)
    amount = fields.Float(string="Amount", digits=(16, 2), required=True)
    create_date = fields.Datetime(string="Created on", default=fields.Datetime.now)
    write_date = fields.Datetime(string="Updated on", default=fields.Datetime.now)

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ensure trip_id is set from context if not provided
            if not vals.get('trip_id'):
                if self.env.context.get('default_trip_id'):
                    vals['trip_id'] = self.env.context.get('default_trip_id')
                elif self.env.context.get('active_id') and self.env.context.get('active_model') == 'kojto.hr.business.trips':
                    vals['trip_id'] = self.env.context.get('active_id')

            # Set default currency from business trip if available
            if not vals.get('currency_id') and vals.get('trip_id'):
                business_trip = self.env['kojto.hr.business.trips'].browse(vals['trip_id'])
                if business_trip.currency_id:
                    vals['currency_id'] = business_trip.currency_id.id
                else:
                    vals['currency_id'] = self.env.company.currency_id.id
            elif not vals.get('currency_id'):
                vals['currency_id'] = self.env.company.currency_id.id

        return super(KojtoHrBusinessTripPayments, self).create(vals_list)

    @api.depends('payment_datetime')
    def _compute_payment_date(self):
        for record in self:
            record.payment_date = record.payment_datetime.date()
