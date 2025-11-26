from odoo import models, fields

class KojtoBaseImages(models.Model):
    _name = "kojto.base.images"
    _description = "Kojto Base Images"
    _rec_name = "name"
    _order = "name desc"

    image = fields.Binary(string="Image File", attachment=True)
    name = fields.Char(string="Name")
    datetime_taken = fields.Datetime(string="DateTime Taken")
    face_encoding = fields.Text(string="Face Encoding (JSON)")
