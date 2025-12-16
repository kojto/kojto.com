from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class KojtoEn1090Equipment(models.Model):
    _name = "kojto.en1090.equipment"
    _description = "Equipment for EN1090 Controls"
    _order = "name"

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Equipment name must be unique!')
    ]

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    code = fields.Char(string="Code")
    equipment_type = fields.Selection([
        ('ut', 'Ultrasonic Testing'),
        ('vt', 'Visual Testing'),
        ('mt', 'Magnetic Particle Testing'),
        ('pt', 'Penetrant Testing'),
        ('rt', 'Radiographic Testing'),
        ('welding', 'Welding Equipment'),
        ('general', 'General Equipment'),
        ('welding_material', 'Welding Material'),
        ('other', 'Other')

    ], string="Type", required=True)
    manufacturer = fields.Char(string="Manufacturer")
    model = fields.Char(string="Model")
    serial_number = fields.Char(string="Serial Number")
    calibration_date = fields.Date(string="Last Calibration Date")
    next_calibration_date = fields.Date(string="Next Calibration Date")
    description = fields.Text(string="Description")

    # Computed fields for backward compatibility
    is_ut_device = fields.Boolean(string="UT Device", compute="_compute_device_type_flags", store=True)
    is_vt_device = fields.Boolean(string="VT Device", compute="_compute_device_type_flags", store=True)
    is_mt_device = fields.Boolean(string="MT Device", compute="_compute_device_type_flags", store=True)
    is_pt_device = fields.Boolean(string="PT Device", compute="_compute_device_type_flags", store=True)
    is_rt_device = fields.Boolean(string="RT Device", compute="_compute_device_type_flags", store=True)
    is_welding_equipment = fields.Boolean(string="Welding Equipment", compute="_compute_device_type_flags", store=True)
    is_general_equipment = fields.Boolean(string="General Equipment", compute="_compute_device_type_flags", store=True)

    # Relations
    welding_certificates_ids = fields.One2many('kojto.en1090.welding.certificates', 'equipment_id', string="Certificates")
    welding_specialists_ids = fields.Many2many('kojto.en1090.welding.specialists', string="Assigned Specialists", relation='kojto_en1090_specialist_equipment_rel')

    @api.depends('equipment_type')
    def _compute_device_type_flags(self):
        for record in self:
            record.is_ut_device = record.equipment_type == 'ut'
            record.is_vt_device = record.equipment_type == 'vt'
            record.is_mt_device = record.equipment_type == 'mt'
            record.is_pt_device = record.equipment_type == 'pt'
            record.is_rt_device = record.equipment_type == 'rt'
            record.is_welding_equipment = record.equipment_type == 'welding'
            record.is_general_equipment = record.equipment_type == 'general'

    @api.constrains('equipment_type')
    def _check_equipment_type(self):
        for record in self:
            if not record.equipment_type:
                raise ValidationError(_("Equipment type is required."))

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|',
                     ('name', operator, name),
                     ('description', operator, name)]
        return self.search(domain + args, limit=limit).name_get()

    def name_get(self):
        result = []
        for record in self:
            # Get the display value for equipment_type
            type_display = dict(self._fields['equipment_type'].selection).get(record.equipment_type, '')
            name = f"{record.name} ({type_display})"
            if record.model:
                name += f" - {record.model}"
            result.append((record.id, name))
        return result
