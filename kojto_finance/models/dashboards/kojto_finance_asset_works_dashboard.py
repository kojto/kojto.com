# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api

class KojtoFinanceAssetWorksDashboard(models.Model):
    _name = 'kojto.finance.asset.works.dashboard'
    _description = 'Finance Asset Works Dashboard'
    _auto = False
    _order = 'year desc, quarter desc, month desc'

    year = fields.Char(string='Year (YYYY)', readonly=True)
    quarter = fields.Char(string='Quarter (YYYY-QN)', readonly=True)
    month = fields.Char(string='Month (YYYY-MM)', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', readonly=True)
    asset_works_total = fields.Float(string='Asset Works Total', digits=(16, 2), readonly=True)
    asset_works_quantity = fields.Float(string='Asset Works Quantity', digits=(16, 2), readonly=True)

    @api.depends()
    def _compute_currency_id(self):
        """Compute currency_id based on the currency of contact with ID 1
        Note: currency id 26 is BGN, currency id 125 is EUR
        If currency is different from BGN or EUR, set to EUR (125)"""
        contact = self.env['kojto.contacts'].browse(1)
        currency_id = contact.currency_id.id if contact.exists() and contact.currency_id else False

        # If currency is different from BGN (26) or EUR (125), set to EUR (125)
        if currency_id not in [26, 125]:
            currency_id = 125

        for record in self:
            record.currency_id = currency_id

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY TO_CHAR(w.datetime_start, 'YYYY-MM') DESC) as id,
                    EXTRACT(YEAR FROM TO_DATE(TO_CHAR(w.datetime_start, 'YYYY-MM'), 'YYYY-MM')) as year,
                    EXTRACT(YEAR FROM TO_DATE(TO_CHAR(w.datetime_start, 'YYYY-MM'), 'YYYY-MM')) || '-Q' || EXTRACT(QUARTER FROM TO_DATE(TO_CHAR(w.datetime_start, 'YYYY-MM'), 'YYYY-MM')) as quarter,
                    TO_CHAR(w.datetime_start, 'YYYY-MM') as month,
                    COALESCE(SUM(
                        CASE
                            WHEN target_currency.currency_id = 26 THEN w."value_in_BGN"
                            ELSE w."value_in_EUR"
                        END
                    ), 0) as asset_works_total,
                    COALESCE(SUM(w.quantity), 0) as asset_works_quantity
                FROM kojto_asset_works w
                CROSS JOIN (
                    SELECT
                        CASE
                            WHEN contact_currency.id = 26 THEN 26  -- BGN
                            ELSE 125  -- EUR (default)
                        END as currency_id,
                        CASE
                            WHEN contact_currency.id = 26 THEN 'BGN'
                            ELSE 'EUR'
                        END as currency_name
                    FROM (
                        SELECT COALESCE(c.currency_id, 125) as id
                        FROM kojto_contacts c
                        WHERE c.id = 1
                    ) contact_currency
                ) target_currency
                WHERE w.datetime_start IS NOT NULL
                    AND w.quantity > 0
                GROUP BY TO_CHAR(w.datetime_start, 'YYYY-MM'), target_currency.currency_id
                ORDER BY TO_CHAR(w.datetime_start, 'YYYY-MM') DESC
            )
        ''')
