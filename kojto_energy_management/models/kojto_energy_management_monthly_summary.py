# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from datetime import datetime
import calendar


class KojtoEnergyManagementMonthlySummary(models.Model):
    _name = 'kojto.energy.management.monthly.summary'
    _description = 'Energy Management Monthly Summary'
    _order = 'year desc, month desc, power_meter_id'
    _rec_name = 'display_name'
    _auto = False  # This is a database view

    # Basic Information
    power_meter_id = fields.Many2one('kojto.energy.management.devices', string='Power Meter', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    month = fields.Integer(string='Month', readonly=True)
    display_name = fields.Char(string='Summary', compute='_compute_display_name', store=False)

    # Currency for monetary fields
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    # Period Information
    period_start = fields.Date(string='Period Start', compute='_compute_period_dates', store=False)
    period_end = fields.Date(string='Period End', compute='_compute_period_dates', store=False)

    # Energy Consumption (MWh) - Sum of differences
    total_imported_mwh = fields.Float(string='Imported (MWh)', digits=(16, 3), readonly=True)
    total_exported_mwh = fields.Float(string='Exported (MWh)', digits=(16, 3), readonly=True)

    # Energy Values - Sum of monetary values
    total_imported_value = fields.Float(string='Imported', digits=(16, 2), readonly=True)
    total_exported_value = fields.Float(string='Exported', digits=(16, 2), readonly=True)

    # Counter Readings - Start and End of Period
    counter_imported_start = fields.Float(string='Import Counter Start (MWh)', digits=(16, 3), readonly=True)
    counter_imported_end = fields.Float(string='Import Counter End (MWh)', digits=(16, 3), readonly=True)
    counter_exported_start = fields.Float(string='Export Counter Start (MWh)', digits=(16, 3), readonly=True)
    counter_exported_end = fields.Float(string='Export Counter End (MWh)', digits=(16, 3), readonly=True)

    # Statistics
    reading_count = fields.Integer(string='Reading Count', readonly=True)
    avg_power_kw = fields.Float(string='Average Power (kW)', digits=(16, 3), readonly=True)

    def init(self):
        """Create the database view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY power_meter_id,
                        year DESC,
                        month DESC
                    ) AS id,
                    power_meter_id,
                    year,
                    month,
                    (SELECT id FROM res_currency WHERE name = 'EUR' LIMIT 1) AS currency_id,
                    SUM(imported_kwh) / 1000.0 AS total_imported_mwh,
                    SUM(exported_kwh) / 1000.0 AS total_exported_mwh,
                    SUM(imported_kwh_value) AS total_imported_value,
                    SUM(exported_kwh_value) AS total_exported_value,
                    MAX(counter_imported_start) AS counter_imported_start,
                    MAX(counter_exported_start) AS counter_exported_start,
                    MAX(counter_imported_end) AS counter_imported_end,
                    MAX(counter_exported_end) AS counter_exported_end,
                    COUNT(*) AS reading_count,
                    AVG(p_kw) AS avg_power_kw
                FROM (
                    SELECT
                        pmr.power_meter_id,
                        EXTRACT(YEAR FROM pmr.datetime_utc)::integer AS year,
                        EXTRACT(MONTH FROM pmr.datetime_utc)::integer AS month,
                        pmr.imported_kwh,
                        pmr.exported_kwh,
                        pmr.imported_kwh_value,
                        pmr.exported_kwh_value,
                        pmr.p_kw,
                        FIRST_VALUE(pmr.imported_kwh_counter) OVER (
                            PARTITION BY pmr.power_meter_id,
                            EXTRACT(YEAR FROM pmr.datetime_utc),
                            EXTRACT(MONTH FROM pmr.datetime_utc)
                            ORDER BY pmr.datetime_utc ASC
                        ) / 1000.0 AS counter_imported_start,
                        FIRST_VALUE(pmr.exported_kwh_counter) OVER (
                            PARTITION BY pmr.power_meter_id,
                            EXTRACT(YEAR FROM pmr.datetime_utc),
                            EXTRACT(MONTH FROM pmr.datetime_utc)
                            ORDER BY pmr.datetime_utc ASC
                        ) / 1000.0 AS counter_exported_start,
                        LAST_VALUE(pmr.imported_kwh_counter) OVER (
                            PARTITION BY pmr.power_meter_id,
                            EXTRACT(YEAR FROM pmr.datetime_utc),
                            EXTRACT(MONTH FROM pmr.datetime_utc)
                            ORDER BY pmr.datetime_utc ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        ) / 1000.0 AS counter_imported_end,
                        LAST_VALUE(pmr.exported_kwh_counter) OVER (
                            PARTITION BY pmr.power_meter_id,
                            EXTRACT(YEAR FROM pmr.datetime_utc),
                            EXTRACT(MONTH FROM pmr.datetime_utc)
                            ORDER BY pmr.datetime_utc ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        ) / 1000.0 AS counter_exported_end
                    FROM kojto_energy_management_power_meter_readings pmr
                    JOIN kojto_energy_management_devices d
                        ON d.id = pmr.power_meter_id AND d.active = TRUE
                    WHERE pmr.power_meter_id IS NOT NULL
                ) sub
                GROUP BY
                    power_meter_id,
                    year,
                    month
                ORDER BY
                    power_meter_id,
                    year DESC,
                    month DESC
            )
        """ % self._table)

    @api.depends('power_meter_id', 'year', 'month')
    def _compute_display_name(self):
        """Compute display name for the summary"""
        for record in self:
            month_name = calendar.month_name[record.month] if record.month else ''
            record.display_name = f"{record.power_meter_id.name} - {month_name} {record.year}"

    @api.depends('year', 'month')
    def _compute_period_dates(self):
        """Compute period start and end dates"""
        for record in self:
            if record.year and record.month:
                # First day of the month
                record.period_start = datetime(record.year, record.month, 1).date()
                # Last day of the month
                last_day = calendar.monthrange(record.year, record.month)[1]
                record.period_end = datetime(record.year, record.month, last_day).date()
            else:
                record.period_start = False
                record.period_end = False

    def action_view_readings(self):
        """View the actual readings for this monthly summary"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Readings for {self.display_name}',
            'res_model': 'kojto.energy.management.power.meter.readings',
            'view_mode': 'list,form',
            'domain': [
                ('power_meter_id', '=', self.power_meter_id.id),
                ('datetime_utc', '>=', self.period_start.strftime('%Y-%m-%d 00:00:00')),
                ('datetime_utc', '<=', self.period_end.strftime('%Y-%m-%d 23:59:59'))
            ],
            'context': {'search_default_filter_this_month': 1}
        }

    def name_get(self):
        """Custom name_get to show summary information"""
        result = []
        for record in self:
            name = f"{record.power_meter_id.name} - {calendar.month_name[record.month]} {record.year}"
            result.append((record.id, name))
        return result
