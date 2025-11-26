# -*- coding: utf-8 -*-
from odoo import models, fields


class KojtoContactEmails(models.Model):
    _inherit = "kojto.base.emails"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactPhones(models.Model):
    _inherit = "kojto.base.phones"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactNames(models.Model):
    _inherit = "kojto.base.names"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactAddresses(models.Model):
    _inherit = "kojto.base.addresses"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactBankAccounts(models.Model):
    _inherit = "kojto.base.bank.accounts"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactTaxNumbers(models.Model):
    _inherit = "kojto.base.tax.numbers"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")


class KojtoContactCertificates(models.Model):
    _inherit = "kojto.base.certificates"

    contact_id = fields.Many2one("kojto.contacts", string="Contact", ondelete="cascade")
