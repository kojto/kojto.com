#$ kojto_profiles/models/kojto_profile_batches.py

from odoo import models, fields, api
from odoo import _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import base64
from ..utils.export_profile_batch_to_excel import export_profile_batch_to_excel

class KojtoProfileBatches(models.Model):
    _name = "kojto.profile.batches"
    _description = "Kojto Profile Batches"
    _rec_name = "name"
    _inherit = ["kojto.library.printable"]
    _order = "name"

    name = fields.Char(string="Name", compute="generate_batch_name", store=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    active = fields.Boolean(string="Is Active", default=True)

    subcode_description = fields.Char(related="subcode_id.description", string="Subcode Description")

    batch_content_ids = fields.One2many("kojto.profile.batch.content", "batch_id", string="Batch Positions", help="Collection of profiles with their lengths and quantities in this batch")
    description = fields.Text(string="Description")
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today)
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By', default=lambda self: self.env.user.employee)
    excel_file = fields.Binary(string="Excel File", attachment=True)
    excel_filename = fields.Char(string="Excel Filename")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")
    total_batch_external_edges = fields.Float(string="External Edges (m)", compute="_compute_total_batch_external_edges", store=False, digits=(9, 2))
    total_batch_coating_area = fields.Float(string="Coating Area (m²)", compute="_compute_total_batch_coating_area", store=False, digits=(9, 2))
    total_batch_weight_gross = fields.Float(string="Gross Weight (t)", compute="_compute_total_batch_weights", store=False, digits=(9, 2))
    total_batch_weight_net = fields.Float(string="Net Weight (t)", compute="_compute_total_batch_weights", store=False, digits=(9, 2))
    total_batch_process_time = fields.Float(string="Total Process Time (hrs)", compute="_compute_total_batch_process_time", store=False, digits=(9, 2))
    total_batch_pcs = fields.Float(string="Total Profile Pcs", compute="_compute_total_batch_pcs", store=False, digits=(9, 2))
    company_id = fields.Many2one("kojto.contacts", string="Company", compute="compute_company_id")

    def compute_company_id(self):
        for record in self:
            contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
            record.company_id = contact.id if contact else False

    @api.depends("batch_content_ids.total_profile_length_net", "batch_content_ids.number_ext_corners")
    def _compute_total_batch_external_edges(self):
        for record in self:
            record.total_batch_external_edges = sum(content.total_profile_length_net * content.number_ext_corners for content in record.batch_content_ids)

    @api.depends("batch_content_ids.total_profile_length_net", "batch_content_ids.total_profile_coating_area")
    def _compute_total_batch_coating_area(self):
        for record in self:
            record.total_batch_coating_area = sum(content.total_profile_coating_area for content in record.batch_content_ids)

    @api.depends("batch_content_ids.total_profile_weight_gross", "batch_content_ids.total_profile_weight_net")
    def _compute_total_batch_weights(self):
        for record in self:
            total_gross = sum(content.total_profile_weight_gross for content in record.batch_content_ids)
            total_net = sum(content.total_profile_weight_net for content in record.batch_content_ids)
            record.total_batch_weight_gross = total_gross / 1000
            record.total_batch_weight_net = total_net / 1000

    @api.depends("batch_content_ids.quantity")
    def _compute_total_batch_pcs(self):
        for record in self:
            record.total_batch_pcs = sum(content.quantity for content in record.batch_content_ids) or 0.0

    @api.depends("batch_content_ids.total_profile_process_time")
    def _compute_total_batch_process_time(self):
        for record in self:
            total_process_time_minutes = sum(content.total_profile_process_time for content in record.batch_content_ids)
            record.total_batch_process_time = total_process_time_minutes / 60.0

    def copy_and_open(self):
        self.ensure_one()
        employee = self.env.user.employee
        fallback_employee = self.issued_by
        if not employee and not fallback_employee:
            raise UserError(_("No employee found for the current user or the source batch. Please contact your administrator."))
        new_batch = self.copy({'issued_by': employee.id if employee else fallback_employee.id})
        # Copy all batch content rows to the new batch
        for content in self.batch_content_ids:
            content_vals = {
                'batch_id': new_batch.id,
                'position': content.position,
                'description': content.description,
                'profile_id': content.profile_id.id,
                'length': content.length,
                'length_extension': content.length_extension,
                'quantity': content.quantity,
            }
            self.env['kojto.profile.batch.content'].create(content_vals)
        return {"type": "ir.actions.act_window", "res_model": "kojto.profile.batches", "view_mode": "form", "res_id": new_batch.id, "target": "current"}

    _report_ref = "kojto_profiles.print_profile_batches"

    def export_to_excel(self):
        file_content, filename = export_profile_batch_to_excel(self)
        self.excel_file = file_content
        self.excel_filename = filename
        return {"type": "ir.actions.act_url", "url": f"/web/content?model={self._name}&id={self.id}&field=excel_file&filename_field=excel_filename&download=true", "target": "self"}

    @api.depends("subcode_id")
    def generate_batch_name(self):
        for record in self:
            if not all([record.subcode_id, record.subcode_id.code_id, record.subcode_id.maincode_id]):
                record.name = ""
                continue
            base_name_prefix = ".".join([record.subcode_id.maincode_id.maincode, record.subcode_id.code_id.code, record.subcode_id.subcode, "BCH"])
            self.env.cr.execute("""
                SELECT MAX(CAST(RIGHT(name, 3) AS INTEGER)) as num
                FROM kojto_profile_batches
                WHERE name LIKE %s AND id != %s
            """, (f"{base_name_prefix}.%", record.id or 0))
            last_number = self.env.cr.fetchone()[0] or 0
            next_number = last_number + 1
            if next_number > 999:
                raise ValidationError(f"Maximum batch number reached for {base_name_prefix}")
            record.name = f"{base_name_prefix}.{str(next_number).zfill(3)}"
        return {}

    def action_open_create_from_batch_wizard(self):
        self.ensure_one()
        if not self.batch_content_ids:
            raise UserError(_("No profiles found in the batch to create from."))

        # Collect unique profile IDs from the current batch, filtering out None values
        unique_profile_ids = set()
        for content in self.batch_content_ids:
            if content.profile_id:
                unique_profile_ids.add(content.profile_id.id)
            else:
                _logger.warning(f"Batch content with position {content.position} does not have a profile_id.")

        if not unique_profile_ids:
            raise UserError(_("No valid profiles found in the batch."))

        # Collect unique shape IDs associated with the profiles in the batch
        unique_shape_ids = set()
        for content in self.batch_content_ids:
            if content.profile_id and hasattr(content.profile_id, 'shape_ids') and content.profile_id.shape_ids:
                for shape in content.profile_id.shape_ids:
                    unique_shape_ids.add(shape.id)
            elif content.profile_id:
                _logger.debug(f"Profile {content.profile_id.name} has no shape_ids attribute or no shapes associated.")

        # Prepare wizard lines only for profiles in the current batch
        profile_lines = [(0, 0, {
            'profile_id': profile_id,
            'is_selected': True
        }) for profile_id in unique_profile_ids]

        # Create the wizard instance
        wizard = self.env['kojto.profile.create.from.batch.wizard'].create({
            'batch_id': self.id,
            'profile_line_ids': profile_lines
        })

        # Return action to open the wizard with filtered profile and shape IDs
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create New Batch from Profiles'),
            'res_model': 'kojto.profile.create.from.batch.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': {
                'default_batch_id': self.id,
                'restrict_to_batch_profiles': True,
                'allowed_profile_ids': list(unique_profile_ids),
                'allowed_shape_ids': list(unique_shape_ids)
            }
        }

    def action_import_batch_content(self):
        self.ensure_one()
        header = "Position\tProfile\tLength\tQuantity\tLengthExtension\tDescription\n"
        if self.batch_content_ids:
            lines = [
                f"{content.position or ''}\t{content.profile_id.name or ''}\t{content.length or 0.0}\t{content.quantity or 0}\t{content.length_extension or 0.0}\t{content.description or ''}"
                for content in self.batch_content_ids
            ]
            first_line = lines[0].split("\t") if lines else []
            is_header = (
                len(first_line) >= 5 and
                first_line[0].strip() == "Position" and
                first_line[1].strip() == "Profile" and
                first_line[2].strip() == "Length" and
                first_line[3].strip() == "Quantity" and
                first_line[4].strip() == "LengthExtension"
            )
            data_lines = lines[1:] if is_header and len(lines) > 1 else lines
            batch_content_data = header + "\n".join(data_lines) + "\n"
        else:
            batch_content_data = header
        return {
            "name": "Import Batch Content",
            "type": "ir.actions.act_window",
            "res_model": "kojto.profile.batch.content.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "default_data": batch_content_data,
                "dialog_size": "small",
            },
        }
