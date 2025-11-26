from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class KojtoBaseMaterialGrades(models.Model):
    _name = "kojto.base.material.grades"
    _description = "Material Grades"
    _rec_name = "name"
    _order = "name asc"
    _sql_constraints = [('name_uniq', 'unique(name)', 'Material grade name must be unique!')]

    density = fields.Float("Density kg/m3")
    name = fields.Char("Name", required=True)

    # Material group according to ISO 15608:2017
    material_grade_type = fields.Selection([
        # Steels (Groups 1-11)
        ('group_1_1', '1.1 - Unalloyed low carbon steels (ReH ≤ 275 N/mm², C ≤ 0.25%)'),
        ('group_1_2', '1.2 - Low carbon steels (275 < ReH ≤ 360 N/mm², C ≤ 0.25%)'),
        ('group_1_3', '1.3 - Normalized fine-grain steels (ReH > 360 N/mm², C ≤ 0.25%)'),
        ('group_1_4', '1.4 - Weathering steels'),
        ('group_2_1', '2.1 - Thermomechanically treated fine-grain steels (360 < ReH ≤ 460 N/mm²)'),
        ('group_2_2', '2.2 - Thermomechanically treated fine-grain steels (ReH > 460 N/mm²)'),
        ('group_3_1', '3.1 - Quenched and tempered steels'),
        ('group_5_1', '5.1 - Creep-resistant steels (1Cr ½Mo)'),
        ('group_5_2', '5.2 - Creep-resistant steels (2¼Cr 1Mo)'),
        ('group_6_4', '6.4 - High-temperature creep-resistant steels (Vanadium-alloyed)'),
        ('group_7', '7 - Ferritic/martensitic and precipitation-hardened steels'),
        ('group_8_1', '8.1 - Austenitic stainless steels (Cr ≤ 19%, Ni ≤ 35%)'),
        ('group_10_1', '10.1 - Duplex stainless steels (Cr ≤ 24%, Ni > 4%)'),
        ('group_11_1', '11.1 - High carbon steels (0.30% < C ≤ 0.85%)'),

        # Aluminium and Aluminium Alloys (Groups 21-26)
        ('group_21', '21 - Pure aluminium (≤ 1% impurities)'),
        ('group_22_1', '22.1 - Non-heat-treatable Al-Mn alloys'),
        ('group_22_4', '22.4 - Non-heat-treatable Al-Mg alloys (Mg > 3.5%)'),
        ('group_23_1', '23.1 - Heat-treatable Al-Mg-Si alloys'),
        ('group_24', '24 - Cast aluminium alloys (Al-Si)'),
        ('group_25', '25 - Cast aluminium alloys (Al-Cu)'),
        ('group_26', '26 - Other cast aluminium alloys'),

        # Cast Irons (Groups 71-76)
        ('group_71', '71 - Grey cast irons'),
        ('group_72_1', '72.1 - Spheroidal graphite cast irons (ferritic)'),
        ('group_72_2', '72.2 - Spheroidal graphite cast irons (ferritic-pearlitic)'),
        ('group_72_3', '72.3 - Spheroidal graphite cast irons (pearlitic)'),
        ('group_72_4', '72.4 - Spheroidal graphite cast irons (bainitic)'),
        ('group_73', '73 - Malleable cast irons'),
        ('group_74', '74 - White cast irons'),
        ('group_75', '75 - Compacted graphite cast irons'),
        ('group_76', '76 - Other cast irons'),

        ('other', 'Other')
    ], string='Material Grade Type (ISO 15608)', required=True, default='group_1_1')
    description = fields.Text("Description")

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("A material grade with name '%s' already exists.") % record.name)
