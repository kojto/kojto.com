from odoo import models, fields, api
from ..utils.kojto_en1090_name_generator import generate_document_name, CONTROL_PREFIX
from .mixins.kojto_en1090_pdf_generator import KojtoEn1090PDFGenerator
from odoo.exceptions import UserError, ValidationError


class KojtoEn1090DocControl(models.Model):
    _name = "kojto.en1090.doc.control"
    _description = "Control Document"
    _inherit = [
        "kojto.en1090.pdf.generator",
        "kojto.en1090.doc.control.vt.mixin",
        "kojto.en1090.doc.control.rt.mixin",
        "kojto.en1090.doc.control.mt.mixin",
        "kojto.en1090.doc.control.pt.mixin",
        "kojto.en1090.doc.control.ut.mixin",
        "kojto.en1090.doc.control.cl.mixin",
    ]


    # Reports config for printing
    _report_ref = "kojto_en1090.report_kojto_en1090_doc_control_templates"
    _report_css_ref = "kojto_pdf_1090_document.css"

    # Basic Fields
    name = fields.Char(string="Name", compute="generate_name", store=True, copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True, readonly=True)
    document_bundle_id = fields.Many2one("kojto.en1090.document.bundles", string="Document bundle")
    include_document_in_bundle = fields.Boolean(string="Include Document in Bundle", default=True)

    language_id = fields.Many2one("res.lang", string="Language", default=1)
    control_type = fields.Selection([
        ('vt', 'Visual Testing'),
        ('ut', 'Ultrasonic Testing'),
        ('mt', 'Magnetic Particle Testing'),
        ('pt', 'Penetrant Testing'),
        ('rt', 'Radiographic Testing'),
        ('cl', 'Check List'),
        ('other', 'Other')
    ], string="Control Type", required=True, default='vt')

    # Computed boolean fields for visibility
    is_vt = fields.Boolean(compute='_compute_control_type_flags')
    is_rt = fields.Boolean(compute='_compute_control_type_flags')
    is_mt = fields.Boolean(compute='_compute_control_type_flags')
    is_pt = fields.Boolean(compute='_compute_control_type_flags')
    is_ut = fields.Boolean(compute='_compute_control_type_flags')
    is_cl = fields.Boolean(compute='_compute_control_type_flags')

    # Common Fields
    date_issue = fields.Date(string="Issue Date")
    control_performeted_by = fields.Many2one("kojto.en1090.welding.specialists", string="Performed Control")
    technical_document_revision_id = fields.Many2one("kojto.technical.doc.revisions", string="Drawing")

    # Common Attributes
    stage_of_production = fields.Selection([
        ('pre_welding', 'Pre-Welding'),
        ('welding', 'Welding'),
        ('post_welding', 'Post-Welding'),
        ('assembly', 'Assembly'),
        ('final_inspection', 'Final Inspection'),
        ('packaging', 'Packaging'),
        ('shipping', 'Shipping')
    ], string="Stage of Production", required=True, default='final_inspection')

    equipment_ids = fields.Many2many("kojto.en1090.equipment", string="Equipment", relation="kojto_en1090_control_equipment_rel")
    welding_seam_ids = fields.Many2many("kojto.en1090.welding.seams", string="Welding Seams", relation="kojto_en1090_control_seams_rel")

    # Common Control Details
    defect_indications = fields.Char(string="Defect Indications", default="No indications of defects")
    illuminance = fields.Float(string="Illuminance (lux)", default=300)
    temperature = fields.Float(string="Temperature (°C)", default=20)
    percent_of_testing = fields.Char(string="Percent of Testing (%)", default="100%")
    results_statement = fields.Text(string="Results Statement", default="No defects found")
    evaluation = fields.Selection([("accepted", "Accepted"), ("rejected", "Rejected")], string="Evaluation", default="accepted")

    @api.depends("document_bundle_id", "control_type")
    def generate_name(self):
        for record in self:
            if not record.control_type:
                record.name = "Untitled"
                continue
            suffix = f"{CONTROL_PREFIX}.{record.control_type.upper()}"
            record.name = generate_document_name(record, record.document_bundle_id, suffix)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'document_bundle_id' in fields_list and self._context.get('default_document_bundle_id'):
            res['document_bundle_id'] = self._context['default_document_bundle_id']
        if 'control_type' in fields_list and 'control_type' not in res:
            res['control_type'] = 'vt'
        return res

    def copy_control(self):
        """Copy the current control document and create a new one with the same data."""
        self.ensure_one()
        # Fields that should be copied as is
        copy_fields = [
            'document_bundle_id', 'control_type', 'stage_of_production',
            'control_performeted_by', 'technical_document_revision_id',
            'equipment_ids', 'welding_seam_ids', 'defect_indications', 'illuminance'
        ]

        # Create copy dict with only the fields we want to copy
        copy_dict = {
            'name': False,  # Force name recomputation
            'date_issue': fields.Date.today(),
            'attachments': False,  # Don't copy attachments
        }
        for field in copy_fields:
            value = self[field]
            if isinstance(value, models.Model):
                if value._rec_name and value._ids and len(value) == 1:
                    # many2one, single record
                    copy_dict[field] = value.id
                else:
                    # many2many/one2many, multiple records
                    copy_dict[field] = [(6, 0, value.ids)]
            else:
                copy_dict[field] = value

        new_control = self.copy(copy_dict)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Control Document',
            'res_model': 'kojto.en1090.doc.control',
            'res_id': new_control.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def print_document(self):
        self.ensure_one()
        return self.print_document_as_pdf()



    @api.depends('control_type')
    def _compute_control_type_flags(self):
        for record in self:
            record.is_vt = record.control_type == 'vt'
            record.is_rt = record.control_type == 'rt'
            record.is_mt = record.control_type == 'mt'
            record.is_pt = record.control_type == 'pt'
            record.is_ut = record.control_type == 'ut'
            record.is_cl = record.control_type == 'cl'

    @api.depends('wps_id', 'wps_id.weld_deposition_ids')
    def _compute_sequence_in_wps(self):
        for record in self:
            if record.wps_id:
                # Get the list of ids (including new records)
                deposition_ids = record.wps_id.weld_deposition_ids.ids
                if record.id in deposition_ids:
                    record.sequence_in_wps = deposition_ids.index(record.id) + 1
                else:
                    # For new records not yet in the parent's list, assign 0 or len+1
                    record.sequence_in_wps = len(deposition_ids) + 1
            else:
                record.sequence_in_wps = 0

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

        if not self.language_id:
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
            ('language_id', '=', self.language_id.id),
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
