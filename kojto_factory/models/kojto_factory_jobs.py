"""
Kojto Factory Jobs Model

Purpose:
--------
Defines the model for factory jobs, which represent production jobs in the factory.
Each job is associated with a process and can have multiple tasks through job contents.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class KojtoFactoryJobs(models.Model):
    _name = 'kojto.factory.jobs'
    _description = 'Kojto Factory Jobs'
    _rec_name = 'name'

    name = fields.Char(string='Job Name', required=True, compute='_compute_job_name', store=True)
    process_id = fields.Many2one('kojto.factory.processes', string='Process', required=True)
    job_content_ids = fields.One2many('kojto.factory.job.contents', 'job_id', string='Tasks')
    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date')
    description = fields.Text(string='Description', help='Description of the job and its tasks')
    active = fields.Boolean(string='Active', default=True)
    total_job_quantity = fields.Float(string='Total Quantity', compute='_compute_total_job_quantity', store=True)
    attachments = fields.Many2many('ir.attachment', string='Attachments')
    material_id = fields.Many2one('kojto.base.material.grades', string='Material')
    asset_id = fields.Many2one('kojto.assets', string='Asset')
    thickness = fields.Float(string='Thickness')
    job_weight = fields.Float(string='Job Weight (kg)')
    job_length = fields.Float(string='Job Length (m)')
    job_area = fields.Float(string='Job Area (m²)')
    job_volume = fields.Float(string='Job Volume (m³)')
    consolidation_field = fields.Char(string='Consolidation Field', compute='_compute_consolidation_field', store=True)
    store_id = fields.Many2one('kojto.base.stores', string='Store', required=True)
    date_issue = fields.Date(string='Issue Date', default=fields.Date.today)
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By', default=lambda self: self.env.user.employee, readonly=True)

    transaction_ids = fields.One2many('kojto.warehouses.transactions', 'job_id', string='Transactions')

    # Related fields inherited from process_id
    material_id_is_required = fields.Boolean(related='process_id.material_id_is_required')
    asset_id_is_required = fields.Boolean(related='process_id.asset_id_is_required')
    thickness_is_required = fields.Boolean(related='process_id.thickness_is_required')

    @api.depends('process_id', 'process_id.name')
    def _compute_job_name(self):
        for job in self:
            job.name = 'New Job'
            if not job.process_id or not job.process_id.name:
                continue
            domain = [('process_id', '=', job.process_id.id), ('id', '!=', job.id)]
            count = self.search_count(domain)
            while True:
                count += 1
                name = f"{job.process_id.short_name}.{str(count).zfill(5)}"
                if not self.search([('name', '=', name), ('id', '!=', job.id)]):
                    job.name = name
                    break

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if self.search([('name', '=', record.name), ('id', '!=', record.id)]):
                raise ValidationError("Job name must be unique.")

    @api.depends('job_content_ids')
    def _compute_total_job_quantity(self):
        for job in self:
            job.total_job_quantity = sum(job.job_content_ids.mapped('produced_quantity'))

    @api.constrains('process_id', 'material_id', 'asset_id', 'thickness')
    def _check_process_requirements(self):
        for job in self:
            if not job.process_id:
                continue
            if job.material_id_is_required and not job.material_id:
                raise ValidationError(f"Material is required for process '{job.process_id.name}'.")
            if job.asset_id_is_required and not job.asset_id:
                raise ValidationError(f"Asset is required for process '{job.process_id.name}'.")
            if job.thickness_is_required and not job.thickness:
                raise ValidationError(f"Thickness is required for process '{job.process_id.name}'.")

    @api.depends('process_id', 'process_id.name', 'material_id', 'material_id.name', 'asset_id', 'asset_id.name', 'thickness')
    def _compute_consolidation_field(self):
        for job in self:
            process_name = job.process_id.short_name if job.process_id else ''
            concat_fields = []
            if job.process_id:
                if job.material_id_is_required and job.material_id:
                    concat_fields.append(f"MAT_{job.material_id.name}")
                if job.asset_id_is_required and job.asset_id:
                    concat_fields.append(f"MACH_{job.asset_id.name}")
                if job.thickness_is_required and job.thickness:
                    concat_fields.append(f"THK_{job.thickness}")
            if concat_fields:
                job.consolidation_field = f"{process_name}_" + '_'.join(concat_fields)
            elif process_name:
                job.consolidation_field = process_name
            else:
                job.consolidation_field = ''

    def action_open_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Tasks',
            'res_model': 'kojto.factory.tasks',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.job_content_ids.task_id.ids)],
            'target': 'current',
        }

    def copy_job_row(self):
        """Copy the current job row, duplicating job_content_ids."""
        self.ensure_one()
        # Copy job_content_ids by preparing a command list
        job_content_commands = [(0, 0, {
            'task_id': content.task_id.id,
            'produced_quantity': 0.0,  # Reset produced_quantity
        }) for content in self.job_content_ids]
        new_job = self.copy({
            'job_content_ids': job_content_commands,  # Duplicate job_content_ids
            'name': f"{self.name} (Copy)",  # Temporary name
            'attachments': False,  # Don't copy attachments
        })
        # Recompute task quantities for affected tasks
        task_ids = new_job.job_content_ids.mapped('task_id')
        if task_ids:
            task_ids._compute_produced_task_quantity()
            task_ids._compute_open_task_quantity()
        return True  # Stay in list view
