#/opt/odoo18/custom_addons/kojto_energy_management/models/kojto_energy_management_prices.py
# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoEnergyManagementPrices(models.Model):
    _name = 'kojto.energy.management.prices'
    _description = 'Energy Management Prices'
    _order = 'period_start_cet desc'
    _rec_name = 'id'

    _sql_constraints = [
        ('unique_period_exchange', 'UNIQUE(period_start_cet, exchange)',
         'A price record for this period and exchange already exists!'),
    ]

    # Period fields in CET (stored as text to preserve exact time from CSV)
    period_start_cet = fields.Char(string='Period Start (CET)', size=19, help='Start of the period in Central European Time (YYYY-MM-DD HH:MM:SS) as char field')
    period_end_cet = fields.Char(string='Period End (CET)', size=19, help='End of the period in Central European Time (YYYY-MM-DD HH:MM:SS) as char field')

    # Period fields in UTC
    period_start_utc = fields.Datetime(string='Period Start', help='Start of the period in UTC shown in local time zone by odoo')
    period_end_utc = fields.Datetime(string='Period End', help='End of the period in UTC shown in local time zone by odoo')

    # Price fields
    price_bgn_per_mwh = fields.Float(string='Price BGN per MWh', digits=(16, 2), help='Energy price in Bulgarian Lev per MWh')
    price_eur_per_mwh = fields.Float(string='Price EUR per MWh', digits=(16, 2), help='Energy price in Euro per MWh')

    # Volume field
    volume_mwh = fields.Float(string='Volume (MWh)', digits=(16, 3), help='Energy volume in Megawatt-hours')

    # Exchange field
    exchange = fields.Char(string='Exchange', size=25, default='IBEX', help='Energy exchange name (e.g., IBEX)')

    # Computed display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)



    @api.depends('period_start_cet', 'exchange')
    def _compute_display_name(self):
        for record in self:
            if record.period_start_cet and record.exchange:
                record.display_name = f"{record.exchange} - {record.period_start_cet}"
            elif record.period_start_cet:
                record.display_name = str(record.period_start_cet)
            elif record.exchange:
                record.display_name = record.exchange
            else:
                record.display_name = f"Energy Price #{record.id}"

    @api.constrains('period_start_cet', 'exchange')
    def _check_unique_period_exchange(self):
        """Check that period_start_cet and exchange combination is unique"""
        for record in self:
            if record.period_start_cet and record.exchange:
                # Search for existing records with same period_start_cet and exchange
                domain = [
                    ('period_start_cet', '=', record.period_start_cet),
                    ('exchange', '=', record.exchange),
                    ('id', '!=', record.id)  # Exclude current record
                ]
                existing = self.search(domain, limit=1)
                if existing:
                    raise ValidationError(
                        f'A price record for period "{record.period_start_cet}" '
                        f'and exchange "{record.exchange}" already exists! '
                        f'(Record ID: {existing.id})'
                    )

    @api.constrains('period_start_cet', 'period_end_cet')
    def _check_period_cet(self):
        for record in self:
            if record.period_start_cet and record.period_end_cet:
                if record.period_start_cet >= record.period_end_cet:
                    raise ValidationError('Period Start (CET) must be before Period End (CET)')

    @api.constrains('period_start_utc', 'period_end_utc')
    def _check_period_utc(self):
        for record in self:
            if record.period_start_utc and record.period_end_utc:
                if record.period_start_utc >= record.period_end_utc:
                    raise ValidationError('Period Start (UTC) must be before Period End (UTC)')

    def cron_import_ibex_prices(self):
        """
        Scheduled action to import IBEX prices
        NOTE: This method is kept for compatibility but does nothing.
        IBEX price import is now handled by a Linux cron job.
        See: management_machine_scripts/cron_import_ibex_prices.sh
        """
        # IBEX import is handled by external cron job
        pass

