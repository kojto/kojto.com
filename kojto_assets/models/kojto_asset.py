# -*- coding: utf-8 -*- just a test
from odoo import models, fields, api


class KojtoAssets(models.Model):
    _name = "kojto.assets"
    _description = "Asset Management"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_assets.report_kojto_assets"

    name = fields.Char(string="Asset Name")
    active = fields.Boolean(string="Is Active", default=True)

    description = fields.Char(string="Description")
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    language_id = fields.Many2one("res.lang", string="Language", default=10, required=True)
    pdf_attachment_id = fields.Many2one('ir.attachment', string="PDF Attachment", copy=False)
    values = fields.One2many("kojto.asset.value", "asset_id", string="Value")
    subcode_rates = fields.One2many("kojto.asset.subcode.rates", "asset_id", string="Subcode Rate")
    maintenances = fields.One2many("kojto.asset.maintenance", "asset_id", string="Maintenance")
    attachments = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        domain="[('res_model', '=', 'kojto.assets'), ('res_id', '=', id)]",
    )
    repr_attachments = fields.Char(string="Attachments", compute="compute_single_attachment")

    @api.depends("attachments")
    def compute_single_attachment(self):
        for record in self:
            if not record.attachments:
                record.repr_attachments = ""
                continue

            sorted_attachments = record.attachments.sorted(key=lambda r: r.id)
            if len(sorted_attachments) > 1:
                record.repr_attachments = f"{sorted_attachments[0].name} + {len(sorted_attachments) - 1} more"
            else:
                record.repr_attachments = sorted_attachments[0].name
        return {}

    def print_asset(self):
        self.ensure_one()
        return self.print_document_as_pdf()
