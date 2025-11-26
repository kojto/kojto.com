from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.compute_material_properties_table_html import compute_material_properties_table_html
import random
import string


class KojtoDeliveryInspectionCertificates(models.Model):
    _name = 'kojto.delivery.inspection.certificates'
    _description = 'Delivery Inspection Certificates'
    _order = 'name desc'
    _inherit = ["kojto.library.printable"]
    _sql_constraints = [('unique_name', 'unique(name)', 'The Name must be unique!'),]

    # Reports config for printing
    _report_ref = "kojto_deliveries.report_kojto_delivery_inspection_certificate"
    _report_css_ref = "kojto_pdf_main_document_header.css"

    date_issue = fields.Date(string="Issue Date", required=True, default=fields.Date.today)
    language_id = fields.Many2one('res.lang', string='Language', default=lambda self: self.env['res.lang']._lang_get(self.env.user.lang))
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF attachment")

    # Basic Information
    name = fields.Char(string='Name', required=True, compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    certificate_type = fields.Selection([
        ('2.1', 'EN 10204 2.1'),
        ('2.2', 'EN 10204 2.2'),
        ('3.1', 'EN 10204 3.1'),
        ('3.2', 'EN 10204 3.2')], string='Certificate Type', required=True, default='3.1')

    # Relationships
    delivery_id = fields.Many2one('kojto.deliveries', string='Delivery', required=True)
    subcode_id = fields.Many2one(related='delivery_id.subcode_id', string='Subcode', store=True)

    # Company Information (Manufacturer) - Related from delivery
    company_name_id = fields.Many2one(related='delivery_id.company_name_id', string='Manufacturer Name', store=True)
    company_address_id = fields.Many2one(related='delivery_id.company_address_id', string='Manufacturer Address', store=True)
    company_phone_id = fields.Many2one(related='delivery_id.company_phone_id', string='Manufacturer Phone', store=True)
    company_email_id = fields.Many2one(related='delivery_id.company_email_id', string='Manufacturer Email', store=True)

    # Counterparty Information (Customer) - Related from delivery
    counterparty_name_id = fields.Many2one(related='delivery_id.counterparty_name_id', string='Customer Name', store=True)
    counterparty_address_id = fields.Many2one(related='delivery_id.counterparty_address_id', string='Customer Address', store=True)
    counterparty_phone_id = fields.Many2one(related='delivery_id.counterparty_phone_id', string='Customer Phone', store=True)
    counterparty_email_id = fields.Many2one(related='delivery_id.counterparty_email_id', string='Customer Email', store=True)

    # Product Information
    product_name = fields.Char(string='Product Name', required=True, default='Products of steel')
    product_standard = fields.Char(string='Product Standard', default='БДС EN 1090')
    dimensional_tolerance_standard = fields.Selection([
        ('en_10025', 'EN 10025 - Hot rolled products of structural steels'),
        ('en_10028', 'EN 10028 - Flat products for pressure purposes'),
        ('en_10029', 'EN 10029 - Hot-rolled steel plates'),
        ('en_10034', 'EN 10034 - Hot rolled I and H sections'),
        ('en_10048', 'EN 10048 - Hot rolled narrow strips'),
        ('en_10051', 'EN 10051 - Continuously hot-rolled strip and plate'),
        ('en_10055', 'EN 10055 - Hot rolled equal flange tees'),
        ('en_10056', 'EN 10056 - Structural steel equal and unequal angles'),
        ('en_10058', 'EN 10058 - Hot rolled flat bars'),
        ('en_10059', 'EN 10059 - Hot rolled square bars'),
        ('en_10060', 'EN 10060 - Hot rolled round bars'),
        ('en_10210', 'EN 10210 - Hot finished structural hollow sections'),
        ('en_10219', 'EN 10219 - Cold formed welded structural hollow sections'),
        ('en_10279', 'EN 10279 - Hot rolled Z sections'),
        ('en_10297', 'EN 10297 - Seamless circular tubes'),
        ('en_10305', 'EN 10305 - Precision steel tubes'),
        ('en_1090', 'EN 1090 - Execution of steel structures'),
        ('astm_a1123', 'ASTM A1123/A1123M - Sharp cornerd profiles'),
    ], string='Tolerance Standard', default='en_1090', required=True)
    execution_type = fields.Selection([
        ('laser_welded', 'Laser Welded'),
        ('mig_mag_welded', 'MIG/MAG Welded'),
        ('milled', 'Milled'),
        ('extruded', 'Extruded'),
        ('other', 'Other'),
    ], string='Execution Type', default='laser_welded', required=True)

    material_grade_id = fields.Many2one('kojto.base.material.grades', string='Material Grade')
    material_grade_type = fields.Selection(related='material_grade_id.material_grade_type', string='Material Grade Type', readonly=True)

    # Order Information
    net_weight = fields.Float(string='Net Weight (kg)', digits=(10, 3))
    batch_ids = fields.Many2many('kojto.warehouses.batches', relation='delivery_insp_cert_batches_rel', string='Batches', required=True, context={'active_test': False})

    # Additional Information
    additional_notes = fields.Text(string='Additional Notes')
    material_properties_table = fields.Html(string='Material Properties Table', compute='_compute_material_properties_table')

    @api.constrains('net_weight')
    def _check_net_weight(self):
        for record in self:
            if record.net_weight < 0:
                raise ValidationError(_('Net weight cannot be negative.'))

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if self.search_count([('name', '=', rec.name)]) > 1:
                raise ValidationError(_('The Name must be unique!'))

    def print_document(self):
        """Print the delivery inspection certificate document."""
        self.ensure_one()
        return self.print_document_as_pdf()

    def _compute_name(self):
        for record in self:
            if not record.name:
                while True:
                    generated = f"{''.join(random.choices(string.ascii_uppercase, k=2))}{''.join(random.choices(string.digits, k=6))}"
                    if not self.search_count([('name', '=', generated)]):
                        record.name = generated
                        break

    @api.depends('batch_ids', 'batch_ids.batch_properties_ids')
    def _compute_material_properties_table(self):
        for record in self:
            record.material_properties_table = compute_material_properties_table_html(record.batch_ids)
