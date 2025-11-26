# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import pytz


class KojtoAssetWorks(models.Model):
    _name = "kojto.asset.works"
    _description = "Asset Works"

    asset_id = fields.Many2one("kojto.assets", string="Asset", required=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode ID", required=True)
    datetime_start = fields.Datetime(string="From", default=lambda self: self.get_utc_from_local(8), required=True)
    datetime_end = fields.Datetime(string="To", default=lambda self: self.get_utc_from_local(17), required=True)
    comment = fields.Char(string="Comment")
    quantity = fields.Float(string="Quantity", required=True)

    credited_subcode_id = fields.Many2one("kojto.commission.subcodes", string="Credited Subcode", compute="_compute_credited_subcode_id", store=True)
    value_in_BGN = fields.Float(string="Value in BGN", digits=(12, 2), compute="_compute_value_in_BGN", store=True)
    value_in_EUR = fields.Float(string="Value in EUR", digits=(12, 2), compute="_compute_value_in_EUR", store=True)

    @api.depends("quantity", "subcode_id", "asset_id", "datetime_start")
    def _compute_credited_subcode_id(self):
        for record in self:
            if not record.quantity or not record.subcode_id or not record.asset_id:
                record.credited_subcode_id = False
                continue

            # Get the asset's subcode rate for this asset and date only (ignore subcode_id filter)
            subcode_rate = self.env['kojto.asset.subcode.rates'].search([
                ('asset_id', '=', record.asset_id.id),
                ('datetime_start', '<=', record.datetime_start),
            ], order='datetime_start desc', limit=1)

            if subcode_rate:
                record.credited_subcode_id = subcode_rate.subcode_id
            else:
                record.credited_subcode_id = False

    @api.depends("quantity", "subcode_id", "asset_id", "datetime_start")
    def _compute_value_in_BGN(self):
        for record in self:
            if not record.quantity or not record.subcode_id or not record.asset_id:
                record.value_in_BGN = 0.0
                continue

            # Get the asset's subcode rate for this asset and date only (ignore subcode_id filter)
            subcode_rate = self.env['kojto.asset.subcode.rates'].search([
                ('asset_id', '=', record.asset_id.id),
                ('datetime_start', '<=', record.datetime_start),
            ], order='datetime_start desc', limit=1)

            if subcode_rate:
                record.value_in_BGN = record.quantity * subcode_rate.rate_in_BGN
            else:
                record.value_in_BGN = 0.0

    @api.depends("quantity", "subcode_id", "asset_id", "datetime_start")
    def _compute_value_in_EUR(self):
        for record in self:
            if not record.quantity or not record.subcode_id or not record.asset_id:
                record.value_in_EUR = 0.0
                continue

            # Get the asset's subcode rate for this asset and date only (ignore subcode_id filter)
            subcode_rate = self.env['kojto.asset.subcode.rates'].search([
                ('asset_id', '=', record.asset_id.id),
                ('datetime_start', '<=', record.datetime_start),
            ], order='datetime_start desc', limit=1)

            if subcode_rate:
                record.value_in_EUR = record.quantity * subcode_rate.rate_in_EUR
            else:
                record.value_in_EUR = 0.0

    def get_utc_from_local(self, hour):
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)
        local_time = utc_now.astimezone(user_timezone).replace(hour=hour, minute=0, second=0, microsecond=0)
        return local_time.astimezone(pytz.utc).replace(tzinfo=None)

    def compute_value_in_BGN_and_EUR_batch(self):
        """
        Compute value_in_BGN, value_in_EUR, and credited_subcode_id for the current asset works records.
        This method bypasses the write validation for previous months.
        """
        for record in self:
            if not record.quantity or not record.subcode_id or not record.asset_id:
                value_in_BGN = 0.0
                value_in_EUR = 0.0
                credited_subcode_id = None
            else:
                # Get the asset's subcode rate for this asset and date only (ignore subcode_id filter)
                subcode_rate = self.env['kojto.asset.subcode.rates'].search([
                    ('asset_id', '=', record.asset_id.id),
                    ('datetime_start', '<=', record.datetime_start),
                ], order='datetime_start desc', limit=1)

                if subcode_rate:
                    value_in_BGN = record.quantity * subcode_rate.rate_in_BGN
                    value_in_EUR = record.quantity * subcode_rate.rate_in_EUR
                    credited_subcode_id = subcode_rate.subcode_id.id
                else:
                    value_in_BGN = 0.0
                    value_in_EUR = 0.0
                    credited_subcode_id = None

            # Update value_in_BGN, value_in_EUR, and credited_subcode_id fields directly in the database to bypass validation
            if credited_subcode_id is not None:
                self.env.cr.execute(
                    "UPDATE kojto_asset_works SET value_in_BGN = %s, value_in_EUR = %s, credited_subcode_id = %s WHERE id = %s",
                    (value_in_BGN, value_in_EUR, credited_subcode_id, record.id)
                )
            else:
                self.env.cr.execute(
                    "UPDATE kojto_asset_works SET value_in_BGN = %s, value_in_EUR = %s, credited_subcode_id = NULL WHERE id = %s",
                    (value_in_BGN, value_in_EUR, record.id)
                )
