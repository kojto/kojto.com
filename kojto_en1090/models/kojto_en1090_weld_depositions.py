from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo import Command

class KojtoEn1090WeldDepositions(models.Model):
    _name = "kojto.en1090.weld.depositions"
    _description = "Welding Depositions"
    _order = "sequence_in_wps"
    _sql_constraints = [
        ('unique_sequence_per_wps', 'UNIQUE(wps_id, sequence_in_wps)', 'Sequence number must be unique for each WPS!'),
    ]

    name = fields.Char(string="Name", required=True, copy=False)
    active = fields.Boolean(string="Active", default=True, readonly=True)
    wps_id = fields.Many2one("kojto.en1090.wps", string="WPS", required=True, help="The welding procedure specification to be used", ondelete="cascade")
    sequence_in_wps = fields.Integer(string="#", help="The sequence number of the deposition in the WPS")
    welding_process_id = fields.Many2one("kojto.en1090.welding.processes", string="Welding Process", required=True, help="The welding process to be used")
    parameter_content_ids = fields.One2many("kojto.en1090.welding.parameter.contents", "weld_deposition_id", string="Parameters")
    number_of_passes = fields.Integer(string="Passes", default=1)
    deposition_summary = fields.Char(string="Summary", compute="_compute_deposition_summary", store=True)



    @api.constrains('number_of_passes')
    def _check_positive_passes(self):
        for record in self:
            if record.number_of_passes <= 0:
                raise ValidationError(_("Number of passes must be positive."))

    @api.constrains('parameter_content_ids')
    def _check_unique_parameters_in_deposition(self):
        """Ensure that no duplicate parameters exist within a deposition."""
        for record in self:
            if record.parameter_content_ids:
                param_ids = record.parameter_content_ids.mapped('welding_parameter_id').ids
                if len(param_ids) != len(set(param_ids)):
                    # Find the duplicate parameter
                    seen = set()
                    duplicate_param = None
                    for param_id in param_ids:
                        if param_id in seen:
                            duplicate_param = self.env['kojto.en1090.welding.parameters'].browse(param_id)
                            break
                        seen.add(param_id)

                    if duplicate_param:
                        raise ValidationError(_(
                            "Duplicate parameter '%s' found in deposition '%s'. "
                            "Each parameter can only be used once per deposition."
                        ) % (duplicate_param.name, record.name))

    @api.depends('wps_id', 'wps_id.weld_deposition_ids')
    def _compute_sequence_in_wps(self):
        for record in self:
            if not record.wps_id:
                record.sequence_in_wps = 0
                continue

            # Get all depositions for the WPS
            depositions = record.wps_id.weld_deposition_ids

            if not depositions:
                record.sequence_in_wps = 1
                continue

            # Split records into existing and new ones
            existing_records = depositions.filtered(lambda r: isinstance(r.id, int))
            new_records = depositions.filtered(lambda r: not isinstance(r.id, int))

            # For existing records, use their database IDs for sorting
            if record in existing_records:
                sorted_records = list(existing_records.sorted('id'))
                record.sequence_in_wps = sorted_records.index(record) + 1
            # For new records, append them at the end
            elif record in new_records:
                new_records_list = list(new_records)
                record.sequence_in_wps = len(existing_records) + new_records_list.index(record) + 1
            else:
                record.sequence_in_wps = len(depositions) + 1

    @api.depends('welding_process_id', 'sequence_in_wps', 'number_of_passes', 'parameter_content_ids.value')
    def _compute_deposition_summary(self):
        for record in self:
            if not record.welding_process_id or not record.id:
                record.deposition_summary = ""
                continue

            param_summaries = []
            for content in record.parameter_content_ids:
                param = content.welding_parameter_id
                param_summary = f"{param.abbreviation or param.name}"
                if content.value:
                    param_summary += f": {content.value}"
                if param.unit:
                    param_summary += f" {param.unit}"
                param_summaries.append(param_summary)

            summary_parts = [
                str(record.sequence_in_wps),
                f"Passes: {record.number_of_passes}",
                record.welding_process_id.code,
            ]
            summary_parts.extend(param_summaries)
            record.deposition_summary = " | ".join(summary_parts)

    @api.onchange('welding_process_id')
    def _onchange_welding_process_id(self):
        """Update parameter_content_ids in the UI when welding_process_id changes."""
        if self.welding_process_id:
            commands = self._generate_parameter_contents(for_onchange=True)
            if commands:
                self.parameter_content_ids = commands
        else:
            self.parameter_content_ids = [(5, 0, 0)]  # Clear all parameter contents

    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Only generate parameters if not explicitly skipped and not manually set
        if not self.env.context.get('skip_parameter_generation') and 'parameter_content_ids' not in vals:
            record._generate_parameter_contents()
        return record

    def write(self, vals):
        res = super().write(vals)
        # Only generate parameters if not explicitly skipped and welding process changed
        if not self.env.context.get('skip_parameter_generation') and 'welding_process_id' in vals and 'parameter_content_ids' not in vals:
            self._generate_parameter_contents()
        return res

    def _generate_parameter_contents(self, for_onchange=False):
        """Generate or update parameter content records based on the welding process.

        Args:
            for_onchange (bool): If True, return Command operations for UI updates instead of creating records.

        Returns:
            list: List of Command operations if for_onchange is True, else None.
        """
        # Skip generation if context flag is set (for copied depositions)
        if self.env.context.get('skip_parameter_generation'):
            return commands if for_onchange else None

        commands = []
        for record in self:
            if not record.welding_process_id:
                if for_onchange:
                    return [(5, 0, 0)]  # Clear all parameter contents
                record.parameter_content_ids.unlink()
                continue

            # Get all parameters for the current welding process
            new_parameters = self.env['kojto.en1090.welding.parameters'].search([
                ('active', '=', True),
                ('welding_process_ids', 'in', record.welding_process_id.id)
            ])

            # Get existing parameter content records
            existing_contents = record.parameter_content_ids
            existing_param_ids = existing_contents.mapped('welding_parameter_id').ids
            existing_values = {c.welding_parameter_id.id: c.value for c in existing_contents}

            # Identify parameters to add and remove
            new_param_ids = new_parameters.ids
            params_to_remove = existing_contents.filtered(lambda c: c.welding_parameter_id.id not in new_param_ids)
            params_to_add = new_parameters.filtered(lambda p: p.id not in existing_param_ids)

            if for_onchange:
                # Clear existing records
                commands.append((5, 0, 0))
                # Add parameter contents, preserving existing values where possible
                for param in new_parameters:  # Add all parameters to ensure order
                    value = existing_values.get(param.id, str(param.default_parameter_value) if param.default_parameter_value else '')
                    commands.append((0, 0, {
                        'welding_parameter_id': param.id,
                        'value': value,
                    }))
            else:
                # Remove parameter contents that are no longer relevant
                if params_to_remove:
                    params_to_remove.unlink()
                # Create new parameter contents for missing parameters, preserving existing values
                if params_to_add:
                    vals_list = [{
                        'welding_parameter_id': param.id,
                        'weld_deposition_id': record.id,
                        'value': existing_values.get(param.id, str(param.default_parameter_value) if param.default_parameter_value else ''),
                    } for param in params_to_add]
                    self.env['kojto.en1090.welding.parameter.contents'].create(vals_list)

        return commands if for_onchange else None

    def copy_deposition(self):
        """Copy the current deposition and create a new one with the same data, copying only the current parameter contents. Ensure the WPS is saved first."""
        self.ensure_one()

        # Save the WPS if it exists
        if self.wps_id:
            self.wps_id.flush_recordset()

        # Copy the deposition with context to prevent automatic parameter generation and prevent parameter_content_ids creation
        new_deposition = self.with_context(skip_parameter_generation=True).copy({
            'wps_id': self.wps_id.id,
            'name': self.name,  # Keep the original name
            'sequence_in_wps': self.sequence_in_wps,
            'number_of_passes': self.number_of_passes,
            'welding_process_id': self.welding_process_id.id if self.welding_process_id else False,
            'parameter_content_ids': [],  # Prevent auto-generation of all process parameters
        })

        # Manually copy only the current parameter contents with their values
        if self.parameter_content_ids:
            for param_content in self.parameter_content_ids:
                param_content.copy({
                    'weld_deposition_id': new_deposition.id,
                    'welding_parameter_id': param_content.welding_parameter_id.id if param_content.welding_parameter_id else False,
                    'value': param_content.value,
                })

        # Return action to refresh the current view
        return {
            'type': 'ir.actions.act_window',
            'name': 'WPS',
            'res_model': 'kojto.en1090.wps',
            'res_id': self.wps_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_wps_type': self.wps_id.wps_type,
            }
        }
