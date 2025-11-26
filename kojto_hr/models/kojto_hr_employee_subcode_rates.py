"""
Kojto HR Employee Subcode Rates Model

Purpose:
--------
Manages employee subcode rates, including hourly rates for different
subcodes and their validity periods.
"""

from datetime import datetime, timedelta

import pytz

from odoo import models, fields, api


class KojtoHrEmployeeSubcodeRates(models.Model):
    _name = "kojto.hr.employee.subcode.rates"
    _description = "Kojto HR Employee Subcode Rates"
    _order = "date_start desc"

    employee_id = fields.Integer(string="Employee ID", required=True, readonly=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode ID", required=True)
    hour_rate = fields.Float(string="Hour Rate", digits=(12, 2), required=True)
    date_start = fields.Date(string="Valid From", required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id.id, required=True)
    hour_rate_in_BGN = fields.Float(string="Rate in BGN", digits=(12, 2), compute="_compute_hour_rate_in_BGN", store=True)
    hour_rate_in_EUR = fields.Float(string="Rate in EUR", digits=(12, 2), compute="_compute_hour_rate_in_EUR", store=True)

    @api.depends("hour_rate", "currency_id", "date_start")
    def _compute_hour_rate_in_BGN(self):
        for record in self:
            if not record.hour_rate or not record.currency_id:
                record.hour_rate_in_BGN = 0.0
                continue

            # Get BGN currency
            bgn_currency = self.env['res.currency'].search([('name', '=', 'BGN')], limit=1)
            if not bgn_currency:
                record.hour_rate_in_BGN = 0.0
                continue

            # If currency is already BGN, return the same value
            if record.currency_id.id == bgn_currency.id:
                record.hour_rate_in_BGN = record.hour_rate
                continue

            # If currency is EUR, use hardcoded rate
            if record.currency_id.name == 'EUR':
                record.hour_rate_in_BGN = record.hour_rate * 1.95583
                continue

            # For other currencies, try to get exchange rate from kojto.base.currency.exchange
            exchange_rate = 0.0
            reference_dt = record._get_reference_datetime()
            if reference_dt:
                # Try direct rate first
                exchange_record = self.env['kojto.base.currency.exchange'].search([
                    ('base_currency_id', '=', record.currency_id.id),
                    ('target_currency_id', '=', bgn_currency.id),
                    ('datetime', '<=', reference_dt),
                ], order='datetime desc', limit=1)

                if exchange_record:
                    exchange_rate = exchange_record.exchange_rate
                else:
                    # Try reverse rate
                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                        ('base_currency_id', '=', bgn_currency.id),
                        ('target_currency_id', '=', record.currency_id.id),
                        ('datetime', '<=', reference_dt),
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

            record.hour_rate_in_BGN = record.hour_rate * exchange_rate if exchange_rate > 0 else 0.0

    @api.depends("hour_rate", "currency_id", "date_start")
    def _compute_hour_rate_in_EUR(self):
        for record in self:
            if not record.hour_rate or not record.currency_id:
                record.hour_rate_in_EUR = 0.0
                continue

            # Get EUR currency
            eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)
            if not eur_currency:
                record.hour_rate_in_EUR = 0.0
                continue

            # If currency is already EUR, return the same value
            if record.currency_id.id == eur_currency.id:
                record.hour_rate_in_EUR = record.hour_rate
                continue

            # If currency is BGN, use hardcoded rate
            if record.currency_id.name == 'BGN':
                record.hour_rate_in_EUR = record.hour_rate * (1.0 / 1.95583)
                continue

            # For other currencies, try to get exchange rate from kojto.base.currency.exchange
            exchange_rate = 0.0
            reference_dt = record._get_reference_datetime()
            if reference_dt:
                # Try direct rate first
                exchange_record = self.env['kojto.base.currency.exchange'].search([
                    ('base_currency_id', '=', record.currency_id.id),
                    ('target_currency_id', '=', eur_currency.id),
                    ('datetime', '<=', reference_dt),
                ], order='datetime desc', limit=1)

                if exchange_record:
                    exchange_rate = exchange_record.exchange_rate
                else:
                    # Try reverse rate
                    exchange_record = self.env['kojto.base.currency.exchange'].search([
                        ('base_currency_id', '=', eur_currency.id),
                        ('target_currency_id', '=', record.currency_id.id),
                        ('datetime', '<=', reference_dt),
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

            record.hour_rate_in_EUR = record.hour_rate * exchange_rate if exchange_rate > 0 else 0.0

    def recompute_hour_rates_batch(self):
        """
        Force recompute hour_rate_in_BGN and hour_rate_in_EUR for the current records.
        Uses direct SQL updates for better performance, similar to time tracking.
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
            if not record.hour_rate or not record.currency_id:
                hour_rate_in_BGN = 0.0
            else:
                if record.currency_id.id == bgn_id:
                    hour_rate_in_BGN = record.hour_rate
                elif record.currency_id.name == 'EUR':
                    hour_rate_in_BGN = record.hour_rate * 1.95583
                else:
                    # Get exchange rate
                    exchange_rate = 0.0
                    reference_dt = record._get_reference_datetime()
                    if reference_dt:
                        # Try direct rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', bgn_id),
                            ('datetime', '<=', reference_dt),
                        ], order='datetime desc', limit=1)
                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', bgn_id),
                                ('target_currency_id', '=', record.currency_id.id),
                                ('datetime', '<=', reference_dt),
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
                    hour_rate_in_BGN = record.hour_rate * exchange_rate if exchange_rate > 0 else 0.0

            # Compute EUR rate
            if not record.hour_rate or not record.currency_id:
                hour_rate_in_EUR = 0.0
            else:
                if record.currency_id.id == eur_id:
                    hour_rate_in_EUR = record.hour_rate
                elif record.currency_id.name == 'BGN':
                    hour_rate_in_EUR = record.hour_rate * (1.0 / 1.95583)
                else:
                    # Get exchange rate
                    exchange_rate = 0.0
                    reference_dt = record._get_reference_datetime()
                    if reference_dt:
                        # Try direct rate
                        exchange_record = self.env['kojto.base.currency.exchange'].search([
                            ('base_currency_id', '=', record.currency_id.id),
                            ('target_currency_id', '=', eur_id),
                            ('datetime', '<=', reference_dt),
                        ], order='datetime desc', limit=1)
                        if exchange_record:
                            exchange_rate = exchange_record.exchange_rate
                        else:
                            # Try reverse rate
                            exchange_record = self.env['kojto.base.currency.exchange'].search([
                                ('base_currency_id', '=', eur_id),
                                ('target_currency_id', '=', record.currency_id.id),
                                ('datetime', '<=', reference_dt),
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
                    hour_rate_in_EUR = record.hour_rate * exchange_rate if exchange_rate > 0 else 0.0

            # Update directly in database using SQL (bypasses validation like time tracking)
            self.env.cr.execute(
                'UPDATE kojto_hr_employee_subcode_rates SET "hour_rate_in_BGN" = %s, "hour_rate_in_EUR" = %s WHERE id = %s',
                (hour_rate_in_BGN, hour_rate_in_EUR, record.id)
            )

        return {
            'message': f'Recomputed hour_rate_in_BGN and hour_rate_in_EUR for {len(self)} record(s)'
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _recompute_related_time_tracking(self, employee_ids=None):
        """Recompute time tracking values whenever a rate changes."""
        if employee_ids is None:
            employee_ids = set(self.mapped("employee_id"))
        else:
            employee_ids = set(employee_ids)

        employee_ids = {emp_id for emp_id in employee_ids if emp_id}
        if not employee_ids:
            return

        time_tracking_records = self.env["kojto.hr.time.tracking"].search([
            ("employee_id", "in", list(employee_ids)),
        ])
        if time_tracking_records:
            time_tracking_records.compute_value_in_BGN_and_EUR_batch()

    def _get_reference_datetime(self):
        self.ensure_one()
        if self.date_start:
            base_dt = datetime.combine(self.date_start, datetime.min.time())
            return base_dt + timedelta(hours=12)
        return self.datetime_start

    # -------------------------------------------------------------------------
    # CRUD overrides
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        records = super().create(vals)
        records._recompute_related_time_tracking()
        return records

    def write(self, vals):
        affected_employee_ids = set(self.mapped("employee_id"))
        res = super().write(vals)
        affected_employee_ids.update(self.mapped("employee_id"))
        self._recompute_related_time_tracking(employee_ids=affected_employee_ids)
        return res

    def unlink(self):
        affected_employee_ids = set(self.mapped("employee_id"))
        res = super().unlink()
        if affected_employee_ids:
            self._recompute_related_time_tracking(employee_ids=affected_employee_ids)
        return res
