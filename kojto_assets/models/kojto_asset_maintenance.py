# -*- coding: utf-8 -*-
from odoo import models, fields
from datetime import datetime
import pytz


class KojtoAssetMaintenance(models.Model):
    _name = "kojto.asset.maintenance"
    _description = "Asset Maintenance"

    asset_id = fields.Many2one("kojto.assets", string="Asset", required=True)
    datetime_start = fields.Datetime(string="From", default=lambda self: self.get_utc_from_local(8), required=True)
    datetime_end = fields.Datetime(string="To", default=lambda self: self.get_utc_from_local(17), required=True)
    description = fields.Char(string="Description")
    service_type = fields.Selection(string="Service Type", selection=[("maintenance", "Maintenance"), ("repair", "Repair"), ("checkup", "Checkup"),],)
    datetime_paid = fields.Datetime(string="Paid On")
    invoice_number = fields.Char(string="Invoice Number")
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.asset.maintenance'), ('res_id', '=', id)]",)

    def get_utc_from_local(self, hour):
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)
        local_time = utc_now.astimezone(user_timezone).replace(hour=hour, minute=0, second=0, microsecond=0)
        return local_time.astimezone(pytz.utc).replace(tzinfo=None)
