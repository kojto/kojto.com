# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api

class KojtoFinanceVatBalanceDashboard(models.Model):
    _name = 'kojto.finance.vat.balance.dashboard'
    _description = 'Finance VAT Balance Dashboard'
    _auto = False
    _order = 'year desc, quarter desc, month desc'

    year = fields.Char(string='Year (YYYY)', readonly=True)
    quarter = fields.Char(string='Quarter (YYYY-QN)', readonly=True)
    month = fields.Char(string='Month (YYYY-MM)', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', readonly=True)

    outgoing_vat_total = fields.Float(string='Outgoing VAT Total', digits=(16, 2), readonly=True)
    incoming_vat_total = fields.Float(string='Incoming VAT Total', digits=(16, 2), readonly=True)
    result = fields.Float(string='Result', digits=(16, 2), readonly=True)

    @api.depends()
    def _compute_currency_id(self):
        contact = self.env['kojto.contacts'].browse(1)
        currency_id = contact.currency_id.id if contact.exists() and contact.currency_id else False
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
                    COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN vat_total ELSE 0 END), 0) as outgoing_vat_total,
                    COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN vat_total ELSE 0 END), 0) as incoming_vat_total,
                    (COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN vat_total ELSE 0 END), 0)
                     - COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN vat_total ELSE 0 END), 0)) as result
                FROM (
                    SELECT
                        TO_CHAR(i.date_issue, 'YYYY-MM') as period,
                        i.document_in_out_type,
                        i.invoice_type,
                        COALESCE(SUM(
                            CASE
                                WHEN i.currency_id = target_currency.currency_id THEN (c.pre_vat_total * c.vat_rate / 100.0)
                                ELSE (c.pre_vat_total * c.vat_rate / 100.0) * COALESCE(
                                    CASE
                                        WHEN target_currency.currency_id = 26 THEN i.exchange_rate_to_bgn
                                        ELSE i.exchange_rate_to_eur
                                    END, 1.0)
                            END
                        ), 0) as vat_total
                    FROM kojto_finance_invoices i
                    LEFT JOIN kojto_finance_invoice_contents c ON i.id = c.invoice_id
                    CROSS JOIN (
                        SELECT
                            CASE
                                WHEN contact_currency.id = 26 THEN 26
                                ELSE 125
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
                ('pre_vat_total', '!=', 0),
                ('vat_rate', '!=', 0),
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
                ('pre_vat_total', '!=', 0),
                ('vat_rate', '!=', 0),
            ],
            'target': 'current',
        }

    def _next_month_first(self):
        from datetime import datetime
        year, month = map(int, self.month.split('-'))
        if month == 12:
            return f'{year+1}-01-01'
        else:
            return f'{year}-{str(month+1).zfill(2)}-01'
