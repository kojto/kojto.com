from odoo import models, fields, api, _
from ...utils.kojto_en1090_name_generator import generate_document_name, WPS_PREFIX
from ..mixins.kojto_en1090_pdf_generator import KojtoEn1090PDFGenerator
import json
from odoo.exceptions import ValidationError

class KojtoEn1090WPS(models.Model):
    _name = 'kojto.en1090.wps'
    _description = 'WPS'
    _order = 'name'
    _rec_name = "name_summary"
    _inherit = ['kojto.en1090.pdf.generator']

    # Reports config for printing
    _report_ref = 'kojto_en1090.report_kojto_en1090_wps'
    _report_css_ref = 'kojto_pdf_1090_document.css'

    name = fields.Char(string="Name", compute="generate_name", store=True, copy=False, readonly=True)
    name_secondary = fields.Char(string="Number", copy=False)
    name_summary = fields.Char(string="Name Summary", compute="_compute_name_summary", store=True, copy=False, readonly=True)
    include_document_in_bundle = fields.Boolean(string="Include Document in Bundle", default=False)

    active = fields.Boolean(string="Active", default=True, readonly=True)
    description = fields.Text(string="Description")
    language_id = fields.Many2one("res.lang", string="Language", default=1)
    issued_by = fields.Many2one("kojto.contacts", string="Issued By", default=1, required=True)

    wps_type = fields.Selection([("preliminary", "Preliminary"), ("production", "Production"), ("equipment", "Equipment")], string="WPS Type", default="preliminary")
    date_issue = fields.Date(string="Issue Date", required=True, default=fields.Date.today)

    wpqr_id = fields.Many2one('kojto.en1090.wpqrs', string='WPQR Reference')
    welder_id = fields.Many2one('kojto.en1090.welding.specialists', string='Welder', domain="[('is_certified_welder', '=', True)]")
    welding_engineer_id = fields.Many2one('kojto.en1090.welding.specialists', string='IWE', domain="[('is_welding_engineer', '=', True)]")

    wall_thickness = fields.Char(string="Thickness (mm)", help="Wall thickness of the tube", default="1")
    depth_of_penetration = fields.Char(string="Penetration (mm)", help="Depth of penetration of the weld", default="1")
    tube_diameter = fields.Char(string="Diameter (mm)", help="Diameter of the tube", default="1")

    # Attributes
    material_ids = fields.Many2many("kojto.base.material.grades", string="Materials", relation="wps_material_grades_rel")
    welding_joint_geometry_id = fields.Many2one("kojto.en1090.weld.geometries", string="Joint Geometry", help="Geometry types of welding joints used in this WPS (e.g. V-groove, fillet, etc.)")
    welding_joint_svg = fields.Binary(related="welding_joint_geometry_id.weld_drawing_svg", string="Welding Joint SVG", attachment=True, help="SVG representation of the welding joint geometry")

    equipment_ids = fields.Many2many("kojto.en1090.equipment", string="Equipment used for the WPS")
    welding_position = fields.Selection([
        ("PA", "PA - Flat"),
        ("PB", "PB - Horizontal Fillet"),
        ("PC", "PC - Horizontal Groove"),
        ("PD", "PD - Horizontal Overhead"),
        ("PE", "PE - Overhead Groove"),
        ("PF", "PF - Vertical Up"),
        ("PG", "PG - Vertical Down"),
        ("PH", "PH - Pipe Horizontal")], string="Position", default="PA")


    surface_preparation_description = fields.Char(string="Surface Preparation", help="Method used for preparing the base metal surface before welding", default="grinding")
    interpass_cleaning_description = fields.Char(string="Interpass Cleaning", help="Method used for cleaning between weld passes", default="brushing")
    post_weld_finishing_description = fields.Char(string="Post-weld Finishing", help="Method used for finishing the weld surface after completion", default="brushing")

    weld_deposition_ids = fields.One2many("kojto.en1090.weld.depositions", "wps_id", string="Welding Depositions")
    wps_used_on_batch_ids = fields.Many2many("kojto.warehouses.batches", string="WPS Used On Batch")
    json_properties_of_batch_materials = fields.Json(string="Properties of Batch Materials", compute="_compute_json_properties_of_batch_materials")
    weld_deposition_summary = fields.Html(string="Weld Deposition Summary", compute="_compute_weld_deposition_summary")
    attachment_id = fields.Many2many("ir.attachment", string="Attachment", relation="kojto_en1090_wps_attachment_rel", domain="[('res_model', '=', 'kojto.en1090.wps'), ('res_id', '=', id), ('mimetype', '=', 'application/pdf')]")

    degree_of_mechanisation = fields.Selection([
        ('manual_welding', 'Manual Welding'),
        ('mechanized_welding', 'Mechanized Welding'),
        ('automated_welding', 'Automated Welding')
    ], string="Degree of Mechanisation", default="manual_welding", required=True)

    wpqr_range_of_approval = fields.Text(related="wpqr_id.range_of_approval", string="Range of Approval")
    material_summary = fields.Char(compute="_compute_material_summary", string="Materials")

    @api.constrains('attachment_id')
    def _check_single_pdf_attachment(self):
        for record in self:
            if len(record.attachment_id) > 1:
                raise ValidationError(_("Only one PDF attachment is allowed per WPS."))

    @api.constrains('wps_type', 'wpqr_id')
    def _check_wpqr_for_preliminary(self):
        for record in self:
            if record.wps_type == 'preliminary' and record.wpqr_id:
                raise ValidationError(_("A preliminary WPS cannot have a WPQR Reference. Please clear the WPQR Reference field."))

    @api.model
    def create(self, vals):
        # If creating as preliminary, ensure wpqr_id is not set
        if vals.get('wps_type') == 'preliminary':
            vals['wpqr_id'] = False
        return super().create(vals)

    def write(self, vals):
        # If changing to preliminary, clear wpqr_id
        if 'wps_type' in vals and vals['wps_type'] == 'preliminary':
            vals['wpqr_id'] = False
        # If trying to set wpqr_id while type is preliminary, block it
        if (vals.get('wpqr_id') or (not vals.get('wpqr_id') is None)):
            for rec in self:
                new_type = vals.get('wps_type', rec.wps_type)
                if new_type == 'preliminary' and vals.get('wpqr_id'):
                    raise ValidationError(_("A preliminary WPS cannot have a WPQR Reference. Please clear the WPQR Reference field."))
        return super().write(vals)

    @api.depends('wps_used_on_batch_ids')
    def _compute_json_properties_of_batch_materials(self):
        property_fields_chemical = [
            'carbon', 'silicon', 'manganese', 'chromium', 'molybdenum', 'vanadium', 'nickel', 'copper',
            'phosphorus', 'sulfur', 'nitrogen', 'titanium', 'magnesium', 'zinc', 'iron', 'aluminum',
            'tin', 'cobalt', 'boron', 'carbon_equivalent'
        ]
        property_fields_mechanical = [
            'yield_strength_0_2', 'yield_strength_1_0', 'tensile_strength', 'elongation', 'reduction_of_area',
            'impact_energy', 'impact_temperature', 'hardness_hb', 'hardness_hrc', 'hardness_hv',
            'young_modulus', 'poisson_ratio', 'density', 'thermal_expansion', 'thermal_conductivity',
            'electrical_resistivity'
        ]
        for record in self:
            result = []
            for batch in record.wps_used_on_batch_ids:
                batch_json = []
                for prop in batch.batch_properties_ids:
                    chemical = {field: getattr(prop, field) for field in property_fields_chemical}
                    mechanical = {field: getattr(prop, field) for field in property_fields_mechanical}
                    extra = {
                        'name': prop.name,
                        'description': prop.description,
                        'melting_process': prop.melting_process,
                        'material_grade_id': prop.material_grade_id.id if prop.material_grade_id else None,
                        'material_grade_name': prop.material_grade_id.name if prop.material_grade_id else None,
                    }
                    batch_json.append({
                        'chemical': chemical,
                        'mechanical': mechanical,
                        'extra': extra
                    })
                result.append(batch_json)
            record.json_properties_of_batch_materials = json.dumps(result)

    @api.depends('wps_type')
    def generate_name(self):
        for record in self:
            prefix = 'pWPS' if record.wps_type == 'preliminary' else 'WPS'
            record.name = f"{prefix}.{str(record.id).zfill(6)}"

    def open_o2m_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': '',
            'res_model': 'kojto.en1090.wps',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wps_type': self.wps_type,
            }
        }

    def copy_wps(self):
        """Copy the current WPS and create a new one with the same data."""
        self.ensure_one()
        # Create a copy of the current record
        new_wps = self.copy({
            'name': False,  # Let the name be recomputed
            'wps_type': self.wps_type,
            'date_issue': fields.Date.today(),
            'welder_id': self.welder_id.id,
            'welding_engineer_id': self.welding_engineer_id.id,
            'material_ids': [(6, 0, self.material_ids.ids)],
            'welding_joint_geometry_id': self.welding_joint_geometry_id.id,
            'equipment_ids': [(6, 0, self.equipment_ids.ids)],
            'welding_position': self.welding_position,
            'surface_preparation_description': self.surface_preparation_description,
            'interpass_cleaning_description': self.interpass_cleaning_description,
            'post_weld_finishing_description': self.post_weld_finishing_description,
        })

        # Copy weld depositions if any
        if self.weld_deposition_ids:
            for deposition in self.weld_deposition_ids:
                # Copy the deposition with context to prevent automatic parameter generation
                new_deposition = deposition.with_context(skip_parameter_generation=True).copy({
                    'wps_id': new_wps.id,
                    'name': deposition.name,  # Keep the original name
                    'sequence_in_wps': deposition.sequence_in_wps,
                    'number_of_passes': deposition.number_of_passes,
                    'welding_process_id': deposition.welding_process_id.id if deposition.welding_process_id else False,
                })

                # Manually copy all parameter contents with their values
                if deposition.parameter_content_ids:
                    for param_content in deposition.parameter_content_ids:
                        param_content.copy({
                            'weld_deposition_id': new_deposition.id,
                            'welding_parameter_id': param_content.welding_parameter_id.id if param_content.welding_parameter_id else False,
                            'value': param_content.value,
                        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'WPS',
            'res_model': 'kojto.en1090.wps',
            'res_id': new_wps.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def print_document(self):
        """Print the WPS document using Odoo's standard report system."""
        self.ensure_one()
        return self.print_document_as_pdf()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'wps_type' in fields_list and self._context.get('default_wps_type'):
            res['wps_type'] = self._context['default_wps_type']
        return res

    @api.depends('weld_deposition_ids', 'weld_deposition_ids.parameter_content_ids', 'weld_deposition_ids.parameter_content_ids.value')
    def _compute_weld_deposition_summary(self):
        for record in self:
            if not record.weld_deposition_ids:
                record.weld_deposition_summary = ""
                continue

            # Get all weld depositions sorted by sequence
            depositions = record.weld_deposition_ids.sorted('sequence_in_wps')

            # Collect all unique parameters used across all depositions
            all_parameters = set()
            for deposition in depositions:
                for param_content in deposition.parameter_content_ids:
                    try:
                        if param_content.welding_parameter_id and param_content.welding_parameter_id.exists():
                            all_parameters.add(param_content.welding_parameter_id)
                    except:
                        # Skip invalid parameter content
                        continue

            # Convert to sorted list for consistent column order
            # Filter out any records that don't exist and handle missing names
            valid_parameters = []
            for param in all_parameters:
                try:
                    if param.exists() and param.name:
                        valid_parameters.append(param)
                except:
                    # Skip invalid parameters
                    continue

            unique_parameters = sorted(valid_parameters, key=lambda x: x.name)

            # Check which parameters have values (not all empty)
            parameters_with_values = []
            for param in unique_parameters:
                try:
                    if not param.exists():
                        continue
                    has_values = False
                    for deposition in depositions:
                        param_content = deposition.parameter_content_ids.filtered(
                            lambda pc: pc.welding_parameter_id and pc.welding_parameter_id.exists() and pc.welding_parameter_id.id == param.id
                        )
                        if param_content and param_content[0].value:
                            has_values = True
                            break
                    if has_values:
                        parameters_with_values.append(param)
                except:
                    # Skip invalid parameters
                    continue

            # Calculate column width
            # Fixed columns: Nr, Number of Passes, Welding Process (2x width)
            # Plus parameter columns that have values
            total_columns = 2 + len(parameters_with_values)  # Excluding welding process from count
            base_column_width = 100 / (total_columns + 1)  # +1 for welding process which is 2x width
            welding_process_width = base_column_width * 2

            # Start building HTML table
            html_content = f"""
            <div style="width: 100%; overflow-x: auto; margin-bottom: 20px; margin-top: 20px;">
                <table class="performance-table" style="width: 100%; max-width: 100%; border-collapse: collapse; word-wrap: break-word; word-break: normal;">
                    <thead>
                        <tr style="background-color: #B0C4DE; font-weight: bold;">
                            <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: 100%;" colspan="{total_columns + 1}">Weld Depositions</th>
                        </tr>
                        <tr style="background-color: #B0C4DE; font-weight: bold;">
                            <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {base_column_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Nr</th>
                            <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {base_column_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Passes</th>
                            <th style="padding: 4px; border: 1px solid #ddd; text-align: left; width: {welding_process_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Process</th>
            """

            # Add parameter columns (only those with values)
            for param in parameters_with_values:
                try:
                    if not param.exists():
                        continue
                    param_header = param.abbreviation or self.get_translated_welding_parameter_name(param) or param.name
                    if param.unit:
                        param_header += f" ({param.unit})"
                    html_content += f"""
                                <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {base_column_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">{param_header}</th>
                    """
                except:
                    # Skip invalid parameters
                    continue

            html_content += """
                        </tr>
                    </thead>
                    <tbody>
                """

            # Add rows for each deposition
            for deposition in depositions:
                # Get translated welding process name
                process_name = ''
                try:
                    if deposition.welding_process_id and deposition.welding_process_id.exists():
                        process_name = self.get_translated_welding_process_name(deposition.welding_process_id) or ''
                except:
                    process_name = ''

                html_content += f"""
                    <tr>
                        <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{deposition.sequence_in_wps or ''}</td>
                        <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{deposition.number_of_passes or ''}</td>
                        <td style="padding: 4px; border: 1px solid #ddd; text-align: left; word-wrap: break-word; white-space: normal;">{process_name}</td>
                """

                # Add parameter values for this deposition (only for parameters with values)
                for param in parameters_with_values:
                    try:
                        if not param.exists():
                            value = ''
                        else:
                            # Find the parameter content for this deposition and parameter
                            param_content = deposition.parameter_content_ids.filtered(
                                lambda pc: pc.welding_parameter_id and pc.welding_parameter_id.exists() and pc.welding_parameter_id.id == param.id
                            )

                            if param_content:
                                value = param_content[0].value or ''
                            else:
                                value = ''
                    except:
                        value = ''

                    html_content += f"""
                        <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{value}</td>
                    """

                html_content += """
                    </tr>
                """

            html_content += """
                    </tbody>
                </table>
            </div>
            """

            # Add parameter legend if there are parameters with values
            if parameters_with_values:
                html_content += """
            <div style="margin-top: 10px; margin-bottom: 20px;">
                <h4 style="margin-bottom: 10px; font-size: 10px; font-weight: bold;">Welding Parameters Legend:</h4>
                <ul style="list-style-type: none; padding: 0; margin: 0; columns: 2; column-gap: 20px; font-size: 8px;">
                """

                for param in parameters_with_values:
                    try:
                        if not param.exists():
                            continue
                        abbreviation = param.abbreviation or param.name
                        # Get translated parameter name
                        full_name = self.get_translated_welding_parameter_name(param) or param.name
                        html_content += f"""
                        <li style="margin-bottom: 3px; break-inside: avoid;">
                            <strong>{abbreviation}:</strong> {full_name}
                        </li>
                        """
                    except:
                        # Skip invalid parameters
                        continue

                html_content += """
                </ul>
            </div>
            """

            record.weld_deposition_summary = html_content

    @api.depends('name', 'name_secondary', 'weld_deposition_ids', 'weld_deposition_ids.welding_process_id')
    def _compute_name_summary(self):
        for record in self:
            name = record.name or ''
            name_secondary = record.name_secondary or ''

            # Get process codes
            process_codes = set()
            for deposition in record.weld_deposition_ids:
                if deposition.welding_process_id and deposition.welding_process_id.code:
                    process_codes.add(deposition.welding_process_id.code)
            process_summary = ', '.join(sorted(process_codes))

            # Build name summary
            parts = []
            if name:
                parts.append(name)
            if name_secondary:
                parts.append(name_secondary)
            if process_summary:
                parts.append(process_summary)

            record.name_summary = ' - '.join(parts) if parts else ''

    @api.depends('material_ids', 'material_ids.name')
    def _compute_material_summary(self):
        for record in self:
            if record.material_ids:
                material_names = [material.name for material in record.material_ids if material.name]
                record.material_summary = ', '.join(sorted(material_names)) if material_names else ""
            else:
                record.material_summary = ""

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
            try:
                return record.name or ''
            except:
                return ''

        # Map model names to their corresponding reference fields in translations
        model_to_field_map = {
            'kojto.en1090.welding.specialists': 'specialist_id',
            'kojto.en1090.weld.geometries': 'geometry_id',
            'kojto.en1090.welding.processes': 'process_id',
            'kojto.en1090.welding.parameters': 'parameter_id',
        }

        reference_field = model_to_field_map.get(model_name)
        if not reference_field:
            try:
                return record.name or ''
            except:
                return ''

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
            try:
                return record.name or ''
            except:
                return ''

    def get_translated_specialist_name(self, specialist):
        """Get translated name for a welding specialist"""
        return self.get_translated_name(specialist, 'kojto.en1090.welding.specialists')

    def get_translated_welding_parameter_name(self, parameter):
        """Get translated name for a welding parameter"""
        return self.get_translated_name(parameter, 'kojto.en1090.welding.parameters')

    def get_translated_welding_process_name(self, process):
        """Get translated name for a welding process"""
        return self.get_translated_name(process, 'kojto.en1090.welding.processes')

    def get_translated_weld_geometry_name(self, geometry):
        """Get translated name for a weld geometry"""
        return self.get_translated_name(geometry, 'kojto.en1090.weld.geometries')
