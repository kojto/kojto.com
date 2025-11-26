"""
Kojto Technical Document Types Model

Purpose:
--------
Defines the model for technical document types, which categorize
technical documents in the system.
"""

from odoo import models, fields


class KojtoTechnicalDocTypes(models.Model):
    _name = "kojto.technical.doc.types"
    _description = "Technical Document Types"
    _rec_name = "technical_document_type_name"

    technical_document_type_name = fields.Char(string="Technical doc type name", required=True)
