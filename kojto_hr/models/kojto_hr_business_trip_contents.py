from odoo import models, fields, api, _
import logging
import traceback
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class KojtoHrBusinessTripContents(models.Model):
    _name = "kojto.hr.business.trip.contents"
    _description = "Kojto HR Business Trip Contents"
    _rec_name = "name"

    name = fields.Char(string="Description", translate=True)
    trip_id = fields.Many2one("kojto.hr.business.trips", string="Business trip", required=True, ondelete="cascade")
    quantity = fields.Float(string="Quantity", digits=(16, 2), default=1.0)
    unit_id = fields.Many2one("kojto.base.units", string="Unit", default=35)
    unit_price = fields.Float(string="Unit Price", digits=(16, 2), default=0.0)
    total_sum = fields.Float(string="Total Sum", compute="compute_total_sum", digits=(16, 2))
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    trip_group = fields.Selection(string="Group", selection=[("transport", "Transport"), ("housing", "Housing"), ("daily", "Daily"), ("other", "Other")],)
    is_actual_expense = fields.Boolean(string="Actual Expense", default=lambda self: self._default_is_actual_expense())
    payable_to_employee = fields.Boolean(string="Payable to Employee", default=False)
    create_date = fields.Datetime(string="Created on", default=fields.Datetime.now)
    write_date = fields.Datetime(string="Updated on", default=fields.Datetime.now)

    @api.model
    def _default_is_actual_expense(self):
        """Get default value for is_actual_expense from context"""
        return self.env.context.get('default_is_actual_expense', False)

    @api.model
    def default_get(self, fields_list):
        """Override to set is_actual_expense from context"""
        res = super(KojtoHrBusinessTripContents, self).default_get(fields_list)
        if 'is_actual_expense' in fields_list:
            res['is_actual_expense'] = self.env.context.get('default_is_actual_expense', False)
        return res

    @api.depends('quantity', 'unit_price')
    def compute_total_sum(self):
        for record in self:
            record.total_sum = record.quantity * record.unit_price

    @api.onchange('quantity', 'unit_price')
    def _onchange_quantity_unit_price(self):
        """Update total_sum when quantity or unit_price changes"""
        for record in self:
            record.total_sum = record.quantity * record.unit_price

    @api.onchange('total_sum', 'quantity')
    def _onchange_total_sum_quantity(self):
        """Update unit_price when total_sum or quantity changes"""
        for record in self:
            if record.quantity and record.quantity != 0:
                record.unit_price = record.total_sum / record.quantity

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ensure trip_id is set from context if not provided
            if not vals.get('trip_id'):
                if self.env.context.get('default_trip_id'):
                    vals['trip_id'] = self.env.context.get('default_trip_id')
                elif self.env.context.get('active_id') and self.env.context.get('active_model') == 'kojto.hr.business.trips':
                    vals['trip_id'] = self.env.context.get('active_id')

            # Ensure is_actual_expense is set from context if not explicitly provided
            if 'is_actual_expense' not in vals and 'default_is_actual_expense' in self.env.context:
                vals['is_actual_expense'] = self.env.context.get('default_is_actual_expense')

            # Set default values from parent business trip if trip_id is available
            if vals.get('trip_id'):
                business_trip = self.env['kojto.hr.business.trips'].browse(vals['trip_id'])
                if not vals.get('currency_id'):
                    # Get company currency from business trip or default
                    company_currency = self.env.company.currency_id
                    vals['currency_id'] = company_currency.id
            else:
                # If no trip_id, still set default currency
                if not vals.get('currency_id'):
                    company_currency = self.env.company.currency_id
                    vals['currency_id'] = company_currency.id

        try:
            result = super(KojtoHrBusinessTripContents, self).create(vals_list)
            return result
        except Exception as e:
            raise

    def write(self, vals):
        try:
            result = super(KojtoHrBusinessTripContents, self).write(vals)
            return result
        except Exception as e:
            raise

    def copy_business_trip_contents(self):
        """Copy individual expense item within the same business trip"""
        self.ensure_one()

        # Create a copy of the current expense item
        expense_vals = {
            'trip_id': self.trip_id.id,
            'name': self.name,
            'quantity': self.quantity,
            'unit_id': self.unit_id.id if self.unit_id else False,
            'unit_price': self.unit_price,
            'currency_id': self.currency_id.id if self.currency_id else False,
            'trip_group': self.trip_group,
            'is_actual_expense': self.is_actual_expense,
        }

        # Create the new expense item
        new_expense = self.create(expense_vals)

        # Return action to refresh the view and show the new expense
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.hr.business.trips',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'target': 'current',
            'flags': {'reload': True},
        }

    @api.constrains('total_sum')
    def _check_total_sum(self):
        for record in self:
            if record.total_sum < 0:
                raise ValidationError(_("Total sum cannot be negative."))

    def get_unit_name_for_printing(self):
        """Get unit name based on the business trip's language"""
        self.ensure_one()
        if self.unit_id and self.trip_id and self.trip_id.language_id:
            # First try to find a translation in the trip's language
            unit_translation = self.env['kojto.base.units.translation'].search([
                ('unit_id', '=', self.unit_id.id),
                ('language_id', '=', self.trip_id.language_id.id),
            ], limit=1)

            if unit_translation:
                return unit_translation.name
            else:
                # Fallback to the unit's default name
                return self.unit_id.name
        elif self.unit_id:
            # If no language specified, use default name
            return self.unit_id.name
        else:
            return ""
