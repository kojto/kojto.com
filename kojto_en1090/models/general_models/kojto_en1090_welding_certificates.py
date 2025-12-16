from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError
import uuid

class KojtoEn1090WeldingCertificates(models.Model):
    _name = "kojto.en1090.welding.certificates"
    _description = "EN1090 Welding Certificates"
    _order = "name"
    _sql_constraints = [('name_uniq', 'unique(name)', 'Certificate name must be unique!'),]

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    include_document_in_bundle = fields.Boolean(string="Include Document in Bundle", default=True)

    description = fields.Text(string="Description")
    certificate_type = fields.Selection([
        ('welding', 'Welding Certificate'),
        ('inspection', 'Inspection Certificate'),
        ('welding_engineer', 'Welding Engineer Certificate'),
        ('en1090_certificate', 'EN1090 Certificate'),
        ('equipment_certificate', 'Equipment Certificate'),
        ('other', 'Other')
    ], string="Certificate Type", required=True, default='inspection')
    issuing_authority_id = fields.Many2one("kojto.contacts", string="Issuing Authority")
    date_start = fields.Date(string="Issue Date", required=True)
    date_end = fields.Date(string="Expiry Date")
    certificate_number = fields.Char(string="Certificate Number")
    specialist_id = fields.Many2one("kojto.en1090.welding.specialists", string="Specialist")
    equipment_id = fields.Many2one("kojto.en1090.equipment", string="Equipment")
    company_id = fields.Many2one("kojto.contacts", string="Company", default=1)
    attachment_id = fields.Many2many("ir.attachment", string="Attachment", domain="[('res_model', '=', 'kojto.en1090.welding.certificates'), ('res_id', '=', id), ('mimetype', '=', 'application/pdf')]")

    @api.constrains('attachment_id')
    def _check_single_pdf_attachment(self):
        for record in self:
            if len(record.attachment_id) > 1:
                raise ValidationError(_("Only one PDF attachment is allowed per certificate."))

