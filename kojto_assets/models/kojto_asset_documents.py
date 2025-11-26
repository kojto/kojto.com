# -*- coding: utf-8 -*-
from odoo import models, fields


class KojtoAssetDocuments(models.Model):
    _name = "kojto.asset.documents"
    _description = "Asset Documents"

    name = fields.Char(string="Name", required=True)
    asset_id = fields.Many2one("kojto.assets", string="Asset", required=True)
    description = fields.Text(string="Description")
    document = fields.Binary(string="Document")
