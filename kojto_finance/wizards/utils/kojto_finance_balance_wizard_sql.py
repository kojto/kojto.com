# -*- coding: utf-8 -*-
"""
Kojto Finance Balance Wizard - SQL Queries

Contains SQL query functions for calculating subcode balances.
"""


def get_subcode_financials_query():
    """
    Returns the SQL query string for calculating subcode financials.

    Returns:
        str: SQL query string with placeholders for parameters
    """
    return """
        SELECT
            subcode_id,
            COALESCE(SUM(CASE WHEN document_in_out_type = 'outgoing' THEN pre_vat_total ELSE 0 END), 0) as outgoing_pre_vat_total,
            COALESCE(SUM(CASE WHEN document_in_out_type = 'incoming' THEN pre_vat_total ELSE 0 END), 0) as incoming_pre_vat_total,
            COALESCE(SUM(invoiceless_revenue_value), 0) as invoiceless_revenue,
            COALESCE(SUM(invoiceless_expenses_value), 0) as invoiceless_expenses,
            COALESCE(SUM(time_tracking_value), 0) as time_tracking_total,
            COALESCE(SUM(time_tracking_hours), 0) as time_tracking_hours,
            COALESCE(SUM(assets_value), 0) as assets_total
        FROM (
            -- Invoice data
            SELECT
                c.subcode_id,
                i.document_in_out_type,
                CASE
                    WHEN i.currency_id = 125 THEN c.pre_vat_total
                    ELSE c.pre_vat_total * COALESCE(i.exchange_rate_to_eur, 1.0)
                END as pre_vat_total,
                0 as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                0 as time_tracking_value,
                0 as time_tracking_hours,
                0 as assets_value
            FROM kojto_finance_invoices i
            INNER JOIN kojto_finance_invoice_contents c ON i.id = c.invoice_id
            WHERE i.date_issue >= %s
                AND i.date_issue <= %s
                AND i.invoice_type != 'proforma'
                AND c.subcode_id IS NOT NULL

            UNION ALL

            -- Invoiceless revenue (incoming allocations without invoice)
            SELECT
                cfa.subcode_id,
                'outgoing' as document_in_out_type,
                0 as pre_vat_total,
                cfa.amount * COALESCE(cf.exchange_rate_to_eur, 1.0) as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                0 as time_tracking_value,
                0 as time_tracking_hours,
                0 as assets_value
            FROM kojto_finance_cashflow cf
            INNER JOIN kojto_finance_cashflow_allocation cfa ON cf.id = cfa.transaction_id
            LEFT JOIN kojto_commission_subcodes sc ON cfa.subcode_id = sc.id
            LEFT JOIN kojto_commission_codes cc ON sc.code_id = cc.id
            LEFT JOIN kojto_commission_main_codes mc ON cc.maincode_id = mc.id
            WHERE cf.date_value >= %s
                AND cf.date_value <= %s
                AND cf.transaction_direction = 'incoming'
                AND cfa.amount > 0
                AND cfa.invoice_id IS NULL
                AND (mc.cash_flow_only IS NOT TRUE)
                AND (cfa.cash_flow_only IS NOT TRUE)
                AND cfa.subcode_id IS NOT NULL

            UNION ALL

            -- Invoiceless expenses (outgoing allocations without invoice)
            SELECT
                cfa.subcode_id,
                'incoming' as document_in_out_type,
                0 as pre_vat_total,
                0 as invoiceless_revenue_value,
                cfa.amount * COALESCE(cf.exchange_rate_to_eur, 1.0) as invoiceless_expenses_value,
                0 as time_tracking_value,
                0 as time_tracking_hours,
                0 as assets_value
            FROM kojto_finance_cashflow cf
            INNER JOIN kojto_finance_cashflow_allocation cfa ON cf.id = cfa.transaction_id
            LEFT JOIN kojto_commission_subcodes sc ON cfa.subcode_id = sc.id
            LEFT JOIN kojto_commission_codes cc ON sc.code_id = cc.id
            LEFT JOIN kojto_commission_main_codes mc ON cc.maincode_id = mc.id
            WHERE cf.date_value >= %s
                AND cf.date_value <= %s
                AND cf.transaction_direction = 'outgoing'
                AND cfa.amount > 0
                AND cfa.invoice_id IS NULL
                AND (mc.cash_flow_only IS NOT TRUE)
                AND (cfa.cash_flow_only IS NOT TRUE)
                AND cfa.subcode_id IS NOT NULL

            UNION ALL

            -- Time tracking data (subtract from work subcode - hours deplete the subcode)
            SELECT
                tt.subcode_id,
                'time_tracking' as document_in_out_type,
                0 as pre_vat_total,
                0 as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                -tt."value_in_EUR" as time_tracking_value,
                -tt.total_hours as time_tracking_hours,
                0 as assets_value
            FROM kojto_hr_time_tracking tt
            WHERE tt.datetime_start >= %s
                AND tt.datetime_start <= %s
                AND tt.total_hours > 0
                AND tt.subcode_id IS NOT NULL

            UNION ALL

            -- Time tracking data (add to costcenter subcode - hours and money credited to costcenter)
            SELECT
                tt.credited_subcode_id as subcode_id,
                'time_tracking' as document_in_out_type,
                0 as pre_vat_total,
                0 as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                tt."value_in_EUR" as time_tracking_value,
                tt.total_hours as time_tracking_hours,
                0 as assets_value
            FROM kojto_hr_time_tracking tt
            WHERE tt.datetime_start >= %s
                AND tt.datetime_start <= %s
                AND tt.total_hours > 0
                AND tt.credited_subcode_id IS NOT NULL

            UNION ALL

            -- Asset works data (subtract from work subcode - quantity depletes the subcode)
            SELECT
                aw.subcode_id,
                'asset_works' as document_in_out_type,
                0 as pre_vat_total,
                0 as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                0 as time_tracking_value,
                0 as time_tracking_hours,
                -aw."value_in_EUR" as assets_value
            FROM kojto_asset_works aw
            WHERE aw.datetime_start >= %s
                AND aw.datetime_start <= %s
                AND aw.quantity > 0
                AND aw.subcode_id IS NOT NULL

            UNION ALL

            -- Asset works data (add to credited subcode - quantity and money credited to costcenter)
            SELECT
                aw.credited_subcode_id as subcode_id,
                'asset_works' as document_in_out_type,
                0 as pre_vat_total,
                0 as invoiceless_revenue_value,
                0 as invoiceless_expenses_value,
                0 as time_tracking_value,
                0 as time_tracking_hours,
                aw."value_in_EUR" as assets_value
            FROM kojto_asset_works aw
            WHERE aw.datetime_start >= %s
                AND aw.datetime_start <= %s
                AND aw.quantity > 0
                AND aw.credited_subcode_id IS NOT NULL
        ) subquery
        GROUP BY subcode_id
    """


def execute_subcode_financials_query(env, date_from, date_to, datetime_from, datetime_to):
    """
    Execute the subcode financials query and return results.

    Args:
        env: Odoo environment
        date_from: Start date (date object)
        date_to: End date (date object)
        datetime_from: Start datetime (datetime object)
        datetime_to: End datetime (datetime object)

    Returns:
        list: Query results as list of tuples
    """
    query = get_subcode_financials_query()
    params = (
        date_from, date_to,
        date_from, date_to,
        date_from, date_to,
        datetime_from, datetime_to,
        datetime_from, datetime_to,
        datetime_from, datetime_to,
        datetime_from, datetime_to
    )
    env.cr.execute(query, params)
    return env.cr.fetchall()

