from odoo import models

class KojtoResLang(models.Model):
    _inherit = "res.lang"
    _rec_name = "iso_code"
