from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.kojto_en1090_name_generator import generate_document_name, WELDING_TASK_PREFIX
from .mixins.kojto_en1090_pdf_generator import KojtoEn1090PDFGenerator


class KojtoEn1090DocWeldingTasks(models.Model):
    _name = "kojto.en1090.doc.welding.tasks"
    _description = "Welding Tasks"
    _order = "name"
    _inherit = ["kojto.en1090.pdf.generator"]

    # Reports config for printing
    _report_ref = "kojto_en1090.report_kojto_en1090_doc_welding_tasks"
    _report_css_ref = "kojto_pdf_1090_document.css"

    name = fields.Char(string="Name", compute="generate_name", store=True, copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True, readonly=True)
    document_bundle_id = fields.Many2one("kojto.en1090.document.bundles", string="Document Bundle", required=True)
    include_document_in_bundle = fields.Boolean(string="Include Document in Bundle", default=True)

    language_id = fields.Many2one("res.lang", string="Language", default=1)
    date_issue = fields.Date(string="Issue Date", required=True, default=fields.Date.today)
    date_planned = fields.Date(string="Planned Start Date")
    date_executed = fields.Date(string="Execution Start Date")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'document_bundle_id' in fields_list and self._context.get('default_document_bundle_id'):
            res['document_bundle_id'] = self._context['default_document_bundle_id']
        return res

    # Common Fields
    technical_document_revision_id = fields.Many2one("kojto.technical.doc.revisions", string="Drawing")
    equipment_ids = fields.Many2many("kojto.en1090.equipment", string="Equipment", relation="welding_tasks_equipment_rel")

    # Personnel
    plan_issued_by = fields.Many2one("kojto.en1090.welding.specialists", string="Plan Issued By", required=True)
    journal_signed_by = fields.Many2one("kojto.en1090.welding.specialists", string="Journal Signed By", required=True)

    # Welding Seams
    welding_seam_ids = fields.One2many("kojto.en1090.welding.seams", "welding_task_id", string="Welding Seams")

    # Plan Details
    plan_description = fields.Text(string="Plan Description", help="Description of the planned welding work")
    journal_description = fields.Text(string="Journal Description", help="Description of the executed welding work")

    factory_task_id = fields.Many2one("kojto.factory.tasks", string="Factory Task")

    # Computed fields based on welding seams' WPS
    welding_processes_summary = fields.Char(string="Welding Processes", compute="_compute_welding_processes_summary")
    materials_summary = fields.Char(string="Materials", compute="_compute_materials_summary")

    @api.depends("document_bundle_id")
    def generate_name(self):
        for record in self:
            record.name = generate_document_name(record, record.document_bundle_id, WELDING_TASK_PREFIX)

    @api.depends("welding_seam_ids", "welding_seam_ids.applicable_wps_id", "welding_seam_ids.applicable_wps_id.weld_deposition_ids", "welding_seam_ids.applicable_wps_id.weld_deposition_ids.welding_process_id")
    def _compute_welding_processes_summary(self):
        for record in self:
            processes = set()
            for seam in record.welding_seam_ids:
                if seam.applicable_wps_id and seam.applicable_wps_id.weld_deposition_ids:
                    for deposition in seam.applicable_wps_id.weld_deposition_ids:
                        if deposition.welding_process_id:
                            processes.add(deposition.welding_process_id.name)
            record.welding_processes_summary = ", ".join(sorted(processes)) if processes else ""

    @api.depends("welding_seam_ids", "welding_seam_ids.applicable_wps_id", "welding_seam_ids.applicable_wps_id.material_ids")
    def _compute_materials_summary(self):
        for record in self:
            materials = set()
            for seam in record.welding_seam_ids:
                if seam.applicable_wps_id and seam.applicable_wps_id.material_ids:
                    for material in seam.applicable_wps_id.material_ids:
                        materials.add(material.name)
            record.materials_summary = ", ".join(sorted(materials)) if materials else ""

    def get_translated_name(self, record, model_name):
        """
        Get the translated name for a record based on the document's language.
        If no translation is available, return the original name.

        Args:
            record: The record to get translation for
            model_name: The model name for the translation lookup

        Returns:
            str: The translated name or original name if no translation exists
        """
        if not record or not record.id:
            return ''

        # Check if record still exists
        try:
            if not record.exists():
                return ''
        except:
            return ''

        if not self.document_bundle_id or not self.document_bundle_id.language_id:
            return record.name or ''

        # Map model names to their corresponding reference fields in translations
        model_to_field_map = {
            'kojto.en1090.welding.specialists': 'specialist_id',
            'kojto.en1090.weld.geometries': 'geometry_id',
            'kojto.en1090.welding.processes': 'process_id',
            'kojto.en1090.welding.parameters': 'parameter_id',
        }

        reference_field = model_to_field_map.get(model_name)
        if not reference_field:
            return record.name or ''

        # Look for translation in the translations table using the specific reference field
        domain = [
            (reference_field, '=', record.id),
            ('language_id', '=', self.document_bundle_id.language_id.id),
            ('active', '=', True)
        ]

        translation = self.env['kojto.en1090.translations'].search(domain, limit=1)

        if translation:
            return translation.translated_name
        else:
            return record.name or ''

    def get_translated_specialist_name(self, specialist):
        """
        Get the translated name for a welding specialist.

        Args:
            specialist: The welding specialist record

        Returns:
            str: The translated name or original name if no translation exists
        """
        return self.get_translated_name(specialist, 'kojto.en1090.welding.specialists')

    def get_translated_welding_parameter_name(self, parameter):
        """
        Get the translated name for a welding parameter.

        Args:
            parameter: The welding parameter record

        Returns:
            str: The translated name or original name if no translation exists
        """
        return self.get_translated_name(parameter, 'kojto.en1090.welding.parameters')

    def get_translated_welding_process_name(self, process):
        """
        Get the translated name for a welding process.

        Args:
            process: The welding process record

        Returns:
            str: The translated name or original name if no translation exists
        """
        return self.get_translated_name(process, 'kojto.en1090.welding.processes')

    def get_translated_weld_geometry_name(self, geometry):
        """
        Get the translated name for a weld geometry.

        Args:
            geometry: The weld geometry record

        Returns:
            str: The translated name or original name if no translation exists
        """
        return self.get_translated_name(geometry, 'kojto.en1090.weld.geometries')

    def action_view_welding_seams(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Welding Seams"),
            "res_model": "kojto.en1090.welding.seams",
            "view_mode": "list,form",
            "domain": [("id", "in", self.welding_seam_ids.ids)],
            "context": {"create": False},
        }

    def action_generate_plan_report(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Welding Plan Report"),
            "res_model": "kojto.en1090.doc.welding.tasks",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "context": {"report_type": "plan"},
        }

    def action_generate_journal_report(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Welding Journal Report"),
            "res_model": "kojto.en1090.doc.welding.tasks",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "context": {"report_type": "journal"},
        }

    def open_o2m_record(self):
        """Open the record in a new form view."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def copy_welding_task(self):
        """Copy the current welding task and create a new one with the same data."""
        self.ensure_one()
        # Create a copy of the current record
        new_task = self.copy({
            'name': False,  # Let the name be recomputed
            'document_bundle_id': self.document_bundle_id.id,
            'date_issue': fields.Date.today(),
            'date_planned': self.date_planned,
            'date_executed': False,  # Reset execution date
            'technical_document_revision_id': self.technical_document_revision_id.id,
            'equipment_ids': [(6, 0, self.equipment_ids.ids)],
            'plan_issued_by': self.plan_issued_by.id,
            'journal_signed_by': self.journal_signed_by.id,
            'plan_description': self.plan_description,
            'journal_description': False,  # Reset journal description
        })

        # Copy welding seams if any
        if self.welding_seam_ids:
            for seam in self.welding_seam_ids:
                seam.copy({
                    'welding_task_id': new_task.id,
                })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Welding Task',
            'res_model': 'kojto.en1090.doc.welding.tasks',
            'res_id': new_task.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def print_document(self):
        self.ensure_one()
        return self.print_document_as_pdf()
