from odoo import models, fields

class KojtoBaseBanks(models.Model):
    _name = "kojto.base.banks"
    _description = "Kojto Banks"
    _rec_name = "name"
    _order = "name desc"

    name = fields.Char(string="Bank Name", required=True)
    address = fields.Char(string="Address")
    BAE = fields.Char(string="BAE Code")
    BIC = fields.Char(string="BIC Code")
    branch_bic = fields.Char(string="Branch BIC")
    branch_name = fields.Char(string="Branch Name")
    city = fields.Char(string="City")
    country = fields.Char(string="Country")
    email = fields.Char(string="Email")
    fax = fields.Char(string="Fax")
    fin = fields.Char(string="FIN")
    phone = fields.Char(string="Phone")
    score_fileact_real_time = fields.Char(string="SCORE FileAct Real Time")
    score_fileact_store_forward = fields.Char(string="SCORE FileAct Store & Forward")
    state = fields.Char(string="Region")
    website = fields.Char(string="Website")
    zip_code = fields.Char(string="Postal Code")
