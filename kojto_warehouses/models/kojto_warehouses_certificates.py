# kojto_warehouses/models/kojto_warehouses_certificates.py
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class KojtoWarehousesCertificates(models.Model):
    _name = "kojto.warehouses.certificates"
    _description = "Warehouse Certificates"
    _rec_name = "name"
    _order = "date_issued desc"

    name = fields.Char("Name", required=True)
    counterparty_id = fields.Many2one(related="batch_id.counterparty_id", string="Manufacturer", help="Manufacturer of the batch")
    date_issued = fields.Date(string="Date Issued", default=fields.Date.today)
    standard = fields.Char("Standard")
    certificate_type = fields.Selection([
        ("certificate", "Certificate"),
        ("conformity", "Declaration of Conformity"),
        ("supplier", "Supplier Declaration"),
        ("test", "Test Report"),
        ("surface", "Surface Defects")], string="Type", required=True, default="certificate")
    description = fields.Char("Description")
    attachment_id = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.warehouses.certificates'), ('res_id', '=', id), ('mimetype', '=', 'application/pdf')]")

    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", required=True)
    inspection_report_ids = fields.Many2many('kojto.warehouses.inspection.report', compute='_compute_inspection_report_ids')

    @api.depends('batch_id')
    def _compute_inspection_report_ids(self):
        for record in self:
            if record.batch_id:
                record.inspection_report_ids = record.batch_id.inspection_report_ids
            else:
                record.inspection_report_ids = [(5, 0, 0)]

    @api.constrains('attachment_id')
    def _check_single_pdf_attachment(self):
        for record in self:
            if len(record.attachment_id) > 1:
                raise ValidationError(_("Only one PDF attachment is allowed per certificate."))

    @api.constrains('attachment_id')
    def _check_single_pdf_attachment(self):
        for record in self:
            if len(record.attachment_id) > 1:
                raise ValidationError(_("Only one PDF attachment is allowed per certificate."))
