from odoo import models, fields, api


class KojtoEn1090WPQRS(models.Model):
    _name = "kojto.en1090.wpqrs"
    _description = "Welding Procedure Qualification Record (WPQR)"
    _rec_name = "name_summary"

    name = fields.Char(string="Name", compute="generate_name", store=True, copy=False, readonly=True)
    name_summary = fields.Char(string="Name Summary", compute="_compute_name_summary", store=True, copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True)
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)

    include_document_in_bundle = fields.Boolean(string="Include Document in Bundle", default=False)
    degree_of_mechanisation = fields.Selection(related="preliminary_wps_id.degree_of_mechanisation", string="Degree of Mechanisation")

    name_secondary = fields.Char(string="Number")
    date_issued = fields.Date(string="Issue Date", required=True)
    date_change = fields.Date(string="Revision Date")
    iso_15614_acceptance_level = fields.Selection([('b', 'B'), ('c', 'C'), ('d', 'D')], string="Acc. lv", required=True, default="b", help="Acceptance level according to ISO 15614:2023")
    preliminary_wps_id = fields.Many2one('kojto.en1090.wps', string="Preliminary WPS", required=True)
    range_of_approval = fields.Text(string="Range of Approval")
    description = fields.Text(string="Description")

    company_id = fields.Many2one("kojto.contacts", string="Company", default=lambda self: self.default_company_id(), required=True)
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', company_id)]")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', company_id)]")

    certification_body_id = fields.Many2one("kojto.contacts", string="Certification Body", ondelete="restrict", required=True, domain="[('id', '!=', company_id), ('active', '=', True)]")
    certification_body_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', certification_body_id)]")
    certification_body_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', certification_body_id)]")
    attachment_id = fields.Many2many("ir.attachment", string="Attachment", relation="kojto_en1090_wpqr_attachment_rel", domain="[('res_model', '=', 'kojto.en1090.wpqrs'), ('res_id', '=', id), ('mimetype', '=', 'application/pdf')]")

    materials_summary = fields.Char(string="Materials", compute="_compute_materials_summary")
    welding_joint_geometry_id = fields.Many2one(related="preliminary_wps_id.welding_joint_geometry_id", string="Joint")



    def default_company_id(self):
        """Return the default company for the current user."""
        return self.env.user.company_id.partner_id.id

    def copy_wpqr(self):
        """Copy the current WPQR and create a new one with the same data."""
        self.ensure_one()
        # Create a copy of the current record
        new_wpqr = self.copy({
            'name': False,  # Let the name be recomputed
            'date_issued': fields.Date.today(),
            'date_change': False,
            'preliminary_wps_id': self.preliminary_wps_id.id,
            'iso_15614_acceptance_level': self.iso_15614_acceptance_level,
            'range_of_approval': self.range_of_approval,
            'description': self.description,
            'company_id': self.company_id.id,
            'company_name_id': self.company_name_id.id,
            'company_address_id': self.company_address_id.id,
            'certification_body_id': self.certification_body_id.id,
            'certification_body_name_id': self.certification_body_name_id.id,
            'certification_body_address_id': self.certification_body_address_id.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'WPQR',
            'res_model': 'kojto.en1090.wpqrs',
            'res_id': new_wpqr.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('preliminary_wps_id', 'preliminary_wps_id.weld_deposition_ids', 'preliminary_wps_id.weld_deposition_ids.welding_process_id')
    def _compute_welding_process_summary(self):
        for record in self:
            if record.preliminary_wps_id and record.preliminary_wps_id.weld_deposition_ids:
                processes = set()
                for deposition in record.preliminary_wps_id.weld_deposition_ids:
                    if deposition.welding_process_id:
                        processes.add(deposition.welding_process_id.code)
                record.welding_process_summary = ", ".join(sorted(processes)) if processes else ""
            else:
                record.welding_process_summary = ""

    @api.depends('preliminary_wps_id', 'preliminary_wps_id.material_ids')
    def _compute_materials_summary(self):
        for record in self:
            if record.preliminary_wps_id and record.preliminary_wps_id.material_ids:
                materials = [material.name for material in record.preliminary_wps_id.material_ids]
                record.materials_summary = ", ".join(sorted(materials)) if materials else ""
            else:
                record.materials_summary = ""

    @api.depends('preliminary_wps_id')
    def generate_name(self):
        for record in self:
            record.name = f"WPQR.{str(record.id).zfill(6)}"

    @api.depends('name', 'name_secondary', 'preliminary_wps_id', 'preliminary_wps_id.weld_deposition_ids', 'preliminary_wps_id.weld_deposition_ids.welding_process_id')
    def _compute_name_summary(self):
        for record in self:
            name = record.name or ''
            name_secondary = record.name_secondary or ''

            # Get process codes
            process_codes = set()
            if record.preliminary_wps_id and record.preliminary_wps_id.weld_deposition_ids:
                for deposition in record.preliminary_wps_id.weld_deposition_ids:
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

