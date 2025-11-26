# -*- coding: utf-8 -*-
from odoo import models, fields


class KojtoContactsPosition(models.Model):
    _name = "kojto.contacts.positions"
    _description = "Relationship between Person and Company"

    person_id = fields.Many2one("kojto.contacts", string="Person", domain=[("contact_type", "=", "person")], context={"default_contact_type": "person"})
    company_id = fields.Many2one("kojto.contacts", string="Company", domain=[("contact_type", "=", "company")], context={"default_contact_type": "company"})
    position = fields.Char(string="Position")
