from odoo import models, fields, api


class KojtoEn1090WeldingSpecialists(models.Model):
    _name = "kojto.en1090.welding.specialists"
    _description = "Welding Specialists"
    _rec_name = "name"

    name = fields.Char(string="Name")

    active = fields.Boolean(string="Active", default=True)
    translation_ids = fields.One2many("kojto.en1090.translations", "specialist_id", string="Translations")

    contact_id = fields.Many2one("kojto.contacts", string="Contact")
    title = fields.Char(string="Title")
    welding_certificates_ids = fields.Many2many("kojto.en1090.welding.certificates", string="Welding Certificates", relation="kojto_en1090_specialist_certificates_rel", help="Certificates held by this specialist")
    equipment_ids = fields.Many2many("kojto.en1090.equipment", string="Equipment", relation="kojto_en1090_specialist_equipment_rel", help="Equipment assigned to this specialist")
    personal_stamp_number = fields.Char(string="Stamp Nr.")

    is_welding_engineer = fields.Boolean(string="IWE")
    is_ut_inspector = fields.Boolean(string="UT")
    is_vt_inspector = fields.Boolean(string="VT")
    is_pt_inspector = fields.Boolean(string="PT")
    is_rt_inspector = fields.Boolean(string="RT")
    is_mt_inspector = fields.Boolean(string="MT")
    is_certified_welder = fields.Boolean(string="Welder")
