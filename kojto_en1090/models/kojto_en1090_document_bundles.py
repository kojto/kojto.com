from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import pdf
from weasyprint import HTML
import os
import base64
import tempfile
import logging
from ..utils.compute_document_bundle_content import compute_document_bundle_content
from ..utils.print_complete_document_bundle import print_complete_document_bundle

_logger = logging.getLogger(__name__)

class KojtoEn1090DocumentBundles(models.Model):
    _name = "kojto.en1090.document.bundles"
    _description = "En1090 Document Bundles"
    _inherit = ["kojto.library.printable"]

    _report_ref = "kojto_en1090.report_kojto_en1090_document_bundles"
    _dop_report_ref = "kojto_en1090.report_kojto_en1090_doc_performance"
    _ce_label_report_ref = "kojto_en1090.report_kojto_en1090_ce_label"
    _report_css_ref = "kojto_pdf_1090_document.css"

    # Meta Fields
    name = fields.Char(string="Name", compute="generate_name", store=True, copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True)
    date_issue = fields.Date(string="Issue Date", required=True, default=fields.Date.today)
    description = fields.Text(string="Description")

    # Attachment Fields
    pdf_attachment_id = fields.Many2one('ir.attachment', string="PDF Attachment", copy=False)
    complete_pdf_attachment_id = fields.Many2one('ir.attachment', string="Complete PDF Attachment", copy=False)
    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'kojto.en1090.document.bundles')], string='Attachments')

    # header start
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True)
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', company_id)]")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', company_id)]")

    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", ondelete="restrict", required=True, domain="[('id', '!=', company_id), ('active', '=', True)]")
    counterparty_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', counterparty_id)]")
    counterparty_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', counterparty_id)]")
    counterpartys_reference = fields.Char(string="Your Reference")

    notified_body_id = fields.Many2one("kojto.contacts", string="Notified Body", ondelete="restrict", required=True, domain="[('id', '!=', company_id), ('active', '=', True)]")
    notified_body_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', notified_body_id)]")
    notified_body_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', notified_body_id)]")

    avcp_system = fields.Selection([('system_2_plus', 'System 2+'), ('system_1', 'System 1'), ('system_1_plus', 'System 1+'), ('system_3', 'System 3'), ('system_4', 'System 4')], string="AVCP System", default='system_2_plus', required=True, help="System of Assessment and Verification of Constancy of Performance per CPR")
    execution_class = fields.Selection([('EXC1', 'EXC 1'), ('EXC2', 'EXC 2'), ('EXC3', 'EXC 3'), ('EXC4', 'EXC 4')], string="Execution Class", required=True, default='EXC2')

    # Performance Declaration Fields
    dop_standard_reference = fields.Selection([('EN1090-1', 'EN 1090-1'), ('EN1090-2', 'EN 1090-2'), ('EN1090-3', 'EN 1090-3'), ('EN1090-4', 'EN 1090-4')], string="Standard Reference", default="EN1090-1", required=True)
    dop_content_description = fields.Char(string="Content Description", default="Enter Content Description")
    dop_intended_use = fields.Selection([('structural', 'Structural'), ('non_structural', 'Non-Structural'), ('both', 'Both Structural and Non-Structural')], string="Intended Use", default='structural')

    # Performance Criteria - Structural
    dop_dimension_tolerances = fields.Char(string="Dimension Tolerances", default="compliant")
    dop_load_bearing_capacity = fields.Char(string="Load Bearing Capacity", default="npd")
    dop_serviceability_limit_state_deformation = fields.Char(string="SLS Deformation", default="compliant")
    dop_fatigue_strength = fields.Char(string="Fatigue Strength", default="npd")

    # Performance Criteria - Material
    dop_weldability = fields.Char(string="Weldability", default="S235")
    dop_fracture_toughness = fields.Char(string="Fracture Toughness", default="-")
    dop_durability = fields.Char(string="Durability", default="NA")

    # Performance Criteria - Safety
    dop_resistance_to_fire = fields.Char(string="Resistance to Fire", default="npd")
    dop_reaction_to_fire = fields.Char(string="Reaction to Fire", default="class_a1")
    dop_cadmium_release = fields.Char(string="Cadmium Release", default="npd")
    dop_radioactivity_emission = fields.Char(string="Radioactivity Emission", default="npd")

    # Performance Declaration Personnel
    dop_signed_by = fields.Char(string="Signed By")

    # One2many relations to other models
    technical_document_revision_ids = fields.Many2many("kojto.technical.doc.revisions", "kojto_en1090_doc_bundle_tech_doc_rel", "bundle_id", "revision_id", string="Technical Documents")
    delivery_ids = fields.Many2many("kojto.deliveries", string="Deliveries", relation="kojto_en1090_doc_bundle_delivery_rel", domain="[('subcode_id', '=', subcode_id)]")
    wps_record_ids = fields.Many2many("kojto.en1090.wps", "kojto_en1090_doc_bundle_wps_rel", "bundle_id", "wps_id", string="WPS Records")
    control_document_ids = fields.One2many("kojto.en1090.doc.control", "document_bundle_id", string="Controls")
    welding_task_ids = fields.One2many("kojto.en1090.doc.welding.tasks", "document_bundle_id", string="Welding Jobs")
    warehouse_certificate_ids = fields.Many2many("kojto.warehouses.certificates", "kojto_en1090_doc_bundle_warehouse_cert_rel", "bundle_id", "certificate_id", string="Warehouse Certificates")
    warehouse_inspection_report_ids = fields.Many2many("kojto.warehouses.inspection.report", compute="_compute_warehouse_inspection_report_ids", string="Warehouse Inspection Reports")
    welding_certificates_ids = fields.Many2many("kojto.en1090.welding.certificates", string="Welding Certificates", relation="kojto_en1090_doc_bundle_weld_cert_rel")

    document_bundle_content = fields.Html(string="Document Bundle Content", compute="_compute_document_bundle_content")

    @api.depends("subcode_id")
    def generate_name(self):
        for record in self:
            if not record.subcode_id:
                record.name = ""
                continue

            domain = [("subcode_id", "=", record.subcode_id.id), ("id", "!=", record.id if record.id else False)]
            count = self.search_count(domain)

            record.name = f"{record.subcode_id.name}.EN1090.{count + 1}"

    def print_document_bundle(self):
        self.ensure_one()
        return self.print_document_as_pdf()

    def print_dop_declaration(self):
        self.ensure_one()
        return self.with_context(
            report_ref=self._dop_report_ref,
            force_report_ref=True
        ).print_document_as_pdf()

    def print_complete_document_bundle(self):
        _logger.info("Starting print_complete_document_bundle method")
        try:
            # Verify required fields are set
            self.ensure_one()
            _logger.info(f"Processing document bundle: {self.name}")

            # Check required fields
            required_fields = {
                'company_name_id': 'Company Name',
                'company_address_id': 'Company Address',
                'counterparty_name_id': 'Counterparty Name',
                'counterparty_address_id': 'Counterparty Address',
                'notified_body_name_id': 'Notified Body Name',
                'notified_body_address_id': 'Notified Body Address'
            }

            missing_fields = []
            for field, label in required_fields.items():
                if not getattr(self, field):
                    missing_fields.append(label)

            if missing_fields:
                _logger.error(f"Missing required fields: {', '.join(missing_fields)}")
                raise UserError(_("Please fill in all required fields before printing: %s") % ', '.join(missing_fields))

            _logger.info("All required fields are present, proceeding with print")
            return print_complete_document_bundle(self)

        except Exception as e:
            _logger.error(f"Error in print_complete_document_bundle: {str(e)}")
            raise

    @api.model
    def default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('language_id'):
                # Handle company info
                if vals.get('company_id'):
                    # Find the name in the selected language
                    name = self.env['kojto.base.names'].search([
                        ('contact_id', '=', vals['company_id']),
                        ('language_id', '=', vals['language_id'])
                    ], limit=1)
                    if name:
                        vals['company_name_id'] = name.id

                    # Find the address in the selected language
                    address = self.env['kojto.base.addresses'].search([
                        ('contact_id', '=', vals['company_id']),
                        ('language_id', '=', vals['language_id'])
                    ], limit=1)
                    if address:
                        vals['company_address_id'] = address.id

                # Handle counterparty info
                if vals.get('counterparty_id'):
                    # Find the name in the selected language
                    name = self.env['kojto.base.names'].search([
                        ('contact_id', '=', vals['counterparty_id']),
                        ('language_id', '=', vals['language_id'])
                    ], limit=1)
                    if name:
                        vals['counterparty_name_id'] = name.id

                    # Find the address in the selected language
                    address = self.env['kojto.base.addresses'].search([
                        ('contact_id', '=', vals['counterparty_id']),
                        ('language_id', '=', vals['language_id'])
                    ], limit=1)
                    if address:
                        vals['counterparty_address_id'] = address.id

        return super().create(vals_list)

    @api.onchange('counterparty_id')
    def _onchange_counterparty(self):
        if self.counterparty_id:
            # Get the language to use (either selected language or English)
            lang_id = self.language_id.id if self.language_id else self.env.ref("base.lang_en").id

            # First try to find name and address in the current language
            name = self.env['kojto.base.names'].search([
                ('contact_id', '=', self.counterparty_id.id),
                ('language_id', '=', lang_id),
                ('active', '=', True)
            ], limit=1)

            address = self.env['kojto.base.addresses'].search([
                ('contact_id', '=', self.counterparty_id.id),
                ('language_id', '=', lang_id),
                ('active', '=', True)
            ], limit=1)

            # If not found in current language, try to find any active name/address
            if not name:
                name = self.env['kojto.base.names'].search([
                    ('contact_id', '=', self.counterparty_id.id),
                    ('active', '=', True)
                ], limit=1)

            if not address:
                address = self.env['kojto.base.addresses'].search([
                    ('contact_id', '=', self.counterparty_id.id),
                    ('active', '=', True)
                ], limit=1)

            # Set the values if found
            if name:
                self.counterparty_name_id = name.id
            if address:
                self.counterparty_address_id = address.id

    @api.onchange('language_id')
    def _onchange_language_update_company_info(self):
        if self.language_id:
            # Handle company info
            if self.company_id:
                # Find the name in the selected language
                name = self.env['kojto.base.names'].search([
                    ('contact_id', '=', self.company_id.id),
                    ('language_id', '=', self.language_id.id)
                ], limit=1)
                if name:
                    self.company_name_id = name.id

                # Find the address in the selected language
                address = self.env['kojto.base.addresses'].search([
                    ('contact_id', '=', self.company_id.id),
                    ('language_id', '=', self.language_id.id)
                ], limit=1)
                if address:
                    self.company_address_id = address.id

            # Handle counterparty info
            if self.counterparty_id:
                # Find the name in the selected language
                name = self.env['kojto.base.names'].search([
                    ('contact_id', '=', self.counterparty_id.id),
                    ('language_id', '=', self.language_id.id)
                ], limit=1)
                if name:
                    self.counterparty_name_id = name.id

                # Find the address in the selected language
                address = self.env['kojto.base.addresses'].search([
                    ('contact_id', '=', self.counterparty_id.id),
                    ('language_id', '=', self.language_id.id)
                ], limit=1)
                if address:
                    self.counterparty_address_id = address.id

    @api.onchange('notified_body_id')
    def _onchange_notified_body(self):
        if self.notified_body_id:
            # Get the language to use (either selected language or English)
            lang_id = self.language_id.id if self.language_id else self.env.ref("base.lang_en").id

            # First try to find name and address in the current language
            name = self.env['kojto.base.names'].search([
                ('contact_id', '=', self.notified_body_id.id),
                ('language_id', '=', lang_id),
                ('active', '=', True)
            ], limit=1)

            address = self.env['kojto.base.addresses'].search([
                ('contact_id', '=', self.notified_body_id.id),
                ('language_id', '=', lang_id),
                ('active', '=', True)
            ], limit=1)

            # If not found in current language, try to find any active name/address
            if not name:
                name = self.env['kojto.base.names'].search([
                    ('contact_id', '=', self.notified_body_id.id),
                    ('active', '=', True)
                ], limit=1)

            if not address:
                address = self.env['kojto.base.addresses'].search([
                    ('contact_id', '=', self.notified_body_id.id),
                    ('active', '=', True)
                ], limit=1)

            # Set the values if found
            if name:
                self.notified_body_name_id = name.id
            if address:
                self.notified_body_address_id = address.id

    def action_create_control(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "New Control Document",
            "res_model": "kojto.en1090.doc.control",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_document_bundle_id": self.id
            }
        }

    def write(self, vals):
        # If 'active' is being set to False, cascade to related records
        if 'active' in vals and vals['active'] is False:
            for bundle in self:
                # Controls
                bundle.control_document_ids.write({'active': False})
                # Welding Tasks
                bundle.welding_task_ids.write({'active': False})
                # WPS Records
                bundle.wps_record_ids.write({'active': False})
                # Weld Depositions (via WPS)
                for wps in bundle.wps_record_ids:
                    wps.weld_deposition_ids.write({'active': False})
                    # Welding Parameter Contents (via Depositions)
                    for deposition in wps.weld_deposition_ids:
                        deposition.parameter_content_ids.write({'active': False})
                # Depositions directly related (if any)
                # If you have direct relations, add them here
                # Add more related models as needed
        return super().write(vals)

    @api.depends(
    'technical_document_revision_ids',
    'delivery_ids',
    'wps_record_ids',
    'welding_task_ids',
    'warehouse_certificate_ids',
    'welding_certificates_ids'
    )
    def _compute_document_bundle_content(self):
        for record in self:
            record.document_bundle_content = compute_document_bundle_content(record)

    @api.depends("warehouse_certificate_ids", "warehouse_certificate_ids.inspection_report_ids")
    def _compute_warehouse_inspection_report_ids(self):
        for record in self:
            # Collect all inspection reports from all warehouse certificates
            all_reports = self.env["kojto.warehouses.inspection.report"]
            for cert in record.warehouse_certificate_ids:
                all_reports |= cert.inspection_report_ids
            # Remove duplicates (Odoo recordsets are unique)
            record.warehouse_inspection_report_ids = all_reports

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

    def copy_document_bundle(self):
        """
        Custom method to copy a document bundle:
        - All fields are copied
        - Many2manys (welding certificates, deliveries, wps records, warehouse certificates, technical documents, attachments) are linked, not copied
        - Control documents and welding tasks are copied (new records)
        """
        self.ensure_one()
        Bundle = self
        BundleModel = self.env['kojto.en1090.document.bundles']
        ControlModel = self.env['kojto.en1090.doc.control']
        WeldingTaskModel = self.env['kojto.en1090.doc.welding.tasks']

        # Prepare values for the new bundle
        bundle_vals = Bundle.copy_data()[0]
        # Remove Odoo technical fields if present
        bundle_vals.pop('id', None)
        bundle_vals.pop('name', None)  # Let it be recomputed
        bundle_vals['date_issue'] = fields.Date.today()

        # Link many2manys (do not copy)
        bundle_vals['technical_document_revision_ids'] = [(6, 0, Bundle.technical_document_revision_ids.ids)]
        bundle_vals['delivery_ids'] = [(6, 0, Bundle.delivery_ids.ids)]
        bundle_vals['wps_record_ids'] = [(6, 0, Bundle.wps_record_ids.ids)]
        bundle_vals['warehouse_certificate_ids'] = [(6, 0, Bundle.warehouse_certificate_ids.ids)]
        bundle_vals['welding_certificates_ids'] = [(6, 0, Bundle.welding_certificates_ids.ids)]
        # Attachments (One2many to ir.attachment) - Don't link, will copy separately
        # bundle_vals['attachment_ids'] = [(6, 0, Bundle.attachment_ids.ids)]

        # Remove One2manys that should be created after (controls, welding tasks)
        bundle_vals.pop('control_document_ids', None)
        bundle_vals.pop('welding_task_ids', None)

        # Create the new bundle
        new_bundle = BundleModel.create(bundle_vals)

        # Copy control documents
        for control in Bundle.control_document_ids:
            control.copy({
                'document_bundle_id': new_bundle.id,
                'name': False,
                'date_issue': fields.Date.today(),
            })

        # Copy welding tasks
        for task in Bundle.welding_task_ids:
            task.copy({
                'document_bundle_id': new_bundle.id,
                'name': False,
                'date_issue': fields.Date.today(),
            })

        # Copy attachments - create new attachment records for each existing attachment
        for attachment in Bundle.attachment_ids:
            # Use the built-in copy method to create new attachment record
            new_attachment = attachment.copy({
                'name': attachment.name,  # Keep original name without "(Copy)" suffix
                'res_model': 'kojto.en1090.document.bundles',
                'res_id': new_bundle.id,
            })

        return new_bundle

    def action_copy_document_bundle(self):
        self.ensure_one()
        new_bundle = self.copy_document_bundle()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Copied Document Bundle'),
            'res_model': 'kojto.en1090.document.bundles',
            'res_id': new_bundle.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def import_warehouse_certificates(self):
        """
        Import and link all warehouse certificates from batches associated with consumed materials
        in deliveries attached to this bundle. Ignore certificates already linked.
        """
        self.ensure_one()
        # 1. Find all deliveries attached to the bundle
        deliveries = self.delivery_ids
        if not deliveries:
            raise UserError(_("No deliveries are attached to this document bundle."))

        # 2. For each delivery, find all consumed materials
        consumed_materials = self.env['kojto.delivery.consumed.materials']
        for delivery in deliveries:
            for content in delivery.content:
                consumed_materials |= content.content_compositions

        if not consumed_materials:
            raise UserError(_("No consumed materials found in the attached deliveries."))

        # 3. For each consumed material, find the batch
        batch_ids = consumed_materials.mapped('batch_id').filtered(lambda b: b)
        if not batch_ids:
            raise UserError(_("No batches found for the consumed materials."))

        # 4. For each batch, find all certificates
        certificate_ids = batch_ids.mapped('certificate_ids').filtered(lambda c: c)
        if not certificate_ids:
            raise UserError(_("No warehouse certificates found for the batches."))

        # 5. Link these warehouse certificates to the document bundle (ignore already linked)
        already_linked = self.warehouse_certificate_ids
        to_link = certificate_ids - already_linked
        if to_link:
            self.write({'warehouse_certificate_ids': [(4, cert.id) for cert in to_link]})
        else:
            raise UserError(_("All found warehouse certificates are already linked to this document bundle."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Warehouse Certificates Imported'),
                'message': _('%d new warehouse certificates have been linked to this document bundle.') % len(to_link),
                'type': 'success',
                'sticky': False,
            }
        }
