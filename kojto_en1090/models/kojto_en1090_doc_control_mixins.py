from odoo import models, fields, api

class VTControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.vt.mixin"
    _description = "Visual Testing Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_vt_control"

    # VT Specific Fields
    observation_angle = fields.Char(string="Observation Angle (°)", default="45-60")
    distance = fields.Char(string="Distance (mm)", default="250")
    vt_acceptance_level = fields.Selection(
        [
            ('b', 'B'),
            ('c', 'C'),
            ('d', 'D')
        ],
        string="VT Acceptance Level", default='b'
    )
    vt_methods_of_testing = fields.Selection(
        [
            ('direct', 'VT - Direct Method'),
            ('indirect', 'VT - Indirect Method')
        ],
        string="VT Methods of Testing", default='direct'
    )
    vt_acceptance_standard = fields.Selection(
        [
            ('iso_5817', 'Steel - EN ISO 5817'),
            ('iso_10042', 'Aluminium - EN ISO 10042')  # Corrected
        ],
        string="VT Acceptance Standard", default='iso_5817'
    )
    vt_procedure_standard = fields.Selection(
        [
            ('iso_17637', 'EN ISO 17637')
        ],
        string="VT Procedure Standard", default='iso_17637',
        help="Standard for visual testing procedures."
    )

    def copy(self, default=None):
        """Copy VT specific fields."""
        default = dict(default or {})
        default.update({
            'observation_angle': self.observation_angle,
            'distance': self.distance,
            'vt_acceptance_level': self.vt_acceptance_level,
            'vt_methods_of_testing': self.vt_methods_of_testing,
            'vt_procedure_standard': self.vt_procedure_standard,
        })
        return super().copy(default)

class RTControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.rt.mixin"
    _description = "Radiographic Testing Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_rt_control"

    # RT Specific Fields
    radiation_source_type = fields.Char(string="Radiation Source Type", default="X-ray")
    radiation_source_activity = fields.Float(string="Radiation Source Activity", default=100)
    radiation_source_energy = fields.Float(string="Radiation Source Energy", default=100)
    exposure_time = fields.Float(string="Exposure Time", default=1)
    kv_value = fields.Float(string="KV Value", default=100)
    ma_value = fields.Float(string="MA Value", default=100)
    focal_spot_size = fields.Float(string="Focal Spot Size", default=1)
    source_to_film_distance = fields.Float(string="Source to Film Distance", default=1)
    film_to_object_distance = fields.Float(string="Film to Object Distance", default=1)
    film_type = fields.Char(string="Film Type", default="Type 1")
    film_grade = fields.Char(string="Film Grade", default="Grade 1")
    film_size = fields.Char(string="Film Size", default="100x100")
    intensifying_screens = fields.Char(string="Intensifying Screens", default="1")
    film_processing = fields.Char(string="Film Processing", default="Processing 1")
    image_quality_indicator = fields.Char(string="Image Quality Indicator", default="1")
    sensitivity = fields.Char(string="Sensitivity", default="1")
    density = fields.Char(string="Density", default="1")
    contrast = fields.Char(string="Contrast", default="1")
    unsharpness = fields.Char(string="Unsharpness", default="1")
    geometric_magnification = fields.Float(string="Geometric Magnification", default=1)
    radiation_angle = fields.Float(string="Radiation Angle", default=1)
    radiation_direction = fields.Char(string="Radiation Direction", default="1")

    rt_acceptance_level = fields.Selection(
        [
            ('b', 'B (Stringent)'),
            ('c', 'C (Intermediate)'),
            ('d', 'D (Moderate)')
        ],
        string="RT Acceptance Level", default='b'
    )
    rt_methods_of_testing = fields.Selection(
        [
            ('xray', 'RT - X-ray'),
            ('gamma', 'RT - Gamma')
        ],
        string="RT Methods of Testing", default='xray'
    )
    rt_acceptance_standard = fields.Selection(
        [
            ('iso_5817', 'Steel - EN ISO 5817'),
            ('iso_10042', 'Aluminium - EN ISO 10042')
        ],
        string="RT Acceptance Standard", default='iso_5817'
    )
    rt_procedure_standard = fields.Selection(
        [
            ('iso_17636_1', 'EN ISO 17636-1'),
            ('iso_17636_2', 'EN ISO 17636-2')
        ],
        string="RT Procedure Standard", default='iso_17636_1',
        help="Standards for radiographic testing procedures (film-based or digital)."
    )

    def copy(self, default=None):
        """Copy RT specific fields."""
        default = dict(default or {})
        default.update({
            'radiation_source_type': self.radiation_source_type,
            'radiation_source_activity': self.radiation_source_activity,
            'radiation_source_energy': self.radiation_source_energy,
            'exposure_time': self.exposure_time,
            'kv_value': self.kv_value,
            'ma_value': self.ma_value,
            'focal_spot_size': self.focal_spot_size,
            'source_to_film_distance': self.source_to_film_distance,
            'film_to_object_distance': self.film_to_object_distance,
            'film_type': self.film_type,
            'film_grade': self.film_grade,
            'film_size': self.film_size,
            'intensifying_screens': self.intensifying_screens,
            'film_processing': self.film_processing,
            'image_quality_indicator': self.image_quality_indicator,
            'sensitivity': self.sensitivity,
            'density': self.density,
            'contrast': self.contrast,
            'unsharpness': self.unsharpness,
            'geometric_magnification': self.geometric_magnification,
            'radiation_angle': self.radiation_angle,
            'radiation_direction': self.radiation_direction,
            'rt_acceptance_level': self.rt_acceptance_level,
            'rt_methods_of_testing': self.rt_methods_of_testing,
            'rt_procedure_standard': self.rt_procedure_standard,
        })
        return super().copy(default)

class MTControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.mt.mixin"
    _description = "Magnetic Particle Testing Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_mt_control"

    mt_acceptance_level = fields.Selection(
        [
            ('b', 'B (Stringent)'),
            ('c', 'C (Intermediate)')
        ],
        string="MT Acceptance Level", default='b'  # Corrected
    )
    mt_acceptance_standard = fields.Selection(
        [
            ('iso_5817', 'Steel - EN ISO 5817')
        ],
        string="MT Acceptance Standard", default='iso_5817'
    )
    mt_methods_of_testing = fields.Selection(
        [
            ('contrast', 'MT - Contrast Base'),
            ('uv', 'MT - UV Lamp')
        ],
        string="MT Methods of Testing", default='contrast'
    )
    mt_procedure_standard = fields.Selection(
        [
            ('iso_23278', 'EN ISO 23278')
        ],
        string="MT Procedure Standard", default='iso_23278',
        help="Standard for magnetic particle testing procedures."
    )

    def copy(self, default=None):
        """Copy MT specific fields."""
        default = dict(default or {})
        default.update({
            'mt_acceptance_level': self.mt_acceptance_level,
            'mt_methods_of_testing': self.mt_methods_of_testing,
            'mt_procedure_standard': self.mt_procedure_standard,
        })
        return super().copy(default)

class PTControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.pt.mixin"
    _description = "Penetrant Testing Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_pt_control"

    pt_acceptance_level = fields.Selection(
        [
            ('1', 'Level 1 (Stringent)'),
            ('2', 'Level 2 (Less Stringent)')
        ],
        string="PT Acceptance Level", default='1'
    )
    pt_acceptance_standard = fields.Selection(
        [
            ('iso_5817', 'Steel - EN ISO 5817'),
            ('iso_10042', 'Aluminium - EN ISO 10042')  # Corrected
        ],
        string="PT Acceptance Standard", default='iso_5817'
    )
    pt_methods_of_testing = fields.Selection(
        [
            ('method_a', 'PT - Method A (Visible Penetrant)'),
            ('method_b', 'PT - Method B (Fluorescent Penetrant)'),
            ('method_c', 'PT - Method C (Water Washable)'),
            ('method_d', 'PT - Method D (Post-Emulsifiable, Lipophilic)'),
            ('method_e', 'PT - Method E (Solvent Removable)'),
            ('method_f', 'PT - Method F (Post-Emulsifiable, Hydrophilic)')
        ],
        string="PT Methods of Testing", default='method_a'  # Corrected
    )
    pt_procedure_standard = fields.Selection(
        [
            ('iso_23277', 'EN ISO 23277')
        ],
        string="PT Procedure Standard", default='iso_23277',
        help="Standard for penetrant testing procedures."
    )

    def copy(self, default=None):
        """Copy PT specific fields."""
        default = dict(default or {})
        default.update({
            'pt_acceptance_level': self.pt_acceptance_level,
            'pt_methods_of_testing': self.pt_methods_of_testing,
            'pt_procedure_standard': self.pt_procedure_standard,
        })
        return super().copy(default)

class UTControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.ut.mixin"
    _description = "Ultrasonic Testing Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_ut_control"

    # UT Specific Fields
    sector = fields.Char(string="Sector", default="0-1")
    diameter = fields.Char(string="Diameter (mm)", default="0")
    wall_thickness = fields.Char(string="Wall Thickness (mm)", default="0")
    scheme = fields.Char(string="Scheme", default="A4")
    position = fields.Char(string="Position", default="B,X,Y,D,E,C,F,G")
    probe = fields.Char(string="Probe", default="1,2,3,4")
    area_of_scanning_from = fields.Float(string="Area of Scanning From", default=0.0)
    area_of_scanning_to = fields.Float(string="Area of Scanning To", default=290.0)
    type_of_defect = fields.Char(string="Type of Defect", default="No defects")
    axis_x = fields.Float(string="Axis X", default=0.0)
    axis_lx = fields.Float(string="Axis Lx", default=0.0)
    axis_y = fields.Float(string="Axis Y", default=0.0)
    axis_ly = fields.Float(string="Axis Ly", default=0.0)
    axis_z = fields.Float(string="Axis Z", default=0.0)
    axis_lz = fields.Float(string="Axis Lz", default=0.0)
    amplitude = fields.Float(string="Amplitude", default=0.0)

    ut_acceptance_level = fields.Selection(
        [
            ('1', 'Level 1 (Stringent)'),
            ('2', 'Level 2 (Less Stringent)')
        ],
        string="UT Acceptance Level", default='1'
    )
    ut_acceptance_standard = fields.Selection(
        [
            ('iso_5817', 'Steel - EN ISO 5817'),
            ('iso_10042', 'Aluminium - EN ISO 10042'),
            ('iso_11666', 'UT Levels - EN ISO 11666')
        ],
        string="UT Acceptance Standard", default='iso_5817'
    )
    ut_methods_of_testing = fields.Selection(
        [
            ('contact', 'UT - Contact Method'),
            ('immersion', 'UT - Immersion Method')
        ],
        string="UT Methods of Testing", default='contact'  # Corrected
    )
    ut_procedure_standard = fields.Selection(
        [
            ('iso_17640', 'EN ISO 17640')
        ],
        string="UT Procedure Standard", default='iso_17640',
        help="Standard for ultrasonic testing procedures."
    )

    def copy(self, default=None):
        """Copy UT specific fields."""
        default = dict(default or {})
        default.update({
            'sector': self.sector,
            'diameter': self.diameter,
            'wall_thickness': self.wall_thickness,
            'scheme': self.scheme,
            'position': self.position,
            'probe': self.probe,
            'area_of_scanning_from': self.area_of_scanning_from,
            'area_of_scanning_to': self.area_of_scanning_to,
            'type_of_defect': self.type_of_defect,
            'axis_x': self.axis_x,
            'axis_lx': self.axis_lx,
            'axis_y': self.axis_y,
            'axis_ly': self.axis_ly,
            'axis_z': self.axis_z,
            'axis_lz': self.axis_lz,
            'amplitude': self.amplitude,
            'ut_acceptance_level': self.ut_acceptance_level,
            'ut_methods_of_testing': self.ut_methods_of_testing,
            'ut_procedure_standard': self.ut_procedure_standard,
        })
        return super().copy(default)  # Corrected

class CLControlMixin(models.AbstractModel):
    _name = "kojto.en1090.doc.control.cl.mixin"
    _description = "Check List Control Mixin"

    _report_ref = "kojto_en1090.report_kojto_en1090_doc_cl_control"

    cl_acceptance_level = fields.Selection(
        [
            ('1', 'Quantity'),
            ('2', 'Quality'),
            ('3', 'Quality and Quantity')
        ],
        string="CL Acceptance Level", default='1',
    )

