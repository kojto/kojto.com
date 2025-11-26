# kojto_technical_docs/models/kojto_technical_docs.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoTechnicalDocs(models.Model):
    _name = "kojto.technical.docs"
    _description = "Technical Documents"
    _rec_name = "name"

    active = fields.Boolean(default=True, string="Active")
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)

    name = fields.Char(string="Technical Document Number", required=True)
    technical_document_type_id = fields.Many2one("kojto.technical.doc.types", string="Technical Document Type", required=True)
    description = fields.Text(string="Description")
    revision_ids = fields.One2many("kojto.technical.doc.revisions", "technical_document_id", string="Revisions")

    @api.constrains('name', 'subcode_id')
    def _check_unique_technical_document_name(self):
        for record in self:
            if record.name and record.subcode_id:
                existing = self.search([
                    ('name', '=', record.name),
                    ('subcode_id', '=', record.subcode_id.id),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("Technical Document Number must be unique within the subcode. Document '%s' already exists in subcode '%s'.") % (record.name, record.subcode_id.name))

    @api.model
    def create(self, vals):
        record = super(KojtoTechnicalDocs, self).create(vals)
        self.env['kojto.technical.doc.revisions'].create({
            'technical_document_id': record.id,
            'description': record.description or '',
        })
        return record

