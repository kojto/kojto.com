# -*- coding: utf-8 -*-
from odoo import models, fields


class KojtoContactsCreditLimit(models.Model):
    _name = "kojto.contacts.credit.limit"
    _description = "Credit Limits for Kojto Contacts"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", required=True, ondelete="cascade")
    credit_limit = fields.Float(string="Credit Limit", default=0.0)
    datetime_start = fields.Datetime(string="Start Date", required=True, default=fields.Datetime.now)
    datetime_end = fields.Datetime(string="End Date")
    attachment = fields.Binary(string="Attachment")
    insured_by = fields.Char(string="Insured by")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.EUR").id, required=True)
