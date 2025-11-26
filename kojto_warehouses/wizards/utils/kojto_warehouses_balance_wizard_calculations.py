# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Wizard - Calculations

Contains calculation methods for warehouse balance aggregation using SQL for performance.
"""

from datetime import datetime, timedelta


def calculate_warehouse_balance_sql(env, date_from, date_to, warehouse_ids=None, wizard_id=None):
    """
    Calculate warehouse balance using SQL for performance.
    Uses pre-computed transaction_value_pre_vat_eur field.
    If wizard_id is provided, uses the relation table to filter transactions.

    Args:
        env: Odoo environment
        date_from: Start date
        date_to: End date
        warehouse_ids: List of warehouse IDs (None or empty list means all warehouses)
        wizard_id: Optional wizard ID to use relation table for transaction filtering

    Returns:
        dict: Dictionary containing:
            - warehouse_balance_lines: List of dicts with warehouse balance data
            - transaction_lines: List of dicts with transaction data
    """
    if not date_from or not date_to:
        return {
            'warehouse_balance_lines': [],
            'transaction_lines': [],
        }

    if date_from > date_to:
        return {
            'warehouse_balance_lines': [],
            'transaction_lines': [],
        }

    cr = env.cr

    # Calculate beginning value (sum all transactions up to date_from - 1 day)
    date_before_from = (datetime.strptime(str(date_from), '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')

    # Build warehouse filter for SQL
    warehouse_filter = ""
    if warehouse_ids:
        warehouse_ids_str = ','.join(map(str, warehouse_ids))
        warehouse_filter = f"AND b.store_id IN ({warehouse_ids_str})"

    # SQL query to calculate beginning and ending values per warehouse
    # transaction_value_pre_vat_eur already has the sign built in (positive for to_store, negative for from_store)
    # So we just sum them directly
    # Show ALL active warehouses, even if they have no transactions
    warehouse_where = ""
    if warehouse_ids:
        warehouse_ids_str = ','.join(map(str, warehouse_ids))
        warehouse_where = f"AND s.id IN ({warehouse_ids_str})"

    # Build period transaction filter using relation table if wizard_id is provided
    if wizard_id:
        period_transaction_filter = "AND t.id IN (SELECT transaction_id FROM wh_bal_tx_rel WHERE wizard_id = %s)"
        # Two CTEs (period_to_store and period_from_store) each need wizard_id
        period_params = [wizard_id, wizard_id]
    else:
        period_transaction_filter = "AND t.date_issue >= %s AND t.date_issue <= %s"
        # Two CTEs (period_to_store and period_from_store) each need date_from and date_to
        period_params = [date_from, date_to, date_from, date_to]

    query = f"""
        WITH beginning_values AS (
            SELECT
                b.store_id AS warehouse_id,
                COALESCE(SUM(t.transaction_value_pre_vat_eur), 0) AS beginning_value
            FROM kojto_warehouses_transactions t
            INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
            INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
            WHERE t.date_issue < %s
                AND t.transaction_value_pre_vat_eur IS NOT NULL
                {warehouse_filter}
            GROUP BY b.store_id
        ),
        ending_values AS (
            SELECT
                b.store_id AS warehouse_id,
                COALESCE(SUM(t.transaction_value_pre_vat_eur), 0) AS ending_value
            FROM kojto_warehouses_transactions t
            INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
            INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
            WHERE t.date_issue <= %s
                AND t.transaction_value_pre_vat_eur IS NOT NULL
                {warehouse_filter}
            GROUP BY b.store_id
        ),
        period_to_store AS (
            SELECT
                b.store_id AS warehouse_id,
                COALESCE(SUM(t.transaction_value_pre_vat_eur), 0) AS to_store_value
            FROM kojto_warehouses_transactions t
            INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
            INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
            WHERE t.to_from_store = 'to_store'
                AND t.transaction_value_pre_vat_eur IS NOT NULL
                {period_transaction_filter}
                {warehouse_filter}
            GROUP BY b.store_id
        ),
        period_from_store AS (
            SELECT
                b.store_id AS warehouse_id,
                COALESCE(SUM(ABS(t.transaction_value_pre_vat_eur)), 0) AS from_store_value
            FROM kojto_warehouses_transactions t
            INNER JOIN kojto_warehouses_items i ON t.item_id = i.id
            INNER JOIN kojto_warehouses_batches b ON i.batch_id = b.id
            WHERE t.to_from_store = 'from_store'
                AND t.transaction_value_pre_vat_eur IS NOT NULL
                {period_transaction_filter}
                {warehouse_filter}
            GROUP BY b.store_id
        )
        SELECT
            s.id AS warehouse_id,
            s.name AS warehouse_name,
            COALESCE(bv.beginning_value, 0) AS beginning_value,
            COALESCE(ev.ending_value, 0) AS ending_value,
            COALESCE(pts.to_store_value, 0) AS to_store_value,
            COALESCE(pfs.from_store_value, 0) AS from_store_value
        FROM kojto_base_stores s
        LEFT JOIN beginning_values bv ON s.id = bv.warehouse_id
        LEFT JOIN ending_values ev ON s.id = ev.warehouse_id
        LEFT JOIN period_to_store pts ON s.id = pts.warehouse_id
        LEFT JOIN period_from_store pfs ON s.id = pfs.warehouse_id
        WHERE s.active = TRUE
            {warehouse_where}
        ORDER BY s.name
    """

    # Execute query with appropriate parameters
    # Beginning and ending always use date filters, period uses relation table or date filters
    query_params = [date_from, date_to] + period_params
    cr.execute(query, query_params)
    warehouse_results = cr.dictfetchall()

    # Get transaction lines for the period using SQL
    # Note: transaction_quantity is computed, so we compute it here:
    # For sheet/bar types: use item.weight (fallback to override if weight is NULL)
    # For other types (part): use transaction_quantity_override
    # This matches the Python compute_transaction_quantity logic
    if wizard_id:
        # Use relation table to filter transactions
        transaction_where = "t.id IN (SELECT transaction_id FROM wh_bal_tx_rel WHERE wizard_id = %s)"
        transaction_params = [wizard_id]
    else:
        # Use date filtering
        transaction_where = "t.date_issue >= %s AND t.date_issue <= %s"
        transaction_params = [date_from, date_to]

    transaction_query = f"""
        SELECT
            t.id AS transaction_id,
            t.name AS transaction_name,
            t.date_issue,
            b.store_id AS warehouse_id,
            s.name AS warehouse_name,
            item.name AS item_name,
            b.name AS batch_name,
            t.to_from_store AS transaction_type,
            CASE
                WHEN item.item_type IN ('sheet', 'bar') THEN COALESCE(item.weight, t.transaction_quantity_override, 0)
                ELSE COALESCE(t.transaction_quantity_override, 0)
            END AS quantity,
            CASE
                WHEN (CASE
                    WHEN item.item_type IN ('sheet', 'bar') THEN COALESCE(item.weight, t.transaction_quantity_override, 0)
                    ELSE COALESCE(t.transaction_quantity_override, 0)
                END) > 0 THEN
                    ABS(COALESCE(t.transaction_value_pre_vat_eur, 0) /
                        CASE
                            WHEN item.item_type IN ('sheet', 'bar') THEN COALESCE(item.weight, t.transaction_quantity_override, 0)
                            ELSE COALESCE(t.transaction_quantity_override, 0)
                        END)
                ELSE 0
            END AS unit_price_eur,
            t.transaction_value_pre_vat_eur AS transaction_value_eur
        FROM kojto_warehouses_transactions t
        INNER JOIN kojto_warehouses_items item ON t.item_id = item.id
        INNER JOIN kojto_warehouses_batches b ON item.batch_id = b.id
        LEFT JOIN kojto_base_stores s ON b.store_id = s.id
        WHERE {transaction_where}
            AND t.transaction_value_pre_vat_eur IS NOT NULL
            {warehouse_filter if warehouse_ids else ""}
        ORDER BY t.date_issue DESC, t.id DESC
    """

    cr.execute(transaction_query, transaction_params)

    transaction_results = cr.dictfetchall()

    return {
        'warehouse_balance_lines': warehouse_results,
        'transaction_lines': transaction_results,
    }


def calculate_warehouse_balance(env, date_from, date_to, warehouse_ids=None, wizard_id=None):
    """
    Calculate warehouse balance - returns calculated data only (no record creation).
    Uses SQL for performance optimization.

    Args:
        env: Odoo environment
        date_from: Start date
        date_to: End date
        warehouse_ids: List of warehouse IDs (None or empty list means all warehouses)
        wizard_id: Optional wizard ID to use relation table for transaction filtering

    Returns:
        dict: Dictionary containing:
            - warehouse_balance_lines: List of dicts with warehouse balance data
            - transaction_lines: List of dicts with transaction data
    """
    # Use SQL-based calculation for performance
    return calculate_warehouse_balance_sql(env, date_from, date_to, warehouse_ids, wizard_id)

