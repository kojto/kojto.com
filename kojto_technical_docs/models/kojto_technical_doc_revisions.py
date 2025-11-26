from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class KojtoTechnicalDocRevisions(models.Model):
    _name = "kojto.technical.doc.revisions"
    _description = "Technical Doc Revisions"
    _rec_name = "name"

    name = fields.Char(string="Name", compute='compute_name', store=True, readonly=True)
    description = fields.Char(string="Description")
    technical_document_id = fields.Many2one('kojto.technical.docs', string="Technical Doc ID", required=True)
    technical_document_revision = fields.Integer(string="Technical Doc Revision", compute='_compute_technical_document_revision', store=True, readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', 'kojto_technical_doc_revision_attachment_rel', 'revision_id', 'attachment_id', string='Attachments', help='Attachments for this technical document revision.')


    @api.depends('technical_document_id')
    def _compute_technical_document_revision(self):
        for record in self:
            if record.technical_document_id:
                if record.id:
                    # Count existing records for this technical document to get revision
                    existing_count = self.search_count([
                        ('technical_document_id', '=', record.technical_document_id.id),
                        ('id', '<=', record.id)
                    ])
                    record.technical_document_revision = existing_count
                else:
                    # For new records, count existing ones + 1
                    existing_count = self.search_count([
                        ('technical_document_id', '=', record.technical_document_id.id)
                    ])
                    record.technical_document_revision = existing_count + 1
            else:
                record.technical_document_revision = 0

    @api.depends('technical_document_id', 'technical_document_id.subcode_id', 'technical_document_id.name')
    def compute_name(self):
        for record in self:
            if record.technical_document_id and record.technical_document_id.subcode_id:
                subcode_name = record.technical_document_id.subcode_id.name
            else:
                subcode_name = 'undefined_subcode'

            if record.technical_document_id and record.technical_document_id.name:
                tech_doc_name = record.technical_document_id.name
            else:
                tech_doc_name = 'undefined_doc'

            # For new records, we'll use the ID to determine the revision
            # This avoids the circular dependency issue
            if record.id:
                # Count existing records for this technical document to get revision
                existing_count = self.search_count([
                    ('technical_document_id', '=', record.technical_document_id.id),
                    ('id', '<=', record.id)
                ])
                revision = existing_count
            else:
                # For new records, count existing ones + 1
                existing_count = self.search_count([
                    ('technical_document_id', '=', record.technical_document_id.id)
                ])
                revision = existing_count + 1

            # Format revision as _00, _01, _02, etc.
            formatted_revision = f"_{revision:02d}"

            record.name = f"{subcode_name}.{tech_doc_name}{formatted_revision}"
