"""
Kojto Factory Job Contents Model

Purpose:
--------
Defines the model for job contents, which represent the relationship between
factory jobs and tasks. This model tracks the quantity produced for each task
within a job.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class KojtoFactoryJobContents(models.Model):
    _name = 'kojto.factory.job.contents'
    _description = 'Kojto Factory Job-Task Relation'

    job_id = fields.Many2one('kojto.factory.jobs', string='Job', required=True, ondelete='cascade')
    task_id = fields.Many2one('kojto.factory.tasks', string='Task', required=True, ondelete='cascade')
    produced_quantity = fields.Float(string='Quantity Produced', required=True, default=0.0, digits='Product Unit of Measure')
    open_task_quantity = fields.Float(related='task_id.open_task_quantity', string='Open Task Quantity', store=True, digits='Product Unit of Measure')

    @api.constrains('produced_quantity')
    def _check_produced_quantity(self):
        for record in self:
            if record.produced_quantity < 0:
                raise ValidationError(_("Produced Quantity cannot be negative."))

    @api.onchange('produced_quantity', 'task_id')
    def _onchange_produced_quantity(self):
        if self.task_id:
            self.task_id._compute_produced_task_quantity()
            self.task_id._compute_open_task_quantity()
            return {'value': {'open_task_quantity': self.task_id.open_task_quantity}}

    def copy_job_content_row(self):
        """Copy the current job content row, preserving job_id and task_id, resetting produced_quantity."""
        self.ensure_one()
        new_row = self.copy({
            'job_id': self.job_id.id,
            'task_id': self.task_id.id,
            'produced_quantity': 0.0,  # Reset to 0.0
        })
        if self.task_id:
            self.task_id._compute_produced_task_quantity()
            self.task_id._compute_open_task_quantity()
        return True  # Stay in list view
