# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api

class KojtoFinanceCashflowDashboard(models.Model):
    _name = 'kojto.finance.cashflow.dashboard'
    _description = 'Finance Cash Flow Dashboard'
    _auto = False
    _order = 'year desc, quarter desc, month desc'

    year = fields.Char(string='Year (YYYY)', readonly=True)
    quarter = fields.Char(string='Quarter (YYYY-QN)', readonly=True)
    month = fields.Char(string='Month (YYYY-MM)', readonly=True)
    incoming_cash_flow = fields.Float(string='Incoming Cash Flow', digits=(16, 2), readonly=True)
    outgoing_cash_flow = fields.Float(string='Outgoing Cash Flow', digits=(16, 2), readonly=True)
    balance = fields.Float(string='Balance', digits=(16, 2), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY TO_CHAR(cf.date_value, 'YYYY-MM') DESC) as id,
                    TO_CHAR(cf.date_value, 'YYYY-MM') as period,
                    EXTRACT(YEAR FROM TO_DATE(TO_CHAR(cf.date_value, 'YYYY-MM'), 'YYYY-MM')) as year,
                    EXTRACT(YEAR FROM TO_DATE(TO_CHAR(cf.date_value, 'YYYY-MM'), 'YYYY-MM')) || '-Q' || EXTRACT(QUARTER FROM TO_DATE(TO_CHAR(cf.date_value, 'YYYY-MM'), 'YYYY-MM')) as quarter,
                    TO_CHAR(cf.date_value, 'YYYY-MM') as month,
                    COALESCE(SUM(CASE WHEN cf.transaction_direction = 'incoming' THEN cfa.amount * cf.exchange_rate_to_bgn ELSE 0 END), 0) as incoming_cash_flow,
                    COALESCE(SUM(CASE WHEN cf.transaction_direction = 'outgoing' THEN cfa.amount * cf.exchange_rate_to_bgn ELSE 0 END), 0) as outgoing_cash_flow,
                    COALESCE(SUM(CASE WHEN cf.transaction_direction = 'incoming' THEN cfa.amount * cf.exchange_rate_to_bgn ELSE 0 END), 0)
                    - COALESCE(SUM(CASE WHEN cf.transaction_direction = 'outgoing' THEN cfa.amount * cf.exchange_rate_to_bgn ELSE 0 END), 0) as balance
                FROM kojto_finance_cashflow cf
                INNER JOIN kojto_finance_cashflow_allocation cfa ON cf.id = cfa.transaction_id
                    WHERE cf.date_value IS NOT NULL
                    AND cfa.amount > 0
                    GROUP BY TO_CHAR(cf.date_value, 'YYYY-MM')
                    ORDER BY TO_CHAR(cf.date_value, 'YYYY-MM') DESC
            )
        ''')

    def _next_month_first(self):
        from datetime import datetime
        year, month = map(int, self.month.split('-'))
        if month == 12:
            return f'{year+1}-01-01'
        else:
            return f'{year}-{str(month+1).zfill(2)}-01'

    def action_incoming_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Incoming Cash Flow Allocations',
            'res_model': 'kojto.finance.cashflow.allocation',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_cashflow_allocation_list').id, 'list'), (False, 'form')],
            'domain': [
                ('transaction_id.date_value', '>=', f'{self.month}-01'),
                ('transaction_id.date_value', '<', self._next_month_first()),
                ('transaction_id.transaction_direction', '=', 'incoming'),
                ('amount', '>', 0),
            ],
            'target': 'current',
        }

    def action_outgoing_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Outgoing Cash Flow Allocations',
            'res_model': 'kojto.finance.cashflow.allocation',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_cashflow_allocation_list').id, 'list'), (False, 'form')],
            'domain': [
                ('transaction_id.date_value', '>=', f'{self.month}-01'),
                ('transaction_id.date_value', '<', self._next_month_first()),
                ('transaction_id.transaction_direction', '=', 'outgoing'),
                ('amount', '>', 0),
            ],
            'target': 'current',
        }
