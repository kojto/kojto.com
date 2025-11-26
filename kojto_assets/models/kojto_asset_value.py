# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
import pytz


class KojtoAssetValue(models.Model):
    _name = "kojto.asset.value"
    _description = "Asset Value"

    asset_id = fields.Many2one("kojto.assets", string="Asset", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    datetime_start = fields.Datetime(string="From", default=lambda self: self.get_utc_from_local(8).replace(tzinfo=None), required=True)
    value = fields.Float(string="Value", digits=(18, 2), required=True)
    comment = fields.Char(string="Comment")

    @api.model
    def get_utc_from_local(self, hour):
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)
        local_time = utc_now.astimezone(user_timezone).replace(hour=hour, minute=0, second=0, microsecond=0)
        return local_time.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def create(self, vals):
        # Handle both single record creation and bulk creation
        if isinstance(vals, list):
            # Bulk creation - use super directly
            return super(KojtoAssetValue, self).create(vals)

        # Single record creation
        datetime_start = fields.Datetime.from_string(vals.get("datetime_start"))
        datetime_end = fields.Datetime.from_string(vals.get("datetime_end"))

        if datetime_start and datetime_end:
            # Convert to naive datetime before creating records
            start_dt = datetime_start.replace(tzinfo=None)
            end_dt = datetime_end.replace(tzinfo=None)

            user_tz = self.env.user.tz or "UTC"
            user_timezone = pytz.timezone(user_tz)
            start_local = user_timezone.localize(start_dt)
            end_local = user_timezone.localize(end_dt)

            if start_local.date() != end_local.date():
                records = []
                current_start = start_local
                while current_start.date() < end_local.date():
                    next_day_start = user_timezone.localize(
                        datetime.combine(
                            current_start.date() + timedelta(days=1),
                            datetime.min.time(),
                        )
                    )
                    current_end = min(next_day_start - timedelta(microseconds=1), end_local)
                    # Convert back to naive datetime for stores
                    current_start_utc = current_start.astimezone(pytz.utc).replace(tzinfo=None)
                    current_end_utc = current_end.astimezone(pytz.utc).replace(tzinfo=None)
                    records.append(
                        {
                            **vals,
                            "datetime_start": fields.Datetime.to_string(current_start_utc),
                            "datetime_end": fields.Datetime.to_string(current_end_utc),
                        }
                    )
                    current_start = next_day_start

                if current_start < end_local:
                    records.append(
                        {
                            **vals,
                            "datetime_start": fields.Datetime.to_string(current_start.astimezone(pytz.utc).replace(tzinfo=None)),
                            "datetime_end": fields.Datetime.to_string(end_dt),
                        }
                    )
                # Use super to create all records at once
                return super(KojtoAssetValue, self).create(records)

        # Ensure the datetimes are naive before creating a single record
        if "datetime_start" in vals:
            vals["datetime_start"] = fields.Datetime.to_string(datetime_start.replace(tzinfo=None))
        if "datetime_end" in vals:
            vals["datetime_end"] = fields.Datetime.to_string(datetime_end.replace(tzinfo=None))

        return super(KojtoAssetValue, self).create(vals)
