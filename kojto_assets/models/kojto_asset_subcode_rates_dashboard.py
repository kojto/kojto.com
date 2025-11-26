"""
Kojto Asset Subcode Rates Dashboard Model

Purpose:
--------
Dashboard view that shows active assets with their latest subcode rates,
including subcode, currency, rate, and unit information.
"""

from odoo import models, fields, tools


class KojtoAssetSubcodeRatesDashboard(models.Model):
    _name = "kojto.asset.subcode.rates.dashboard"
    _description = "Kojto Asset Subcode Rates Dashboard"
    _auto = False  # This is a database view

    asset_id = fields.Many2one("kojto.assets", string="Asset", readonly=True)
    asset_name = fields.Char(string="Asset Name", readonly=True)
    asset_description = fields.Char(string="Asset Description", readonly=True)
    unit_id = fields.Many2one("kojto.base.units", string="Unit", readonly=True)
    unit_name = fields.Char(string="Unit Name", readonly=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", readonly=True)
    subcode_name = fields.Char(string="Subcode Name", readonly=True)
    datetime_start = fields.Datetime(string="Valid From", readonly=True)
    rate = fields.Float(string="Rate", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    currency_symbol = fields.Char(string="Currency Symbol", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT DISTINCT ON (a.id, asr.subcode_id)
                    asr.id,
                    a.id as asset_id,
                    a.name as asset_name,
                    a.description as asset_description,
                    a.unit_id,
                    u.name as unit_name,
                    asr.subcode_id,
                    sc.name as subcode_name,
                    asr.datetime_start,
                    asr.rate,
                    asr.currency_id,
                    c.symbol as currency_symbol
                FROM kojto_assets a
                INNER JOIN kojto_asset_subcode_rates asr ON a.id = asr.asset_id
                INNER JOIN kojto_commission_subcodes sc ON asr.subcode_id = sc.id
                INNER JOIN res_currency c ON asr.currency_id = c.id
                LEFT JOIN kojto_base_units u ON a.unit_id = u.id
                WHERE a.active = true
                ORDER BY a.id, asr.subcode_id, asr.datetime_start DESC
            )
        """ % self._table)
