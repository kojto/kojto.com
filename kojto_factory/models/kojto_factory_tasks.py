from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..utils.compute_task_dxf_drawing import compute_task_dxf_drawing


class KojtoFactoryTasks(models.Model):
    _name = 'kojto.factory.tasks'
    _description = 'Kojto Factory Tasks'
    _order = 'name asc'

    name = fields.Char(string='Task Name', required=True, compute='_compute_task_name', store=True)
    package_id = fields.Many2one('kojto.factory.packages', string='Package', required=True, ondelete='cascade')
    subcode_id = fields.Many2one('kojto.commission.subcodes', string='Subcode', related='package_id.subcode_id')
    process_id = fields.Many2one('kojto.factory.processes', string='Process', required=True)
    part_name = fields.Char(string='Part Name', required=True)
    description = fields.Text(string='Description')
    attachments = fields.Many2many('ir.attachment', string='Attachments')
    dxf_drawing = fields.Binary(string='DXF Drawing', compute='_compute_task_dxf_drawing', store=False)
    pdf_drawing = fields.Binary(string='PDF Drawing', compute='_compute_task_pdf_drawing', store=False)
    planned_work_hours = fields.Float(string='Planned HRS')
    actual_work_hours = fields.Float(string='Actual HRS')
    active = fields.Boolean(string='Active', default=True)
    required_task_quantity = fields.Float(string='Required Qty')
    produced_task_quantity = fields.Float(string='Produced Qty', compute='_compute_produced_task_quantity', store=True, digits='Product Unit of Measure')
    open_task_quantity = fields.Float(string='Open Qty', compute='_compute_open_task_quantity', store=True)
    task_unit_id = fields.Many2one('kojto.base.units', string='Unit', related='process_id.process_unit_id')
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By', default=lambda self: self.env.user.employee, readonly=True)
    date_issue = fields.Date(string='Issue Date', default=fields.Date.today)

    task_length = fields.Float(string='Task Length (m)')
    task_weight = fields.Float(string='Task Weight (kg)')
    task_area = fields.Float(string='Task Area (m²)')
    task_volume = fields.Float(string='Task Volume (m³)')

    progress_percent = fields.Float(string='Progress', compute='_compute_progress_percent', store=True)
    job_content_ids = fields.One2many('kojto.factory.job.contents', 'task_id', string='Jobs')
    material_id = fields.Many2one('kojto.base.material.grades', string='Material', default=18)
    asset_id = fields.Many2one('kojto.assets', string='Asset', default=1)
    thickness = fields.Float(string='Thickness', default=1)
    consolidation_field = fields.Char(string='Consolidation Field', compute='_compute_consolidation_field', store=True)
    task_priority = fields.Selection(selection=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], string='Task Priority', default='medium')
    material_id_is_required = fields.Boolean(string='Material Req.', related='process_id.material_id_is_required')
    asset_id_is_required = fields.Boolean(string='Asset Req.', related='process_id.asset_id_is_required')
    thickness_is_required = fields.Boolean(string='Thickness Req.', related='process_id.thickness_is_required')

    @api.depends('job_content_ids.produced_quantity')
    def _compute_produced_task_quantity(self):
        for task in self:
            valid_jobs = task.job_content_ids.filtered(lambda j: j.produced_quantity is not False)
            task.produced_task_quantity = sum(valid_jobs.mapped('produced_quantity') or [0.0])

    @api.depends('required_task_quantity', 'produced_task_quantity')
    def _compute_open_task_quantity(self):
        for task in self:
            task.open_task_quantity = max(0.0, task.required_task_quantity - task.produced_task_quantity)

    @api.constrains('process_id', 'job_content_ids')
    def _check_immutability(self):
        for task in self:
            if task.job_content_ids and task.process_id != task._origin.process_id:
                raise ValidationError(
                    _("Cannot change the process of a task that is linked to a job. "
                      "Please unlink the task from all jobs first.")
                )

    @api.constrains('process_id', 'material_id', 'asset_id', 'thickness')
    def _check_process_requirements(self):
        for task in self:
            if not task.process_id:
                continue
            if task.material_id_is_required and not task.material_id:
                raise ValidationError(_("Material is required for process '%s'.") % task.process_id.name)
            if task.asset_id_is_required and not task.asset_id:
                raise ValidationError(_("Asset is required for process '%s'.") % task.process_id.name)
            if task.thickness_is_required and not task.thickness:
                raise ValidationError(_("Thickness is required for process '%s'.") % task.process_id.name)

    @api.depends('package_id', 'package_id.name')
    def _compute_task_name(self):
        for task in self:
            if not task.package_id or not task.package_id.name:
                task.name = 'New Task'
                continue
            domain = [('package_id', '=', task.package_id.id), ('id', '!=', task.id)]
            count = self.search_count(domain)
            while True:
                count += 1
                name = f"{task.package_id.name}.{str(count).zfill(2)}"
                if not self.search([('name', '=', name), ('id', '!=', task.id)]):
                    task.name = name
                    break

    def set_task_name_directly(self, package_name, index):
        """Set task name directly without using the compute method.
        Used when recalculating names after contract changes to avoid duplicates."""
        task_name = f"{package_name}.{str(index).zfill(2)}"
        self.name = task_name

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if self.search([('name', '=', record.name), ('id', '!=', record.id)]):
                raise ValidationError(_("Task name must be unique."))

    @api.depends('required_task_quantity', 'produced_task_quantity')
    def _compute_progress_percent(self):
        for task in self:
            if task.required_task_quantity > 0:
                task.progress_percent = (task.produced_task_quantity / task.required_task_quantity)
                task.active = task.progress_percent <= 1
            else:
                task.progress_percent = 0
                task.active = True

    @api.depends('process_id', 'process_id.short_name', 'material_id', 'material_id.name',
                 'asset_id', 'asset_id.name', 'thickness')
    def _compute_consolidation_field(self):
        for task in self:
            process_name = task.process_id.short_name if task.process_id else ''
            concat_fields = []
            if task.process_id:
                if task.material_id_is_required and task.material_id:
                    concat_fields.append(f"MAT_{task.material_id.name}")
                if task.asset_id_is_required and task.asset_id:
                    concat_fields.append(f"MACH_{task.asset_id.name}")
                if task.thickness_is_required and task.thickness:
                    concat_fields.append(f"THK_{task.thickness}")
            task.consolidation_field = f"{process_name}_" + '_'.join(concat_fields) if concat_fields else process_name

    @api.depends('attachments')
    def _compute_task_dxf_drawing(self):
        for task in self:
            task.dxf_drawing = False
            dxf_attachment = next((att for att in task.attachments if att.name.lower().endswith('.dxf')), None)
            if dxf_attachment:
                try:
                    svg_data = compute_task_dxf_drawing(dxf_attachment)
                    task.dxf_drawing = svg_data or False
                except Exception:
                    task.dxf_drawing = False

    @api.depends('attachments')
    def _compute_task_pdf_drawing(self):
        for task in self:
            pdf_attachment = task.attachments.filtered(lambda att: att.mimetype == 'application/pdf')[:1]
            task.pdf_drawing = pdf_attachment.datas if pdf_attachment else False

    def action_open_jobs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task Jobs',
            'res_model': 'kojto.factory.jobs',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.job_content_ids.job_id.ids)],
            'target': 'current',
        }

    def open_task_window(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Modify Task',
            'res_model': 'kojto.factory.tasks',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attachments',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attachments.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
            'target': 'current',
        }

    def action_open_task_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.factory.tasks',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def copy_task_row(self):
        """Copy the current task row, without duplicating job_content_ids."""
        self.ensure_one()
        new_task = self.copy({
            'job_content_ids': False,  # Do not duplicate job_content_ids
            'produced_task_quantity': 0.0,  # Reset computed field
            'open_task_quantity': self.required_task_quantity,  # Reset to required quantity
            'attachments': False,  # Don't copy attachments
        })
        return True  # Stay in list view
