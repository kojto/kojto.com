# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api


class KojtoFinanceRevenueExpenseDashboard(models.Model):
    _name = 'kojto.finance.revenue.expense.dashboard'
    _description = 'Finance Revenue Expense Dashboard'
    _auto = False
    _order = 'year desc, quarter desc, month desc'

    year = fields.Char(string='Year (YYYY)', readonly=True)
    quarter = fields.Char(string='Quarter (YYYY-QN)', readonly=True)
    month = fields.Char(string='Month (YYYY-MM)', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', readonly=True)

    outgoing_pre_vat_total = fields.Float(string='Outgoing Pre-VAT Total', digits=(16, 2), readonly=True)
    incoming_pre_vat_total = fields.Float(string='Incoming Pre-VAT Total', digits=(16, 2), readonly=True)
    invoiceless_revenue = fields.Float(string='Invoiceless Revenue', digits=(16, 2), readonly=True)
    invoiceless_expenses = fields.Float(string='Invoiceless Expenses', digits=(16, 2), readonly=True)
    result = fields.Float(string='Result', digits=(16, 2), readonly=True)

    # Remove time_tracking_total and time_tracking_hours fields


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
                    ROW_NUMBER() OVER (ORDER BY period DESC) as id,
                    period,
                    EXTRACT(YEAR FROM TO_DATE(period, 'YYYY-MM')) as year,
                    EXTRACT(YEAR FROM TO_DATE(period, 'YYYY-MM')) || '-Q' || EXTRACT(QUARTER FROM TO_DATE(period, 'YYYY-MM')) as quarter,
                    period as month,
                    COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN pre_vat_total ELSE 0 END), 0) as outgoing_pre_vat_total,
                    COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN pre_vat_total ELSE 0 END), 0) as incoming_pre_vat_total,
                    COALESCE(SUM(invoiceless_revenue_value), 0) as invoiceless_revenue,
                    COALESCE(SUM(invoiceless_expenses_value), 0) as invoiceless_expenses,
                    (COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN pre_vat_total ELSE 0 END), 0)
                     - COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN pre_vat_total ELSE 0 END), 0)
                     - COALESCE(SUM(invoiceless_expenses_value), 0)
                     + COALESCE(SUM(invoiceless_revenue_value), 0)) as result
                FROM (
                    -- Invoice data
                    SELECT
                        TO_CHAR(i.date_issue, 'YYYY-MM') as period,
                        i.document_in_out_type,
                        i.invoice_type,
                        COALESCE(SUM(
                            CASE
                                WHEN i.currency_id = target_currency.currency_id THEN c.pre_vat_total
                                ELSE c.pre_vat_total * COALESCE(
                                    CASE
                                        WHEN target_currency.currency_id = 26 THEN i.exchange_rate_to_bgn
                                        ELSE i.exchange_rate_to_eur
                                    END, 1.0)
                            END
                        ), 0) as pre_vat_total,
                        0 as time_tracking_value,
                        0 as time_tracking_hours,
                        0 as invoiceless_expenses_value,
                        0 as invoiceless_revenue_value
                    FROM kojto_finance_invoices i
                    LEFT JOIN kojto_finance_invoice_contents c ON i.id = c.invoice_id
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
                    WHERE i.date_issue IS NOT NULL
                        AND i.invoice_type != 'proforma'
                    GROUP BY TO_CHAR(i.date_issue, 'YYYY-MM'), i.document_in_out_type, i.invoice_type, i.currency_id, i.exchange_rate_to_bgn, i.exchange_rate_to_eur, target_currency.currency_id

                    UNION ALL

                    -- Time tracking data
                    SELECT
                        TO_CHAR(tt.datetime_start, 'YYYY-MM') as period,
                        'time_tracking' as document_in_out_type,
                        'time_tracking' as invoice_type,
                        0 as pre_vat_total,
                        COALESCE(SUM(
                            CASE
                                WHEN target_currency.currency_id = 26 THEN tt."value_in_BGN"
                                ELSE tt."value_in_EUR"
                            END
                        ), 0) as time_tracking_value,
                        COALESCE(SUM(tt.total_hours), 0) as time_tracking_hours,
                        0 as invoiceless_expenses_value,
                        0 as invoiceless_revenue_value
                    FROM kojto_hr_time_tracking tt
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
                    WHERE tt.datetime_start IS NOT NULL
                        AND tt.total_hours > 0
                    GROUP BY TO_CHAR(tt.datetime_start, 'YYYY-MM'), target_currency.currency_id

                    UNION ALL

                    -- Invoiceless expenses data (allocations with no invoice, not cash_flow_only, not cash_flow_only_inherited)
                    SELECT
                        TO_CHAR(cf.date_value, 'YYYY-MM') as period,
                        'outgoing' as document_in_out_type,
                        'invoiceless_expenses' as invoice_type,
                        0 as pre_vat_total,
                        0 as time_tracking_value,
                        0 as time_tracking_hours,
                        COALESCE(SUM(
                            CASE
                                WHEN target_currency.currency_id = 26 THEN cfa.amount * cf.exchange_rate_to_bgn
                                ELSE cfa.amount * cf.exchange_rate_to_eur
                            END
                        ), 0) as invoiceless_expenses_value,
                        0 as invoiceless_revenue_value
                    FROM kojto_finance_cashflow cf
                    INNER JOIN kojto_finance_cashflow_allocation cfa ON cf.id = cfa.transaction_id
                    LEFT JOIN kojto_commission_subcodes sc ON cfa.subcode_id = sc.id
                    LEFT JOIN kojto_commission_codes cc ON sc.code_id = cc.id
                    LEFT JOIN kojto_commission_main_codes mc ON cc.maincode_id = mc.id
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
                    WHERE cf.date_value IS NOT NULL
                        AND cf.transaction_direction = 'outgoing'
                        AND cfa.amount > 0
                        AND cfa.invoice_id IS NULL
                        AND (mc.cash_flow_only IS NOT TRUE)
                        AND (cfa.cash_flow_only IS NOT TRUE)
                    GROUP BY TO_CHAR(cf.date_value, 'YYYY-MM'), target_currency.currency_id

                    UNION ALL

                    -- Invoiceless revenue data (allocations with no invoice, not cash_flow_only, not cash_flow_only_inherited, incoming)
                    SELECT
                        TO_CHAR(cf.date_value, 'YYYY-MM') as period,
                        'incoming' as document_in_out_type,
                        'invoiceless_revenue' as invoice_type,
                        0 as pre_vat_total,
                        0 as time_tracking_value,
                        0 as time_tracking_hours,
                        0 as invoiceless_expenses_value,
                        COALESCE(SUM(
                            CASE
                                WHEN target_currency.currency_id = 26 THEN cfa.amount * cf.exchange_rate_to_bgn
                                ELSE cfa.amount * cf.exchange_rate_to_eur
                            END
                        ), 0) as invoiceless_revenue_value
                    FROM kojto_finance_cashflow cf
                    INNER JOIN kojto_finance_cashflow_allocation cfa ON cf.id = cfa.transaction_id
                    LEFT JOIN kojto_commission_subcodes sc ON cfa.subcode_id = sc.id
                    LEFT JOIN kojto_commission_codes cc ON sc.code_id = cc.id
                    LEFT JOIN kojto_commission_main_codes mc ON cc.maincode_id = mc.id
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
                    WHERE cf.date_value IS NOT NULL
                        AND cf.transaction_direction = 'incoming'
                        AND cfa.amount > 0
                        AND cfa.invoice_id IS NULL
                        AND (mc.cash_flow_only IS NOT TRUE)
                        AND (cfa.cash_flow_only IS NOT TRUE)
                    GROUP BY TO_CHAR(cf.date_value, 'YYYY-MM'), target_currency.currency_id
                ) subquery
                GROUP BY period
                ORDER BY period DESC
            )
        ''')

    def action_outgoing_invoice_contents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Outgoing Invoice Contents',
            'res_model': 'kojto.finance.invoice.contents',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_invoice_contents_list').id, 'list'), (False, 'form')],
            'domain': [
                ('invoice_id.date_issue', '>=', f'{self.month}-01'),
                ('invoice_id.date_issue', '<', self._next_month_first()),
                ('invoice_id.document_in_out_type', '=', 'outgoing'),
                ('invoice_id.invoice_type', '!=', 'proforma'),
            ],
            'target': 'current',
        }

    def action_incoming_invoice_contents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Incoming Invoice Contents',
            'res_model': 'kojto.finance.invoice.contents',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_invoice_contents_list').id, 'list'), (False, 'form')],
            'domain': [
                ('invoice_id.date_issue', '>=', f'{self.month}-01'),
                ('invoice_id.date_issue', '<', self._next_month_first()),
                ('invoice_id.document_in_out_type', '=', 'incoming'),
                ('invoice_id.invoice_type', '!=', 'proforma'),
            ],
            'target': 'current',
        }

    def _next_month_first(self):
        # self.month is 'YYYY-MM'
        from datetime import datetime
        year, month = map(int, self.month.split('-'))
        if month == 12:
            return f'{year+1}-01-01'
        else:
            return f'{year}-{str(month+1).zfill(2)}-01'

    def action_invoiceless_revenue(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoiceless Revenue Allocations',
            'res_model': 'kojto.finance.cashflow.allocation',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_cashflow_allocation_list').id, 'list'), (False, 'form')],
            'domain': [
                ('transaction_id.date_value', '>=', f'{self.month}-01'),
                ('transaction_id.date_value', '<', self._next_month_first()),
                ('transaction_id.transaction_direction', '=', 'incoming'),
                ('amount', '>', 0),
                ('invoice_id', '=', False),
                ('subcode_id.code_id.maincode_id.cash_flow_only', '=', False),
                ('cash_flow_only', '=', False),
            ],
            'target': 'current',
        }

    def action_invoiceless_expense(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoiceless Expense Allocations',
            'res_model': 'kojto.finance.cashflow.allocation',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_finance.view_kojto_finance_cashflow_allocation_list').id, 'list'), (False, 'form')],
            'domain': [
                ('transaction_id.date_value', '>=', f'{self.month}-01'),
                ('transaction_id.date_value', '<', self._next_month_first()),
                ('transaction_id.transaction_direction', '=', 'outgoing'),
                ('amount', '>', 0),
                ('invoice_id', '=', False),
                ('subcode_id.code_id.maincode_id.cash_flow_only', '=', False),
                ('cash_flow_only', '=', False),
            ],
            'target': 'current',
        }
