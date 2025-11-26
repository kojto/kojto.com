# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import pytz


class KojtoAssetSubcodeRates(models.Model):
    _name = "kojto.asset.subcode.rates"
    _description = "Kojto Asset Subcode Rates"
    _order = "datetime_start desc"

    asset_id = fields.Integer(string="Asset ID", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    datetime_start = fields.Datetime(string="From", default=lambda self: self.get_utc_from_local(8), required=True)
    rate = fields.Float(string="Rate", digits="Account")
    rate_in_BGN = fields.Float(string="Rate in BGN", digits=(12, 2), compute="_compute_rate_in_BGN", store=True)
    rate_in_EUR = fields.Float(string="Rate in EUR", digits=(12, 2), compute="_compute_rate_in_EUR", store=True)

    @api.depends("rate", "currency_id", "datetime_start")
    def _compute_rate_in_BGN(self):
        for record in self:
            if not record.rate or not record.currency_id:
                record.rate_in_BGN = 0.0
                continue

            # Get BGN currency
            bgn_currency = self.env['res.currency'].search([('name', '=', 'BGN')], limit=1)
            if not bgn_currency:
                record.rate_in_BGN = 0.0
                continue

            # If currency is already BGN, return the same value
            if record.currency_id.id == bgn_currency.id:
                record.rate_in_BGN = record.rate
                continue

            # If currency is EUR, use hardcoded rate
            if record.currency_id.name == 'EUR':
                record.rate_in_BGN = record.rate * 1.95583
                continue

            # For other currencies, try to get exchange rate from kojto.base.currency.exchange
            exchange_rate = 0.0
            if record.datetime_start:
                # Try direct rate first
                exchange_record = self.env['kojto.base.currency.exchange'].search([
                    ('base_currency_id', '=', record.currency_id.id),
                    ('target_currency_id', '=', bgn_currency.id),
                    ('datetime', '<=', record.datetime_start),
                ], order='datetime desc', limit=1)

                if exchange_record:
                    exchange_rate = exchange_record.exchange_rate
                else:
                    # Try reverse rate
                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                        ('base_currency_id', '=', bgn_currency.id),
                        ('target_currency_id', '=', record.currency_id.id),
                        ('datetime', '<=', record.datetime_start),
                    ], order='datetime desc', limit=1)

                    if exchange_record and exchange_record.exchange_rate > 0:
                        exchange_rate = 1.0 / exchange_record.exchange_rate
                    else:
                        # If no rate found for the specific date, try most recent rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', bgn_currency.id),
                        ], order='datetime desc', limit=1)

                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try most recent reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', bgn_currency.id),
                                ('target_currency_id', '=', record.currency_id.id),
                            ], order='datetime desc', limit=1)

                            if exchange_record and exchange_record.exchange_rate > 0:
                                exchange_rate = 1.0 / exchange_record.exchange_rate

            record.rate_in_BGN = record.rate * exchange_rate if exchange_rate > 0 else 0.0

    @api.depends("rate", "currency_id", "datetime_start")
    def _compute_rate_in_EUR(self):
        for record in self:
            if not record.rate or not record.currency_id:
                record.rate_in_EUR = 0.0
                continue

            # Get EUR currency
            eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)
            if not eur_currency:
                record.rate_in_EUR = 0.0
                continue

            # If currency is already EUR, return the same value
            if record.currency_id.id == eur_currency.id:
                record.rate_in_EUR = record.rate
                continue

            # If currency is BGN, use hardcoded rate
            if record.currency_id.name == 'BGN':
                record.rate_in_EUR = record.rate * (1.0 / 1.95583)
                continue

            # For other currencies, try to get exchange rate from kojto.base.currency.exchange
            exchange_rate = 0.0
            if record.datetime_start:
                # Try direct rate first
                exchange_record = self.env['kojto.base.currency.exchange'].search([
                    ('base_currency_id', '=', record.currency_id.id),
                    ('target_currency_id', '=', eur_currency.id),
                    ('datetime', '<=', record.datetime_start),
                ], order='datetime desc', limit=1)

                if exchange_record:
                    exchange_rate = exchange_record.exchange_rate
                else:
                    # Try reverse rate
                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                        ('base_currency_id', '=', eur_currency.id),
                        ('target_currency_id', '=', record.currency_id.id),
                        ('datetime', '<=', record.datetime_start),
                    ], order='datetime desc', limit=1)

                    if exchange_record and exchange_record.exchange_rate > 0:
                        exchange_rate = 1.0 / exchange_record.exchange_rate
                    else:
                        # If no rate found for the specific date, try most recent rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', eur_currency.id),
                        ], order='datetime desc', limit=1)

                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try most recent reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', eur_currency.id),
                                ('target_currency_id', '=', record.currency_id.id),
                            ], order='datetime desc', limit=1)

                            if exchange_record and exchange_record.exchange_rate > 0:
                                exchange_rate = 1.0 / exchange_record.exchange_rate

            record.rate_in_EUR = record.rate * exchange_rate if exchange_rate > 0 else 0.0

    def get_utc_from_local(self, hour):
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        user_tz = self.env.user.tz or "UTC"
        user_timezone = pytz.timezone(user_tz)
        local_time = utc_now.astimezone(user_timezone).replace(hour=hour, minute=0, second=0, microsecond=0)
        return local_time.astimezone(pytz.utc).replace(tzinfo=None)

    def recompute_rates_batch(self):
        """
        Force recompute rate_in_BGN and rate_in_EUR for the current records.
        Uses direct SQL updates for better performance, similar to employee subcode rates.
        """
        if not self:
            return {'message': 'No records to recompute'}

        # Get BGN and EUR currencies once
        bgn_currency = self.env['res.currency'].search([('name', '=', 'BGN')], limit=1)
        eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)

        if not bgn_currency or not eur_currency:
            return {'message': 'BGN or EUR currency not found'}

        bgn_id = bgn_currency.id
        eur_id = eur_currency.id

        # Compute values for all records
        for record in self:
            # Compute BGN rate
            if not record.rate or not record.currency_id:
                rate_in_BGN = 0.0
            else:
                if record.currency_id.id == bgn_id:
                    rate_in_BGN = record.rate
                elif record.currency_id.name == 'EUR':
                    rate_in_BGN = record.rate * 1.95583
                else:
                    # Get exchange rate
                    exchange_rate = 0.0
                    if record.datetime_start:
                        # Try direct rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', bgn_id),
                            ('datetime', '<=', record.datetime_start),
                        ], order='datetime desc', limit=1)
                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', bgn_id),
                                ('target_currency_id', '=', record.currency_id.id),
                                ('datetime', '<=', record.datetime_start),
                            ], order='datetime desc', limit=1)
                            if exchange_record and exchange_record.exchange_rate > 0:
                                exchange_rate = 1.0 / exchange_record.exchange_rate
                            else:
                                # Try most recent direct
                                exchange_record = self.env['kojto.base.currency.exchange'].search([
                                    ('base_currency_id', '=', record.currency_id.id),
                                    ('target_currency_id', '=', bgn_id),
                                ], order='datetime desc', limit=1)
                                if exchange_record:
                                    exchange_rate = exchange_record.exchange_rate
                                else:
                                    # Try most recent reverse
                                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                                        ('base_currency_id', '=', bgn_id),
                                        ('target_currency_id', '=', record.currency_id.id),
                                    ], order='datetime desc', limit=1)
                                    if exchange_record and exchange_record.exchange_rate > 0:
                                        exchange_rate = 1.0 / exchange_record.exchange_rate
                    rate_in_BGN = record.rate * exchange_rate if exchange_rate > 0 else 0.0

            # Compute EUR rate
            if not record.rate or not record.currency_id:
                rate_in_EUR = 0.0
            else:
                if record.currency_id.id == eur_id:
                    rate_in_EUR = record.rate
                elif record.currency_id.name == 'BGN':
                    rate_in_EUR = record.rate * (1.0 / 1.95583)
                else:
                    # Get exchange rate
                    exchange_rate = 0.0
                    if record.datetime_start:
                        # Try direct rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', eur_id),
                            ('datetime', '<=', record.datetime_start),
                        ], order='datetime desc', limit=1)
                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', eur_id),
                                ('target_currency_id', '=', record.currency_id.id),
                                ('datetime', '<=', record.datetime_start),
                            ], order='datetime desc', limit=1)
                            if exchange_record and exchange_record.exchange_rate > 0:
                                exchange_rate = 1.0 / exchange_record.exchange_rate
                            else:
                                # Try most recent direct
                                exchange_record = self.env['kojto.base.currency.exchange'].search([
                                    ('base_currency_id', '=', record.currency_id.id),
                                    ('target_currency_id', '=', eur_id),
                                ], order='datetime desc', limit=1)
                                if exchange_record:
                                    exchange_rate = exchange_record.exchange_rate
                                else:
                                    # Try most recent reverse
                                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                                        ('base_currency_id', '=', eur_id),
                                        ('target_currency_id', '=', record.currency_id.id),
                                    ], order='datetime desc', limit=1)
                                    if exchange_record and exchange_record.exchange_rate > 0:
                                        exchange_rate = 1.0 / exchange_record.exchange_rate
                    rate_in_EUR = record.rate * exchange_rate if exchange_rate > 0 else 0.0

            # Update directly in database using SQL (bypasses validation)
            self.env.cr.execute(
                'UPDATE kojto_asset_subcode_rates SET "rate_in_BGN" = %s, "rate_in_EUR" = %s WHERE id = %s',
                (rate_in_BGN, rate_in_EUR, record.id)
            )

        return {
            'message': f'Recomputed rate_in_BGN and rate_in_EUR for {len(self)} record(s)'
        }
