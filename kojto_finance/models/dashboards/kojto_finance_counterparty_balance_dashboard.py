# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api

class KojtoFinanceCounterpartyBalanceDashboard(models.Model):
    _name = 'kojto.finance.counterparty.balance.dashboard'
    _description = 'Finance Counterparty Balance Dashboard'
    _auto = False
    _order = 'net_balance_in_eur desc'

    id = fields.Id()
    counterparty_id = fields.Many2one('kojto.contacts', string='Counterparty', readonly=True)
    receivables_in_eur = fields.Float(string='What They Owe Us', digits=(16, 2), readonly=True)
    payables_in_eur = fields.Float(string='What We Owe Them', digits=(16, 2), readonly=True)
    net_balance_in_eur = fields.Float(string='Net Balance', digits=(16, 2), readonly=True)
    currency_id = fields.Many2one('res.currency', string='Display Currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH relevant_invoices AS (
                    -- Get all parent invoices (type 'invoice', active)
                    SELECT
                        inv.id AS parent_id,
                        inv.id AS invoice_id,
                        inv.document_in_out_type,
                        inv.counterparty_id,
                        inv.exchange_rate_to_eur
                    FROM kojto_finance_invoices inv
                    WHERE inv.invoice_type = 'invoice'
                      AND inv.active = true
                      AND inv.paid = false
                    UNION ALL
                    -- Get all child credit/debit notes for those parents (only if parent is unpaid)
                    SELECT
                        child.parent_invoice_id AS parent_id,
                        child.id AS invoice_id,
                        child.document_in_out_type,
                        child.counterparty_id,
                        child.exchange_rate_to_eur
                    FROM kojto_finance_invoices child
                    JOIN kojto_finance_invoices parent ON parent.id = child.parent_invoice_id
                    WHERE child.invoice_type IN ('credit_note', 'debit_note')
                      AND child.active = true
                      AND child.parent_invoice_id IS NOT NULL
                      AND parent.paid = false
                      AND parent.invoice_type = 'invoice'
                      AND parent.active = true
                ),
                invoice_totals AS (
                    -- Aggregate all contents for each parent invoice (including its children)
                    SELECT
                        r.parent_id AS invoice_id,
                        r.document_in_out_type,
                        r.counterparty_id,
                        ROUND(
                            COALESCE(
                                CASE
                                    WHEN i.custom_vat IS NOT NULL AND i.custom_vat != 0 THEN
                                        SUM(CASE WHEN ic.is_redistribution IS NOT TRUE THEN ic.pre_vat_total ELSE 0 END) + i.custom_vat
                                    ELSE
                                        SUM(CASE WHEN ic.is_redistribution IS NOT TRUE THEN ic.pre_vat_total * (1 + COALESCE(ic.vat_rate, 0)/100) ELSE 0 END)
                                END,
                                0
                            ) * COALESCE(r.exchange_rate_to_eur, 1),
                        2) AS invoice_total_in_eur
                    FROM relevant_invoices r
                    LEFT JOIN kojto_finance_invoice_contents ic ON ic.invoice_id = r.invoice_id
                    LEFT JOIN kojto_finance_invoices i ON i.id = r.parent_id
                    GROUP BY r.parent_id, i.custom_vat, r.exchange_rate_to_eur, r.document_in_out_type, r.counterparty_id
                ),
                allocations AS (
                    -- Pre-aggregate allocations by invoice and direction
                    SELECT
                        alloc.invoice_id,
                        ROUND(COALESCE(SUM(CASE WHEN cf.transaction_direction = 'incoming' THEN alloc.amount * cf.exchange_rate_to_eur ELSE 0 END), 0), 2) AS allocated_amount_in_eur_incoming,
                        ROUND(COALESCE(SUM(CASE WHEN cf.transaction_direction = 'outgoing' THEN alloc.amount * cf.exchange_rate_to_eur ELSE 0 END), 0), 2) AS allocated_amount_in_eur_outgoing
                    FROM kojto_finance_cashflow_allocation alloc
                    JOIN kojto_finance_cashflow cf ON cf.id = alloc.transaction_id
                    WHERE EXISTS (
                        SELECT 1 FROM invoice_totals it WHERE it.invoice_id = alloc.invoice_id
                    )
                    GROUP BY alloc.invoice_id
                ),
                invoice_open_amounts AS (
                    SELECT
                        it.invoice_id,
                        it.counterparty_id,
                        it.document_in_out_type,
                        CASE
                            WHEN it.document_in_out_type = 'incoming' THEN
                                ROUND(it.invoice_total_in_eur - COALESCE(a.allocated_amount_in_eur_outgoing, 0) + COALESCE(a.allocated_amount_in_eur_incoming, 0), 2)
                            WHEN it.document_in_out_type = 'outgoing' THEN
                                ROUND(it.invoice_total_in_eur + COALESCE(a.allocated_amount_in_eur_outgoing, 0) - COALESCE(a.allocated_amount_in_eur_incoming, 0), 2)
                            ELSE NULL
                        END AS open_amount_in_eur
                    FROM invoice_totals it
                    LEFT JOIN allocations a ON a.invoice_id = it.invoice_id
                    JOIN kojto_finance_invoices inv ON inv.id = it.invoice_id
                    WHERE inv.invoice_type = 'invoice'
                      AND inv.active = true
                      AND inv.paid = false
                )
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    counterparty_id,
                    ROUND(COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN open_amount_in_eur ELSE 0 END), 0), 2) AS receivables_in_eur,
                    ROUND(COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN open_amount_in_eur ELSE 0 END), 0), 2) AS payables_in_eur,
                    ROUND(COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN open_amount_in_eur ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN open_amount_in_eur ELSE 0 END), 0), 2) AS net_balance_in_eur,
                    125 AS currency_id
                FROM invoice_open_amounts
                WHERE counterparty_id IS NOT NULL
                GROUP BY counterparty_id
                HAVING ABS(COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN open_amount_in_eur ELSE 0 END), 0)) >= 1
                    OR ABS(COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN open_amount_in_eur ELSE 0 END), 0)) >= 1
                ORDER BY (COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN open_amount_in_eur ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN open_amount_in_eur ELSE 0 END), 0)) DESC
            )
        ''')

