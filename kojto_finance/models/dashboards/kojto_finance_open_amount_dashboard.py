# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api

class KojtoFinanceOpenAmountDashboard(models.Model):
    _name = 'kojto.finance.open.amount.dashboard'
    _description = 'Finance Open Amount Dashboard'
    _auto = False
    _order = 'open_amount_in_eur desc'

    id = fields.Id()
    invoice_id = fields.Integer(string='Invoice ID', readonly=True)
    date_issue = fields.Date(string='Issue Date', readonly=True)
    date_due = fields.Date(string='Due Date', readonly=True)
    document_in_out_type = fields.Char(string='Direction', readonly=True)
    invoice_type = fields.Char(string='Type', readonly=True)
    consecutive_number = fields.Char(string='Consecutive Number', readonly=True)
    currency = fields.Char(string='Invoice Currency', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Display Currency', readonly=True)
    counterparty_id = fields.Many2one('kojto.contacts', string='Counterparty', readonly=True)
    invoice_total_in_eur = fields.Float(string='Invoice Total', digits=(16, 2), readonly=True)
    allocated_amount_in_eur_incoming = fields.Float(string='Allocated In', digits=(16, 2), readonly=True)
    allocated_amount_in_eur_outgoing = fields.Float(string='Allocated Out', digits=(16, 2), readonly=True)
    open_amount_in_eur = fields.Float(string='Open Amount', digits=(16, 2), readonly=True)
    has_child_documents = fields.Boolean(string='Has Child Documents', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH relevant_invoices AS (
                    -- Get all parent invoices (type 'invoice', active)
                    SELECT
                        inv.id AS parent_id,
                        inv.id AS invoice_id,
                        inv.date_issue,
                        inv.date_due,
                        inv.document_in_out_type,
                        inv.invoice_type,
                        inv.consecutive_number,
                        cur.name AS currency,
                        inv.counterparty_id,
                        inv.exchange_rate_to_eur
                    FROM kojto_finance_invoices inv
                    LEFT JOIN res_currency cur ON cur.id = inv.currency_id
                    WHERE inv.invoice_type = 'invoice'
                      AND inv.active = true
                      AND inv.paid = false
                    UNION ALL
                    -- Get all child credit/debit notes for those parents
                    SELECT
                        child.parent_invoice_id AS parent_id,
                        child.id AS invoice_id,
                        child.date_issue,
                        child.date_due,
                        child.document_in_out_type,
                        child.invoice_type,
                        child.consecutive_number,
                        cur.name AS currency,
                        child.counterparty_id,
                        child.exchange_rate_to_eur
                    FROM kojto_finance_invoices child
                    LEFT JOIN res_currency cur ON cur.id = child.currency_id
                    WHERE child.invoice_type IN ('credit_note', 'debit_note')
                      AND child.active = true
                      AND child.parent_invoice_id IS NOT NULL
                ),
                invoice_totals AS (
                    -- Aggregate all contents for each parent invoice (including its children)
                    SELECT
                        r.parent_id AS invoice_id,
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
                    GROUP BY r.parent_id, i.custom_vat, r.exchange_rate_to_eur
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
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY it.invoice_id) AS id,
                    it.invoice_id,
                    inv.date_issue,
                    inv.date_due,
                    inv.document_in_out_type,
                    inv.invoice_type,
                    inv.consecutive_number,
                    cur.name AS currency,
                    125 AS currency_id,
                    inv.counterparty_id,
                    it.invoice_total_in_eur,
                    COALESCE(a.allocated_amount_in_eur_incoming, 0) AS allocated_amount_in_eur_incoming,
                    COALESCE(a.allocated_amount_in_eur_outgoing, 0) AS allocated_amount_in_eur_outgoing,
                    CASE
                        WHEN inv.document_in_out_type = 'incoming' THEN
                            ROUND(it.invoice_total_in_eur - COALESCE(a.allocated_amount_in_eur_outgoing, 0) + COALESCE(a.allocated_amount_in_eur_incoming, 0), 2)
                        WHEN inv.document_in_out_type = 'outgoing' THEN
                            ROUND(it.invoice_total_in_eur + COALESCE(a.allocated_amount_in_eur_outgoing, 0) - COALESCE(a.allocated_amount_in_eur_incoming, 0), 2)
                        ELSE NULL
                    END AS open_amount_in_eur,
                    EXISTS (
                        SELECT 1 FROM kojto_finance_invoices child
                        WHERE child.parent_invoice_id = it.invoice_id
                          AND child.invoice_type IN ('credit_note', 'debit_note')
                          AND child.active = true
                    ) AS has_child_documents
                FROM invoice_totals it
                JOIN kojto_finance_invoices inv ON inv.id = it.invoice_id
                JOIN res_currency cur ON cur.id = inv.currency_id
                LEFT JOIN allocations a ON a.invoice_id = it.invoice_id
                WHERE inv.invoice_type = 'invoice'
                  AND inv.active = true
                  AND inv.paid = false
                ORDER BY open_amount_in_eur DESC
            )
        ''')
