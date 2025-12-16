from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class KojtoHrLeaveTypes(models.Model):
    _name = "kojto.hr.leave.type"
    _description = "Kojto Hr Leave Types"
    _order = "name"

    name = fields.Char(string="Type", required=True)
    leave_group = fields.Selection(
        string="Leave group",
        selection=[
            ("paid", "Paid"),
            ("unpaid", "Unpaid"),
            ("sick", "Sick")
        ],
        required=True,
        default="paid"
    )
    based_on = fields.Char(string="Based on")
    copy_order = fields.Char(string="Copy of order")
    active = fields.Boolean(string="Active", default=True)
    color = fields.Char(string="Color")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Leave type name must be unique!')
    ]

    @api.model
    def _apply_default_leave_group(self, vals):
        """Ensure leave_group has a valid value before create/write."""
        if not vals.get('leave_group'):
            vals['leave_group'] = 'paid'

    def create(self, vals_list):
        # Handle both single dict and list of dicts
        if isinstance(vals_list, list):
            for vals in vals_list:
                self._apply_default_leave_group(vals)
        else:
            self._apply_default_leave_group(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        # Ensure leave_group field has a valid value when updating
        if 'leave_group' in vals and not vals['leave_group']:
            vals['leave_group'] = 'paid'
        return super().write(vals)

    @api.constrains('name', 'leave_group')
    def _check_required_fields(self):
        for record in self:
            if not record.name:
                raise ValidationError("Leave type name is required.")
            if not record.leave_group:
                raise ValidationError("Leave group is required.")

    @api.model
    def create_default_leave_types(self):
        """Create default leave types if none exist"""
        existing_types = self.search([])
        if not existing_types:
            default_types = [
                {'name': 'Annual Leave', 'leave_group': 'paid'},
                {'name': 'Sick Leave', 'leave_group': 'sick'},
                {'name': 'Unpaid Leave', 'leave_group': 'unpaid'},
                {'name': 'Maternity Leave', 'leave_group': 'paid'},
                {'name': 'Paternity Leave', 'leave_group': 'paid'},
            ]
            for type_data in default_types:
                self.create(type_data)
            _logger.info("Created default leave types")
