from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo import Command
from ..utils.kojto_en1090_name_generator import generate_document_name, WELDING_SEAM_PREFIX


class KojtoEn1090WeldingSeams(models.Model):
    _name = "kojto.en1090.welding.seams"
    _description = "Welding Seams"
    _order = "consequtive_number"

    _sql_constraints = [('name_unique', 'UNIQUE(name)', 'Seam name must be unique.'),]

    name = fields.Char("Name", compute="generate_name", store=True, copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True, readonly=True)
    welding_task_id = fields.Many2one("kojto.en1090.doc.welding.tasks", string="Welding Task", required=True)

    # Seam Details
    applicable_wps_id = fields.Many2one("kojto.en1090.wps", string="Applicable WPS", required=True, help="The specific welding procedure specification to be used")
    consequtive_number = fields.Char(string="Nr.", required=True)
    seam_length = fields.Float(string="Length (mm)", digits=(10, 2), required=True)
    seam_thickness = fields.Float(string="Thickness (mm)", digits=(10, 2), required=True)

    # Execution Information
    welder_id = fields.Many2one("kojto.en1090.welding.specialists", string="Welder", domain=[("is_certified_welder", "=", True)], required=True)
    checked_by_id = fields.Many2one("kojto.en1090.welding.specialists", string="Checked By")
    description = fields.Char(string="Description")

    @api.depends("welding_task_id.document_bundle_id")
    def generate_name(self):
        for record in self:
            if record.welding_task_id and record.welding_task_id.document_bundle_id:
                record.name = generate_document_name(record, record.welding_task_id.document_bundle_id, WELDING_SEAM_PREFIX)
            else:
                record.name = False

    # Validation
    @api.constrains('seam_length', 'seam_thickness')
    def _check_dimensions(self):
        for record in self:
            if record.seam_length and record.seam_length <= 0:
                raise ValidationError(_("Seam length must be greater than zero."))
            if record.seam_thickness and record.seam_thickness <= 0:
                raise ValidationError(_("Seam thickness must be greater than zero."))

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("A seam with name '%s' already exists.") % record.name)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'welding_task_id' in fields_list and self._context.get('default_welding_task_id'):
            res['welding_task_id'] = self._context['default_welding_task_id']
        return res
