from odoo import models, fields


class KojtoDeliveries(models.Model):
    _inherit = 'kojto.delivery.contents'

    technical_document_revision_id = fields.Many2one(
        "kojto.technical.doc.revisions",
        string="Technical Doc Revision"
    )
